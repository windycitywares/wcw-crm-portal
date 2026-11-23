"""People at organisations, the way business CRMs model it: a contact can be linked to several accounts, each link with
a role and dates, and one active link is their main account (mirrored in `contacts.account_id`, which the rest of the
CRM reads). Changing a contact's main account anywhere — the contact form, a supplier's contact list, lead conversion,
a supplier login — ends the old link with today's date instead of overwriting it, so the history follows the person.
That rule lives in one place: a flush hook on contacts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.audit.service import AuditService
from app.modules.contacts.models import Contact

from .models import Account, AccountContact

KEEP_OLD = "accounts.keep_old_link"  # session.info: contact ids whose old main link stays open (a switch, not a move)


def _today() -> date:
    return datetime.now(timezone.utc).date()


@event.listens_for(Session, "before_flush")
def _follow_main_account(session: Session, _ctx, _instances) -> None:
    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, Contact):
            continue
        hist = inspect(obj).attrs.account_id.history
        if obj in session.new:
            old, new = None, obj.account_id
            if new is None:
                continue
        elif hist.has_changes():
            old = hist.deleted[0] if hist.deleted else None
            new = obj.account_id
        else:
            continue
        with session.no_autoflush:
            links = [] if obj.id is None else list(session.execute(select(AccountContact).where(
                AccountContact.contact_id == obj.id, AccountContact.ended_on.is_(None))).scalars())
            keep = obj.id in session.info.get(KEEP_OLD, set())
            session.info.get(KEEP_OLD, set()).discard(obj.id)
            for link in links:
                if link.account_id == old and old != new:
                    link.is_primary = False
                    if not keep:
                        link.ended_on = _today()
                elif link.account_id != new:
                    link.is_primary = False
            if new is not None:
                current = next((l for l in links if l.account_id == new), None)
                if current is None:
                    current = AccountContact(account_id=new, is_primary=True, started_on=_today())
                    if obj.id is None:
                        current.contact = obj
                    else:
                        current.contact_id = obj.id
                    session.add(current)
                current.is_primary = True


async def require_edit(session: AsyncSession, actor, account_id: int) -> None:
    from app.core.exceptions import PermissionDeniedError

    from .service import _can_edit

    if not await _can_edit(session, actor, account_id):
        raise PermissionDeniedError("You can only change accounts you own")


class LinkService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    @staticmethod
    def _out(link: AccountContact, contact: Contact | None, account: Account | None) -> dict[str, Any]:
        return {
            "id": link.id, "account_id": link.account_id, "account_name": account.name if account else None,
            "account_type": account.account_type if account else None, "contact_id": link.contact_id,
            "contact_name": contact.display_name if contact else None, "email": contact.email if contact else None,
            "phone": contact.phone if contact else None, "title": contact.title if contact else None,
            "role": link.role, "is_primary": link.is_primary, "started_on": link.started_on,
            "ended_on": link.ended_on, "active": link.ended_on is None,
        }

    async def _rows(self, *cond) -> list[dict[str, Any]]:
        rows = (await self.session.execute(
            select(AccountContact, Contact, Account)
            .join(Contact, Contact.id == AccountContact.contact_id)
            .join(Account, Account.id == AccountContact.account_id)
            .where(*cond, Contact.deleted_at.is_(None), Account.deleted_at.is_(None))
            .order_by(AccountContact.ended_on.is_not(None), AccountContact.is_primary.desc(),
                      AccountContact.ended_on.desc().nulls_first(), AccountContact.id))).all()
        return [self._out(l, c, a) for l, c, a in rows]

    async def for_account(self, account_id: int, *, include_ended: bool) -> list[dict[str, Any]]:
        cond = [AccountContact.account_id == account_id]
        if not include_ended:
            cond.append(AccountContact.ended_on.is_(None))
        return await self._rows(*cond)

    async def for_contact(self, contact_id: int) -> list[dict[str, Any]]:
        return await self._rows(AccountContact.contact_id == contact_id)

    async def active_counts(self, account_ids: list[int]) -> dict[int, int]:
        if not account_ids:
            return {}
        from sqlalchemy import func

        rows = await self.session.execute(
            select(AccountContact.account_id, func.count()).join(Contact, Contact.id == AccountContact.contact_id)
            .where(AccountContact.account_id.in_(account_ids), AccountContact.ended_on.is_(None),
                   Contact.deleted_at.is_(None)).group_by(AccountContact.account_id))
        return {a: n for a, n in rows.all()}

    async def _link(self, link_id: int) -> AccountContact:
        link = await self.session.get(AccountContact, link_id)
        if link is None:
            raise NotFoundError("Link not found")
        return link

    async def add(self, account_id: int, contact_id: int, *, role: str | None, is_primary: bool,
                  started_on: date | None, actor) -> dict[str, Any]:
        await require_edit(self.session, actor, account_id)
        contact = await self.session.get(Contact, contact_id)
        if contact is None or contact.deleted_at is not None:
            raise ValidationFailedError(f"Contact #{contact_id} doesn't exist")
        existing = (await self.session.execute(select(AccountContact).where(
            AccountContact.account_id == account_id, AccountContact.contact_id == contact_id,
            AccountContact.ended_on.is_(None)))).scalar_one_or_none()
        if existing is not None:
            raise ValidationFailedError(f"{contact.display_name} is already linked to this account")
        has_main = contact.account_id is not None
        link = AccountContact(account_id=account_id, contact_id=contact_id, role=(role or "").strip() or None,
                              started_on=started_on or _today(), is_primary=False)
        self.session.add(link)
        await self.session.flush()
        if is_primary or not has_main:
            self.session.info.setdefault(KEEP_OLD, set()).add(contact.id)
            contact.account_id = account_id
            contact.updated_by = actor.id
        await self.audit.record("account.contact_link", actor=actor, entity_type="account", entity_id=account_id,
                                changes={"contact_id": contact_id, "role": link.role, "primary": is_primary or not has_main})
        await self.session.commit()
        return (await self._rows(AccountContact.id == link.id))[0]

    async def update(self, link_id: int, values: dict[str, Any], actor) -> dict[str, Any]:
        link = await self._link(link_id)
        await require_edit(self.session, actor, link.account_id)
        contact = await self.session.get(Contact, link.contact_id)
        if "role" in values:
            link.role = (values["role"] or "").strip() or None
        if values.get("started_on") is not None:
            link.started_on = values["started_on"]
        if values.get("is_primary") and link.ended_on is None and contact.account_id != link.account_id:
            self.session.info.setdefault(KEEP_OLD, set()).add(contact.id)
            contact.account_id = link.account_id  # the flush hook keeps the other links open, just not main
            contact.updated_by = actor.id
        if values.get("ended_on") is not None and link.ended_on is None:
            await self._end(link, contact, values["ended_on"], actor)
        await self.audit.record("account.contact_link_update", actor=actor, entity_type="account",
                                entity_id=link.account_id, changes={"link_id": link.id, **{
                                    k: str(v) if isinstance(v, date) else v for k, v in values.items()}})
        await self.session.commit()
        return (await self._rows(AccountContact.id == link.id))[0]

    async def _end(self, link: AccountContact, contact: Contact, on: date, actor) -> None:
        if link.started_on and on < link.started_on:
            raise ValidationFailedError("The end date is before the start date")
        link.ended_on, was_main = on, contact.account_id == link.account_id
        link.is_primary = False
        if was_main:  # their main account becomes another current one, if they have one
            other = (await self.session.execute(select(AccountContact).where(
                AccountContact.contact_id == contact.id, AccountContact.ended_on.is_(None),
                AccountContact.id != link.id).order_by(AccountContact.id))).scalars().first()
            self.session.info.setdefault(KEEP_OLD, set()).add(contact.id)
            contact.account_id = other.account_id if other else None
            contact.updated_by = actor.id

    async def end(self, link_id: int, actor) -> None:
        link = await self._link(link_id)
        await require_edit(self.session, actor, link.account_id)
        if link.ended_on is None:
            await self._end(link, await self.session.get(Contact, link.contact_id), _today(), actor)
            await self.audit.record("account.contact_unlink", actor=actor, entity_type="account",
                                    entity_id=link.account_id, changes={"contact_id": link.contact_id})
            await self.session.commit()
