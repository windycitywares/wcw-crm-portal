"""Suppliers travel to the shop (shop docs/CRM_SYNC.md → "Suppliers"). The CRM owns the supplier list; the shop keeps a
read-only copy that its Etsy screens and supplier logins pick from.

* The `shop-suppliers` job sends every supplier added, changed, archived or whose contacts changed, found through the
  append-only audit log (like the opt-outs job), so no path has to remember to call it and nothing is lost while the
  shop is down: it keeps its place in `app_settings["shop_suppliers"]`. Its first run sends every supplier, which links
  the ones the shop already had by name.
* `import_from_shop` brings the shop's existing names into the CRM once (an admin presses it on the Suppliers page).
* `shop_stats` reads one supplier's figures from the shop for the CRM supplier page.

Live data only: the shop's supplier list has no Test copy, so the job doesn't run in Test mode.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.audit.models import AuditLog
from app.modules.settings.models import AppSetting
from app.modules.settings.service import SettingsService
from app.modules.suppliers.models import Supplier, SupplierContact

from .client import ShopApiError, shop_client

CURSOR_KEY = "shop_suppliers"
BATCH = 200
ACTIONS = ("supplier.create", "supplier.update", "supplier.delete", "supplier.restore",
           "supplier.contact_add", "supplier.contact_update", "supplier.contact_delete")


def supplier_payload(supplier: Supplier, contact: SupplierContact | None) -> dict[str, Any]:
    """Pure (unit-tested): what the shop gets for one supplier. Archived or inactive → switched off there."""
    return {
        "crm_id": supplier.id,
        "name": supplier.name,
        "is_active": supplier.status == "active" and supplier.deleted_at is None,
        "contact_name": contact.name if contact else None,
        "email": contact.email if contact else None,
        "phone": contact.phone if contact else None,
    }


async def _contact(session: AsyncSession, supplier_id: int) -> SupplierContact | None:
    """The primary contact, else the first one added (deleted contacts don't count)."""
    return (await session.execute(
        select(SupplierContact).where(SupplierContact.supplier_id == supplier_id, SupplierContact.deleted_at.is_(None))
        .order_by(SupplierContact.is_primary.desc(), SupplierContact.id).limit(1))).scalar_one_or_none()


async def _client(session: AsyncSession):
    return shop_client(await SettingsService(session).get_model("shop"))


class ShopSupplierSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _send(self, client, supplier_id: int) -> None:
        supplier = await self.session.get(Supplier, supplier_id)  # archived ones too: they switch off in the shop
        if supplier is not None:
            await client.send_supplier(supplier_payload(supplier, await _contact(self.session, supplier_id)))

    async def run(self) -> str | None:
        if appmode.is_test():
            return None
        try:
            client = await _client(self.session)
        except ShopApiError:
            return None
        cursor = await self.session.get(AppSetting, CURSOR_KEY)
        if cursor is None:  # first run: send everything, which also links the shop's same-named suppliers
            top = (await self.session.execute(select(func.coalesce(func.max(AuditLog.id), 0)))).scalar_one()
            ids = list((await self.session.execute(select(Supplier.id).order_by(Supplier.id))).scalars())
            try:
                for sid in ids:
                    await self._send(client, sid)
            except ShopApiError as exc:
                await self.session.rollback()
                return f"shop suppliers: first sync stopped ({exc}); retrying next run"
            self.session.add(AppSetting(key=CURSOR_KEY, value={"after_id": top}))
            await self.session.commit()
            return f"shop suppliers: {len(ids)} sent (first sync)"
        after = int((cursor.value or {}).get("after_id", 0))
        rows = list((await self.session.execute(
            select(AuditLog).where(AuditLog.id > after, AuditLog.action.in_(ACTIONS)).order_by(AuditLog.id).limit(BATCH))).scalars())
        if not rows:
            return None
        sent, last, done = 0, after, set()
        for row in rows:
            if row.entity_id and row.entity_id not in done:
                try:
                    await self._send(client, int(row.entity_id))
                except ShopApiError as exc:
                    cursor.value = {"after_id": last}
                    await self.session.commit()
                    return f"shop suppliers: stopped at audit {row.id} ({exc}); retrying next run"
                done.add(row.entity_id)
                sent += 1
            last = row.id
        cursor.value = {"after_id": last}
        await self.session.commit()
        return f"shop suppliers: {sent} sent"


async def import_from_shop(session: AsyncSession, actor) -> dict[str, int]:
    """Bring the shop's supplier names into the CRM once: each one the CRM doesn't have (by name, case-insensitive)
    becomes a CRM supplier of the first supplier type, with its contact details. Then all are sent back to link them."""
    from app.modules.lookups.service import LookupService
    from app.modules.suppliers.schemas import SupplierContactIn, SupplierIn
    from app.modules.suppliers.service import SupplierService

    try:
        client = await _client(session)
        shop = (await client.suppliers()).get("items") or []
    except ShopApiError as exc:
        raise ValidationFailedError(f"Can't reach the shop: {exc}") from None
    types = await LookupService(session).values("supplier_type", include_inactive=False)
    if not types:
        raise ValidationFailedError("Add a supplier type first (Settings → Lookups)")
    created = matched = 0
    for item in shop:
        name = " ".join((item.get("name") or "").split())
        if not name:
            continue
        if item.get("crm_id"):
            # Already a copy of a CRM supplier. Its name may be one the CRM changed a moment ago and hasn't sent yet:
            # importing it again would make a duplicate.
            matched += 1
            continue
        exists = (await session.execute(select(Supplier.id).where(
            func.lower(Supplier.name) == name.lower(), Supplier.deleted_at.is_(None)))).first()
        if exists:
            matched += 1
            continue
        contacts = []
        if item.get("contact_name") or item.get("email"):
            contacts.append(SupplierContactIn(name=item.get("contact_name") or name, email=item.get("email") or None,
                                              phone=item.get("phone") or None, is_primary=True))
        await SupplierService(session).create(SupplierIn(
            name=name, supplier_type=types[0].key, status="active" if item.get("is_active", True) else "inactive",
            contacts=contacts), actor)
        created += 1
    # Send everything now so the shop links them at once (the job would within minutes anyway).
    sync = ShopSupplierSync(session)
    linked = 0
    for sid in list((await session.execute(select(Supplier.id).where(Supplier.deleted_at.is_(None)))).scalars()):
        try:
            await sync._send(client, sid)
            linked += 1
        except ShopApiError:
            break
    return {"in_shop": len(shop), "created": created, "already_here": matched, "sent": linked}



async def shop_stats(session: AsyncSession, supplier_id: int) -> dict[str, Any]:
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None or supplier.deleted_at is not None:
        raise NotFoundError("Supplier not found")
    try:
        client = await _client(session)
        return await client.supplier_stats(supplier.name)
    except ShopApiError as exc:
        raise ValidationFailedError(f"Can't reach the shop: {exc}") from None
