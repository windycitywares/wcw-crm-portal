"""Etsy orders → the CRM, one way. A paid Etsy order is created automatically; later syncs refresh what Etsy says
(prices, address, shipped, cancelled) and never touch what the team entered. Status only moves the way
etsy/status.py allows, and every change is written to the order's history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode

from .connection import CHANNEL, EtsyConnectionService
from .etsy import client as etsy_client
from .etsy import receipt as etsy_receipt
from .etsy import status as etsy_status
from .etsy.client import EtsyError
from .models import ChannelListing, ChannelOrder, ChannelOrderEvent, ChannelOrderItem

PAGE = 100
EVERY = timedelta(minutes=5)
FIRST_LOOKBACK = timedelta(days=180)  # the first run brings in the recent past
LOOKBACK = timedelta(days=45)  # later runs re-read this window, so shipped / cancelled changes on older orders arrive too

# Etsy's names → ours. Fields copied from Etsy on every sync; the team's own columns are never in this list.
RENAME = {"etsy_receipt_id": "external_id", "etsy_state": "external_state", "etsy_buyer_id": "external_buyer_id",
          "etsy_updated_at": "external_updated_at"}
MARKETPLACE_FIELDS = (
    "external_state", "ship_by", "buyer_name", "external_buyer_id", "buyer_email", "ship_address", "gift_message",
    "buyer_note", "currency", "items_total", "shipping_charged", "discounts", "tax", "grand_total", "external_updated_at",
)


def _order(parsed: dict[str, Any]) -> dict[str, Any]:
    return {RENAME.get(k, k): v for k, v in parsed.items()}


def _item(parsed: dict[str, Any]) -> dict[str, Any]:
    out = dict(parsed)
    out["external_id"] = out.pop("etsy_transaction_id")
    out["listing_external_id"] = out.pop("etsy_listing_id")
    return out


def _event(order_id: int, kind: str, message: str, frm: str | None = None, to: str | None = None) -> ChannelOrderEvent:
    return ChannelOrderEvent(order_id=order_id, kind=kind, from_status=frm, to_status=to, message=message[:500],
                             source="etsy", actor_name="Etsy")


class EtsyOrderSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, force: bool = False) -> dict[str, Any]:
        service = EtsyConnectionService(self.session)
        conn = await service.row()
        if not (conn.access_token_enc and conn.external_shop_id):
            return {"skipped": "not connected"}
        now = datetime.now(timezone.utc)
        if not force and conn.orders_synced_at and now - conn.orders_synced_at < EVERY:
            return {"skipped": "not due"}
        since = now - (LOOKBACK if conn.orders_synced_at else FIRST_LOOKBACK)
        created = updated = 0
        try:
            key, token = await service.access_token()
            offset = 0
            while True:
                data = await etsy_client.get(
                    f"/shops/{conn.external_shop_id}/receipts", api_key=key, access_token=token,
                    params={"min_created": int(since.timestamp()), "limit": PAGE, "offset": offset,
                            "sort_on": "created", "sort_order": "asc"})
                results = data.get("results") or []
                for raw in results:
                    outcome = await self._apply(etsy_receipt.parse(raw), now)
                    created, updated = created + (outcome == "created"), updated + (outcome == "updated")
                offset += PAGE
                if len(results) < PAGE:
                    break
        except EtsyError as exc:
            await self.session.rollback()
            await service.fail(f"Order sync: {exc}")
            return {"error": str(exc)[:200]}
        conn = await service.row()
        conn.orders_synced_at, conn.last_error, conn.last_error_at = now, None, None
        await self.session.commit()
        return {"created": created, "updated": updated}

    async def _apply(self, parsed: dict[str, Any], now: datetime) -> str | None:
        o = _order(parsed["order"])
        items = [_item(i) for i in parsed["items"]]
        implied, etsy_track, etsy_carrier = o.pop("implied_status"), o.pop("etsy_tracking"), o.pop("etsy_carrier")
        etsy_shipped = o.pop("etsy_shipped_at")
        row = (await self.session.execute(select(ChannelOrder).where(
            ChannelOrder.channel == CHANNEL, ChannelOrder.external_id == o["external_id"]))).scalar_one_or_none()
        if row is None:
            if not o["paid_at"] or not o["ordered_at"]:
                return None  # not paid (yet): an order starts when Etsy says it is paid
            return await self._create(o, items, implied, etsy_track, etsy_carrier, etsy_shipped or now)
        for k in MARKETPLACE_FIELDS:
            setattr(row, k, o[k])
        row.synced_at = now
        if o["paid_at"] and not row.paid_at:
            row.paid_at = o["paid_at"]
        target = etsy_status.sync_target(row.status, implied)
        if target != row.status:
            self.session.add(_event(row.id, "status",
                                    f"Etsy: {etsy_status.LABELS[row.status]} → {etsy_status.LABELS[target]}", row.status, target))
            row.status = target
            if target in (etsy_status.SHIPPED, etsy_status.DELIVERED):
                row.shipped_at = row.shipped_at or etsy_shipped or now
            if target == etsy_status.DELIVERED:
                row.delivered_at = row.delivered_at or now
        if etsy_track and not row.tracking_number:
            row.tracking_number, row.carrier, row.tracking_sent_at = etsy_track, etsy_carrier, now  # Etsy already has it
            self.session.add(_event(row.id, "tracking", f"Etsy has tracking {etsy_track}"))
        await self._add_missing_items(row.id, items)
        return "updated"

    async def _create(self, o, items, implied, etsy_track, etsy_carrier, shipped_at) -> str:
        now = datetime.now(timezone.utc)
        cost, supplier = await self._defaults(items)
        row = ChannelOrder(
            channel=CHANNEL, **o, status=implied, synced_at=now,
            purchase_cost=cost, costs_prefilled=cost is not None, supplier_account_id=supplier,
            past_order=implied in (etsy_status.SHIPPED, etsy_status.DELIVERED, etsy_status.CANCELLED),
            tracking_number=etsy_track, carrier=etsy_carrier, tracking_sent_at=now if etsy_track else None,
            shipped_at=shipped_at if implied in (etsy_status.SHIPPED, etsy_status.DELIVERED) else None,
            delivered_at=now if implied == etsy_status.DELIVERED else None,
        )
        if cost is not None:
            row.cost_source = "listing"
        self.session.add(row)
        await self.session.flush()
        self.session.add(_event(row.id, "created", f"Order {row.external_id} arrived from Etsy", None, implied))
        for it in items:
            self.session.add(ChannelOrderItem(order_id=row.id, **it))
        await self.session.flush()
        from .order_costs import OrderCostService  # costs from SKUs when every line can be priced

        try:
            async with self.session.begin_nested():
                await OrderCostService(self.session).on_new_order(row)
        except Exception:  # noqa: BLE001 - costing must never stop an order arriving; it stays as above
            pass
        return "created"

    async def _add_missing_items(self, order_id: int, items: list[dict[str, Any]]) -> None:
        have = set((await self.session.execute(
            select(ChannelOrderItem.external_id).where(ChannelOrderItem.order_id == order_id))).scalars().all())
        for it in items:
            if it["external_id"] not in have:
                self.session.add(ChannelOrderItem(order_id=order_id, **it))

    async def _defaults(self, items: list[dict[str, Any]]) -> tuple[Decimal | None, int | None]:
        """Start the cost from the listings' cost (only when every item has one) and the supplier (when there is one)."""
        ids = {i["listing_external_id"] for i in items if i["listing_external_id"]}
        if not ids or any(i["listing_external_id"] is None for i in items):
            return None, None
        listings = {lst.external_id: lst for lst in (await self.session.execute(select(ChannelListing).where(
            ChannelListing.channel == CHANNEL, ChannelListing.external_id.in_(ids)))).scalars()}
        total = Decimal("0.00")
        for i in items:
            lst = listings.get(i["listing_external_id"])
            if lst is None or lst.purchase_cost is None:
                return None, None
            total += lst.purchase_cost * i["quantity"]
        suppliers = {lst.supplier_account_id for lst in listings.values() if lst.supplier_account_id}
        return total, (suppliers.pop() if len(suppliers) == 1 else None)


async def job(session: AsyncSession) -> str | None:
    """The `etsy-orders` job: every 5 minutes while Etsy is connected (never in test mode)."""
    if appmode.is_test():
        return None
    result = await EtsyOrderSync(session).run()
    if "skipped" in result:
        return None
    if "error" in result:
        return f"etsy orders: {result['error']}"
    return f"etsy orders: {result['created']} new, {result['updated']} refreshed" if result["created"] else None
