"""The people on a deal and the part each plays (the buying committee): decision maker, signer, champion…

A deal already has one customer and one account; this adds every person involved, each with a role from the
`deal_role` type list (Settings → Types). Changing who is on a deal takes the deal's own edit right.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService
from app.modules.contacts.models import Contact
from app.modules.lookups.service import LookupService

from .models import Deal, DealContact
from .repository import DealRepository

KIND = "deal_role"


def _may_change(user, deal: Deal) -> bool:
    from .service import _may_change as rule  # one rule for the deal and everything on it

    return rule(user, deal)


class DealRoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)

    async def _deal(self, deal_id: int) -> Deal:
        deal = await DealRepository(self.session).get(deal_id)
        if deal is None:
            raise NotFoundError("Deal not found")
        return deal

    async def _deal_to_change(self, deal_id: int, actor) -> Deal:
        deal = await self._deal(deal_id)
        if not _may_change(actor, deal):
            raise PermissionDeniedError("You can only change the people on your own deals")
        return deal

    async def _row(self, deal_id: int, link_id: int) -> DealContact:
        row = await self.session.get(DealContact, link_id)
        if row is None or row.deal_id != deal_id:
            raise NotFoundError("That person isn't on this deal")
        return row

    async def _role(self, key: str | None, current: str | None = None) -> str | None:
        if not key:
            return None
        return await self.lookups.require(KIND, key, allow_inactive_key=current)

    async def _rows(self, *cond) -> list[dict[str, Any]]:
        rows = (await self.session.execute(
            select(DealContact, Contact, Deal).join(Contact, Contact.id == DealContact.contact_id)
            .join(Deal, Deal.id == DealContact.deal_id)
            .where(*cond, Contact.deleted_at.is_(None), Deal.deleted_at.is_(None))
            .order_by(DealContact.is_primary.desc(), DealContact.id))).all()
        return [{
            "id": r.id, "deal_id": r.deal_id, "deal_title": d.title, "deal_status": d.status,
            "contact_id": r.contact_id, "contact_name": c.display_name, "email": c.email, "phone": c.phone,
            "title": c.title, "account_id": c.account_id, "role": r.role, "is_primary": r.is_primary,
            "notes": r.notes,
        } for r, c, d in rows]

    async def for_deal(self, deal_id: int) -> list[dict[str, Any]]:
        await self._deal(deal_id)
        return await self._rows(DealContact.deal_id == deal_id)

    async def for_contact(self, contact_id: int) -> list[dict[str, Any]]:
        return await self._rows(DealContact.contact_id == contact_id)

    async def _only_primary(self, deal_id: int, keep: int) -> None:
        await self.session.execute(update(DealContact).where(DealContact.deal_id == deal_id, DealContact.id != keep)
                                   .values(is_primary=False))

    async def add(self, deal_id: int, values: dict[str, Any], actor) -> dict[str, Any]:
        deal = await self._deal_to_change(deal_id, actor)
        contact = await self.session.get(Contact, values["contact_id"])
        if contact is None or contact.deleted_at is not None:
            raise ValidationFailedError(f"Contact #{values['contact_id']} doesn't exist")
        if (await self.session.execute(select(DealContact.id).where(
                DealContact.deal_id == deal.id, DealContact.contact_id == contact.id))).first():
            raise ValidationFailedError(f"{contact.display_name} is already on this deal")
        row = DealContact(deal_id=deal.id, contact_id=contact.id, role=await self._role(values.get("role")),
                          is_primary=bool(values.get("is_primary")), notes=(values.get("notes") or "").strip() or None,
                          created_by=actor.id, updated_by=actor.id)
        self.session.add(row)
        await self.session.flush()
        if row.is_primary:
            await self._only_primary(deal.id, row.id)
        role = await self._label(row.role)
        await self.timeline.record("deal", deal.id, "deal.contact_added",
                                   f"{contact.display_name} added{f' as {role}' if role else ''}", actor=actor)
        await self.audit.record("deal_contact.create", actor=actor, entity_type="deal", entity_id=deal.id,
                                changes={"contact_id": contact.id, "role": row.role, "primary": row.is_primary})
        await self.session.commit()
        return (await self._rows(DealContact.id == row.id))[0]

    async def update(self, deal_id: int, link_id: int, values: dict[str, Any], actor) -> dict[str, Any]:
        deal = await self._deal_to_change(deal_id, actor)
        row = await self._row(deal.id, link_id)
        before = {"role": row.role, "primary": row.is_primary, "notes": row.notes}
        if "role" in values:
            row.role = await self._role(values["role"], row.role)
        if "notes" in values:
            row.notes = (values["notes"] or "").strip() or None
        if values.get("is_primary") is not None:
            row.is_primary = bool(values["is_primary"])
            if row.is_primary:
                await self._only_primary(deal.id, row.id)
        row.updated_by = actor.id
        after = {"role": row.role, "primary": row.is_primary, "notes": row.notes}
        changes = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
        if changes:
            await self.audit.record("deal_contact.update", actor=actor, entity_type="deal", entity_id=deal.id,
                                    changes={"contact_id": row.contact_id, **changes})
        await self.session.commit()
        return (await self._rows(DealContact.id == row.id))[0]

    async def remove(self, deal_id: int, link_id: int, actor) -> None:
        deal = await self._deal_to_change(deal_id, actor)
        row = await self._row(deal.id, link_id)
        contact = await self.session.get(Contact, row.contact_id)
        await self.session.delete(row)
        await self.timeline.record("deal", deal.id, "deal.contact_removed",
                                   f"{contact.display_name if contact else 'A contact'} taken off the deal", actor=actor)
        await self.audit.record("deal_contact.delete", actor=actor, entity_type="deal", entity_id=deal.id,
                                changes={"contact_id": row.contact_id, "role": row.role})
        await self.session.commit()

    async def _label(self, key: str | None) -> str | None:
        if not key:
            return None
        for v in await self.lookups.values(KIND):
            if v.key == key:
                return v.label
        return key
