"""Queries for campaigns: search the templates, ask the suppression list about an address, and read an
audience (a target list and its members)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select

from app.core.pagination import PageParams
from app.modules.customers.models import Customer
from app.shared.repository import BaseRepository

from .models import EmailTemplate, Suppression, TargetList, TargetListMember


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class EmailTemplateRepository(BaseRepository[EmailTemplate]):
    model = EmailTemplate

    def search(self, *, q: str | None = None) -> Select[tuple[EmailTemplate]]:
        stmt = self.query()
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(
                func.lower(EmailTemplate.name).like(p), func.lower(EmailTemplate.subject).like(p),
            ))
        return stmt.order_by(func.lower(EmailTemplate.name), EmailTemplate.id)

    async def by_name(self, name: str) -> EmailTemplate | None:
        """Used to refuse two templates with the same name — a campaign is picked by name."""
        rows = await self.list(self.query().where(func.lower(EmailTemplate.name) == name.strip().lower())
                               .order_by(EmailTemplate.id).limit(1))
        return rows[0] if rows else None


class SuppressionRepository(BaseRepository[Suppression]):
    model = Suppression

    def search(self, *, reason: str | None = None, q: str | None = None) -> Select[tuple[Suppression]]:
        stmt = self.query()
        if reason:
            stmt = stmt.where(Suppression.reason == reason)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(Suppression.email.like(p), func.lower(Suppression.note).like(p)))
        return stmt.order_by(Suppression.created_at.desc(), Suppression.id.desc())

    async def by_email(self, email: str, *, include_deleted: bool = False) -> Suppression | None:
        stmt = (self.query(include_deleted=include_deleted)
                .where(func.lower(Suppression.email) == (email or "").strip().lower())
                .order_by(Suppression.id).limit(1))
        rows = await self.list(stmt)
        return rows[0] if rows else None

    async def suppressed_of(self, emails: list[str]) -> set[str]:
        """Which of these addresses are on the list (lower-cased, for a batch of recipients)."""
        wanted = sorted({(e or "").strip().lower() for e in emails if e})
        if not wanted:
            return set()
        stmt = self.query().where(func.lower(Suppression.email).in_(wanted))
        return {row.email for row in await self.list(stmt)}


class TargetListRepository(BaseRepository[TargetList]):
    model = TargetList

    def search(self, *, kind: str | None = None, q: str | None = None) -> Select[tuple[TargetList]]:
        stmt = self.query()
        if kind:
            stmt = stmt.where(TargetList.kind == kind)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(
                func.lower(TargetList.name).like(p), func.lower(TargetList.description).like(p),
            ))
        return stmt.order_by(func.lower(TargetList.name), TargetList.id)

    async def by_name(self, name: str) -> TargetList | None:
        """Used to refuse two audiences with the same name — a campaign picks one by name."""
        rows = await self.list(self.query().where(func.lower(TargetList.name) == name.strip().lower())
                               .order_by(TargetList.id).limit(1))
        return rows[0] if rows else None


class TargetListMemberRepository(BaseRepository[TargetListMember]):
    model = TargetListMember

    def members(self, list_id: int, *, q: str | None = None) -> Select[tuple[TargetListMember, Customer]]:
        """The members of a list with their customer, in name order (a list is browsed like a directory)."""
        stmt = (select(TargetListMember, Customer)
                .join(Customer, Customer.id == TargetListMember.customer_id)
                .where(TargetListMember.list_id == list_id, Customer.deleted_at.is_(None)))
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(
                func.lower(Customer.first_name).like(p), func.lower(Customer.last_name).like(p),
                func.lower(Customer.company).like(p), func.lower(Customer.email).like(p),
            ))
        return stmt.order_by(func.lower(Customer.first_name), func.lower(Customer.last_name), Customer.id)

    async def page(self, list_id: int, params: PageParams, *,
                   q: str | None = None) -> tuple[list[tuple[TargetListMember, Customer]], int]:
        stmt = self.members(list_id, q=q)
        total = await self.count(stmt)
        rows = (await self.session.execute(stmt.limit(params.page_size).offset(params.offset))).all()
        return [(member, customer) for member, customer in rows], total

    async def counts(self, list_ids: Sequence[int]) -> dict[int, int]:
        """How many live customers are on each list."""
        if not list_ids:
            return {}
        stmt = (select(TargetListMember.list_id, func.count())
                .join(Customer, Customer.id == TargetListMember.customer_id)
                .where(TargetListMember.list_id.in_(list(list_ids) or [0]), Customer.deleted_at.is_(None))
                .group_by(TargetListMember.list_id))
        return {int(row[0]): int(row[1]) for row in await self.session.execute(stmt)}

    async def reachable(self, list_ids: Sequence[int]) -> dict[int, int]:
        """How many of those a campaign could actually email: an address, consent, no unsubscribe and not
        on the suppression list (SPEC §3.6 "consent required")."""
        if not list_ids:
            return {}
        suppressed = (select(Suppression.id)
                      .where(Suppression.deleted_at.is_(None),
                             func.lower(Suppression.email) == func.lower(Customer.email)).exists())
        stmt = (select(TargetListMember.list_id, func.count())
                .join(Customer, Customer.id == TargetListMember.customer_id)
                .where(TargetListMember.list_id.in_(list(list_ids) or [0]),
                       Customer.deleted_at.is_(None),
                       Customer.email.is_not(None),
                       Customer.marketing_consent.is_(True),
                       Customer.unsubscribed_at.is_(None),
                       ~suppressed)
                .group_by(TargetListMember.list_id))
        return {int(row[0]): int(row[1]) for row in await self.session.execute(stmt)}

    async def among(self, list_id: int, customer_ids: Sequence[int]) -> set[int]:
        """Which of these customers are already on the list."""
        if not customer_ids:
            return set()
        stmt = select(TargetListMember.customer_id).where(
            TargetListMember.list_id == list_id, TargetListMember.customer_id.in_(list(customer_ids)))
        return {int(row[0]) for row in await self.session.execute(stmt)}

    async def by_pair(self, list_id: int, customer_id: int) -> TargetListMember | None:
        rows = await self.list(self.query().where(TargetListMember.list_id == list_id,
                                                 TargetListMember.customer_id == customer_id).limit(1))
        return rows[0] if rows else None
