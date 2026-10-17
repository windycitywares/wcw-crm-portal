"""Queries for campaigns: search the templates, ask the suppression list about an address, read an
audience (a target list and its members), and follow a campaign's recipients through the email outbox."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Select, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.pagination import PageParams
from app.modules.customers.models import Customer
from app.modules.mail.models import FAILED as MAIL_FAILED, SENT as MAIL_SENT, EmailOutbox
from app.shared.repository import BaseRepository

from . import consent, segments
from .models import (
    PENDING, QUEUED, RECIPIENT_FAILED, RECIPIENT_SENT, SCHEDULED, SENDING, Campaign, CampaignRecipient,
    EmailTemplate, Suppression, TargetList, TargetListMember,
)


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
        """How many of those a campaign could actually email (see `consent.conditions()`, SPEC §3.6)."""
        if not list_ids:
            return {}
        stmt = (select(TargetListMember.list_id, func.count())
                .join(Customer, Customer.id == TargetListMember.customer_id)
                .where(TargetListMember.list_id.in_(list(list_ids) or [0]),
                       Customer.deleted_at.is_(None),
                       *consent.conditions())
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


class CampaignRepository(BaseRepository[Campaign]):
    model = Campaign

    def search(self, *, status: str | None = None, q: str | None = None) -> Select[tuple[Campaign]]:
        stmt = self.query()
        if status:
            stmt = stmt.where(Campaign.status == status)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(func.lower(Campaign.name).like(p))
        return stmt.order_by(Campaign.created_at.desc(), Campaign.id.desc())

    async def by_name(self, name: str) -> Campaign | None:
        """Used to refuse two campaigns with the same name — campaigns are picked by name."""
        rows = await self.list(self.query().where(func.lower(Campaign.name) == name.strip().lower())
                               .order_by(Campaign.id).limit(1))
        return rows[0] if rows else None

    async def due(self, now: datetime, *, limit: int = 20) -> list[Campaign]:
        """Scheduled campaigns whose time has come, the oldest first."""
        stmt = (self.query()
                .where(Campaign.status == SCHEDULED, Campaign.scheduled_at.is_not(None),
                       Campaign.scheduled_at <= now)
                .order_by(Campaign.scheduled_at, Campaign.id).limit(limit))
        return list(await self.list(stmt))

    async def sending(self, *, limit: int = 5) -> list[Campaign]:
        """Campaigns part-way through going out, the oldest first (a queue, like the outbox)."""
        stmt = (self.query().where(Campaign.status == SENDING)
                .order_by(Campaign.started_at, Campaign.id).limit(limit))
        return list(await self.list(stmt))

    async def unstarted(self) -> int:
        """How many campaigns are waiting for their time (or for email to be switched on)."""
        return await self.count(self.query().where(Campaign.status.in_((SCHEDULED, SENDING))))


class CampaignRecipientRepository(BaseRepository[CampaignRecipient]):
    model = CampaignRecipient

    def audience(self, *, list_id: int | None = None,
                 rules: dict[str, Any] | None = None) -> Select[tuple[int, str | None]]:
        """The customers an audience holds right now: a static list's members, or a segment's matches.

        This is evaluated once, when a campaign starts, and copied into recipient rows — so what a campaign
        sent is what its audience was at that moment, even for a segment whose rules change later.
        """
        stmt = select(Customer.id, Customer.email)
        if list_id is not None:
            stmt = stmt.join(TargetListMember, TargetListMember.customer_id == Customer.id).where(
                TargetListMember.list_id == list_id)
        else:
            stmt = stmt.where(segments.condition(rules))
        return stmt.where(Customer.deleted_at.is_(None))

    async def audience_size(self, audience: Select[tuple[int, str | None]]) -> int:
        stmt = select(func.count()).select_from(audience.order_by(None).subquery())
        return int((await self.session.execute(stmt)).scalar_one())

    async def snapshot(self, campaign_id: int, audience: Select[tuple[int, str | None]]) -> int:
        """Copy an audience into pending recipient rows. Idempotent: anyone already there is left alone, so a
        second run (or a resumed campaign) adds only what is new."""
        people = audience.order_by(None).subquery()
        stmt = (pg_insert(CampaignRecipient)
                .from_select(
                    ["campaign_id", "customer_id", "email", "status"],
                    select(literal(campaign_id, BigInteger), people.c.id, people.c.email, literal(PENDING)))
                .on_conflict_do_nothing(index_elements=["campaign_id", "customer_id"]))
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)

    def search(self, campaign_id: int, *, status: str | None = None,
               q: str | None = None) -> Select[tuple[CampaignRecipient, Customer]]:
        stmt = (select(CampaignRecipient, Customer)
                .join(Customer, Customer.id == CampaignRecipient.customer_id)
                .where(CampaignRecipient.campaign_id == campaign_id))
        if status:
            stmt = stmt.where(CampaignRecipient.status == status)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(
                func.lower(CampaignRecipient.email).like(p), func.lower(Customer.first_name).like(p),
                func.lower(Customer.last_name).like(p), func.lower(Customer.company).like(p),
            ))
        return stmt.order_by(CampaignRecipient.id)

    async def page(self, campaign_id: int, params: PageParams, *, status: str | None = None,
                   q: str | None = None) -> tuple[list[tuple[CampaignRecipient, Customer]], int]:
        stmt = self.search(campaign_id, status=status, q=q)
        total = await self.count(stmt)
        rows = (await self.session.execute(stmt.limit(params.page_size).offset(params.offset))).all()
        return [(row[0], row[1]) for row in rows], total

    async def pending(self, campaign_id: int,
                      limit: int) -> list[tuple[CampaignRecipient, Customer | None]]:
        """The next recipients still to be looked at, in the order they were copied in. The customer comes
        along (None when the row is gone), so the dispatcher can tell why it would skip someone."""
        stmt = (select(CampaignRecipient, Customer)
                .outerjoin(Customer, Customer.id == CampaignRecipient.customer_id)
                .where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.status == PENDING)
                .order_by(CampaignRecipient.id).limit(limit))
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

    async def counts(self, campaign_ids: Sequence[int]) -> dict[int, dict[str, int]]:
        """Recipients per campaign, by status."""
        if not campaign_ids:
            return {}
        stmt = (select(CampaignRecipient.campaign_id, CampaignRecipient.status, func.count())
                .where(CampaignRecipient.campaign_id.in_(list(campaign_ids)))
                .group_by(CampaignRecipient.campaign_id, CampaignRecipient.status))
        out: dict[int, dict[str, int]] = {}
        for campaign_id, status, n in await self.session.execute(stmt):
            out.setdefault(int(campaign_id), {})[status] = int(n)
        return out

    async def open_counts(self, campaign_ids: Sequence[int]) -> dict[int, int]:
        """How many recipients of each campaign still have to go out (waiting, or in the outbox)."""
        if not campaign_ids:
            return {}
        stmt = (select(CampaignRecipient.campaign_id, func.count())
                .where(CampaignRecipient.campaign_id.in_(list(campaign_ids)),
                       CampaignRecipient.status.in_((PENDING, QUEUED)))
                .group_by(CampaignRecipient.campaign_id))
        return {int(campaign_id): int(n) for campaign_id, n in await self.session.execute(stmt)}

    async def sync_outbox(self, campaign_id: int) -> None:
        """Bring the recipient rows up to date with the outbox: what was sent (and when), and what the mail
        server refused for good. Campaign mail goes out through the outbox, so this is how it learns."""
        await self.session.execute(
            update(CampaignRecipient)
            .where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.status == QUEUED,
                   CampaignRecipient.outbox_id == EmailOutbox.id, EmailOutbox.status == MAIL_SENT)
            .values(status=RECIPIENT_SENT, sent_at=EmailOutbox.sent_at, reason=None))
        await self.session.execute(
            update(CampaignRecipient)
            .where(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.status == QUEUED,
                   CampaignRecipient.outbox_id == EmailOutbox.id, EmailOutbox.status == MAIL_FAILED)
            .values(status=RECIPIENT_FAILED, reason=func.left(EmailOutbox.last_error, 80)))
