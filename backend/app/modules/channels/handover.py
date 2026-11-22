"""The one-time copy of the team's Etsy work from the shop (shop docs/CRM_SYNC.md → "Etsy move").

Etsy syncs straight into the CRM now; the shop still holds what the team entered there — costs, suppliers, notes,
tracking, supplier payments, status and history. This copies it in and reports the counts both sides should agree on.
It is safe to run again: it only fills what the CRM doesn't have yet, and never adds a history line twice. Suppliers
are matched to Supplier accounts by the CRM supplier the shop's copy mirrors, else by name."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.shop.client import ShopApiError, shop_client
from app.modules.accounts.models import Account
from app.modules.audit.service import AuditService
from app.modules.settings.service import SettingsService
from app.modules.suppliers.models import Supplier

from .connection import CHANNEL
from .etsy import status as etsy_status
from .models import ChannelListing, ChannelOrder, ChannelOrderEvent

TEAM_FIELDS = ("purchase_cost", "supplier_order_number", "supplier_paid_at", "supplier_paid_amount",
               "supplier_payment_ref", "shipping_cost", "carrier", "tracking_number", "tracking_sent_at", "purchased_at",
               "shipped_at", "delivered_at", "notes", "buyer_phone")
MONEY = {"purchase_cost", "supplier_paid_amount", "shipping_cost"}
WHEN = {"supplier_paid_at", "tracking_sent_at", "purchased_at", "shipped_at", "delivered_at"}


def _value(field: str, raw: Any) -> Any:
    if raw is None:
        return None
    if field in MONEY:
        return Decimal(str(raw))
    if field in WHEN:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return raw


class ShopHandover:
    def __init__(self, session: AsyncSession, client=None):
        self.session = session
        self.client = client
        self._accounts: dict[str, int | None] = {}

    async def _shop(self):
        if self.client is None:
            self.client = shop_client(await SettingsService(self.session).get_model("shop"))
        return self.client

    async def _account(self, crm_id: int | None, name: str | None) -> int | None:
        key = f"{crm_id}|{(name or '').lower()}"
        if key in self._accounts:
            return self._accounts[key]
        found = None
        if crm_id:
            found = (await self.session.execute(select(Supplier.account_id).where(Supplier.id == crm_id))).scalar()
        if found is None and name:
            found = (await self.session.execute(select(Account.id).where(
                func.lower(Account.name) == name.strip().lower(), Account.account_type == "supplier",
                Account.deleted_at.is_(None)).order_by(Account.id).limit(1))).scalar()
        self._accounts[key] = found
        return found

    async def run(self, actor) -> dict[str, Any]:
        shop = await self._shop()
        out = {"listings": 0, "orders": 0, "orders_not_in_crm": 0, "events": 0, "suppliers_not_found": set()}
        after: int | None = 0
        while after is not None:
            page = await shop.etsy_handover("listings", after)
            for item in page.get("items", []):
                out["listings"] += await self._listing(item, out)
            after = page.get("next_after_id")
        after = 0
        while after is not None:
            page = await shop.etsy_handover("orders", after)
            for item in page.get("items", []):
                await self._order(item, out)
            after = page.get("next_after_id")
        out["suppliers_not_found"] = sorted(out["suppliers_not_found"])
        await AuditService(self.session).record("channel.shop_handover", actor=actor, entity_type="channel",
                                                changes={k: v for k, v in out.items()})
        await self.session.commit()
        out["check"] = await self.check()
        return out

    async def _listing(self, item: dict[str, Any], out: dict[str, Any]) -> int:
        row = (await self.session.execute(select(ChannelListing).where(
            ChannelListing.channel == CHANNEL, ChannelListing.external_id == item["etsy_listing_id"]))).scalar_one_or_none()
        if row is None:
            return 0
        changed = False
        if item.get("supplier") and row.supplier_account_id is None:
            account = await self._account(item.get("supplier_crm_id"), item["supplier"])
            if account is None:
                out["suppliers_not_found"].add(item["supplier"])
            else:
                row.supplier_account_id, changed = account, True
        if item.get("purchase_cost") is not None and row.purchase_cost is None:
            row.purchase_cost, changed = Decimal(str(item["purchase_cost"])), True
        if item.get("notes") and not row.notes:
            row.notes, changed = item["notes"], True
        return int(changed)

    async def _order(self, item: dict[str, Any], out: dict[str, Any]) -> None:
        row = (await self.session.execute(select(ChannelOrder).where(
            ChannelOrder.channel == CHANNEL, ChannelOrder.external_id == item["etsy_receipt_id"]))).scalar_one_or_none()
        if row is None:
            out["orders_not_in_crm"] += 1
            return
        changed = False
        for field in TEAM_FIELDS:
            value = _value(field, item.get(field))
            if value is not None and getattr(row, field) in (None, ""):
                setattr(row, field, value)
                changed = True
        if item.get("supplier") and row.supplier_account_id is None:
            account = await self._account(item.get("supplier_crm_id"), item["supplier"])
            if account is None:
                out["suppliers_not_found"].add(item["supplier"])
            else:
                row.supplier_account_id, changed = account, True
        if item.get("purchase_cost") is not None and row.costs_prefilled and not item.get("costs_prefilled"):
            row.costs_prefilled = False
        if item.get("past_order") and not row.past_order:
            row.past_order, changed = True, True
        shop_status = item.get("status")
        if shop_status and shop_status != row.status and etsy_status.is_valid(shop_status) \
                and (shop_status in etsy_status.EXCEPTIONS or etsy_status.sync_target(row.status, shop_status) == shop_status):
            row.status, changed = shop_status, True  # the team's word (an exception, or further along) wins
        have = {(e.message, e.created_at.replace(microsecond=0)) for e in (await self.session.execute(
            select(ChannelOrderEvent).where(ChannelOrderEvent.order_id == row.id))).scalars()}
        for e in item.get("events", []):
            at = datetime.fromisoformat(str(e["created_at"]).replace("Z", "+00:00"))
            if (e["message"][:500], at.replace(microsecond=0)) in have:
                continue
            self.session.add(ChannelOrderEvent(order_id=row.id, kind=e["kind"], from_status=e.get("from_status"),
                                               to_status=e.get("to_status"), message=e["message"][:500], source="team",
                                               actor_name=e.get("actor_name"), created_at=at))
            out["events"] += 1
        out["orders"] += int(changed)

    async def check(self) -> dict[str, Any]:
        """The shop's counts beside the CRM's, so the copy can be checked before the shop's Etsy is switched off."""
        shop = (await (await self._shop()).etsy_handover("counts"))
        mine = lambda *cond: self.session.execute(select(func.count()).select_from(ChannelOrder).where(  # noqa: E731
            ChannelOrder.channel == CHANNEL, *cond))
        crm = {
            "orders": (await mine()).scalar_one(),
            "orders_with_cost": (await mine(ChannelOrder.purchase_cost.is_not(None))).scalar_one(),
            "orders_with_supplier": (await mine(ChannelOrder.supplier_account_id.is_not(None))).scalar_one(),
            "orders_paid": (await mine(ChannelOrder.supplier_paid_at.is_not(None))).scalar_one(),
        }
        return {"shop": shop, "crm": crm,
                "matches": all(crm[k] >= shop.get(k, 0) for k in crm)}


async def handover(session: AsyncSession, actor) -> dict[str, Any]:
    try:
        return await ShopHandover(session).run(actor)
    except ShopApiError as exc:
        from app.core.exceptions import ValidationFailedError

        raise ValidationFailedError(f"The shop didn't answer: {exc}") from exc
