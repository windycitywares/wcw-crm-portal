"""Opt-outs travel back to the shop (shop docs/CRM_SYNC.md → "Opt-outs from the CRM").

The shop → CRM sync only ran one way, so someone who unsubscribed from a CRM campaign, or whom staff unsubscribed,
removed or deleted here, stayed subscribed on the shop, and the shop's own mail (cart reminders, the welcome
offer) kept going to them. This job tells the shop.

It reads the audit log, which every one of those paths already writes and which is append-only and ordered, so no
path has to remember to call anything and nothing is missed if the shop is down: the job keeps its place
(`app_settings["shop_optouts"]`) and starts again from there next run. Changes the shop itself sent (`via: shop`)
are not sent back. Nothing is sent while the CRM is in Test mode: test data must never unsubscribe a real person.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode
from app.modules.audit.models import AuditLog
from app.modules.contacts.models import Contact
from app.modules.customers.models import Customer
from app.modules.settings.models import AppSetting
from app.modules.settings.service import SettingsService

from .client import ShopApiError, shop_client

CURSOR_KEY = "shop_optouts"
BATCH = 100
# Staff actions on a subscriber that take them off the list (contacts/subscribers.py → `_done`).
LEAVING_VIA = {"unsubscribe", "remove"}


ACTIONS = ("suppression.create", "contact.update", "contact.delete", "customer.update")


def opt_out_email(row: AuditLog, contact: Contact | Customer | None) -> str | None:
    """Pure rule (unit-tested): the address an audit row says has left the list, or None. `contact` is the record
    the row is about (a contact, or a customer for customer rows)."""
    changes: dict[str, Any] = row.changes or {}
    if row.action == "suppression.create":
        return (changes.get("email") or "").strip().lower() or None
    if row.action == "customer.update":
        # Staff turning a customer's marketing consent off on the customer screen.
        took_back = changes.get("marketing_consent") in ([True, False], (True, False))
        return contact.email.strip().lower() if took_back and contact is not None and contact.email else None
    if contact is None or not contact.email:
        return None
    if row.action == "contact.update" and changes.get("via") in LEAVING_VIA:
        return contact.email.strip().lower()
    if row.action == "contact.delete" and (contact.subscribed_at is not None or "subscriber" in (contact.types or [])):
        return contact.email.strip().lower()
    return None


class ShopOptOutSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _cursor(self) -> AppSetting:
        row = await self.session.get(AppSetting, CURSOR_KEY)
        if row is None:
            row = AppSetting(key=CURSOR_KEY, value={"after_id": 0})
            self.session.add(row)
            await self.session.flush()
        return row

    async def run(self) -> str | None:
        if appmode.is_test():
            return None
        try:
            client = shop_client(await SettingsService(self.session).get_model("shop"))
        except ShopApiError:
            return None  # the shop's API isn't connected: nothing to tell it with
        cursor = await self._cursor()
        after = int((cursor.value or {}).get("after_id", 0))
        rows = list((await self.session.execute(
            select(AuditLog).where(AuditLog.id > after,
                                   AuditLog.action.in_(ACTIONS))
            .order_by(AuditLog.id).limit(BATCH)
        )).scalars())
        if not rows:
            await self.session.commit()
            return None
        sent, last = 0, after
        for row in rows:
            contact = None
            if row.entity_id and row.entity_type in ("contact", "customer"):
                model = Contact if row.entity_type == "contact" else Customer
                contact = await self.session.get(model, row.entity_id)  # deleted ones too
            email = opt_out_email(row, contact)
            if email:
                try:
                    await client.opt_out(email, row.at)
                except ShopApiError as exc:
                    cursor.value = {"after_id": last}
                    await self.session.commit()
                    return f"shop opt-outs: stopped at audit {row.id} ({exc}); retrying next run"
                sent += 1
            last = row.id
        cursor.value = {"after_id": last}
        await self.session.commit()
        return f"shop opt-outs: {sent} sent ({len(rows)} changes checked)"  # None only once caught up
