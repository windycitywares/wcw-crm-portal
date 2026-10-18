from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import OPEN_STATUSES, CannedResponse, SlaPolicy, Ticket, TicketMessage


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Who has the ball on a ticket: the direction of the newest message (null if nobody has said anything —
# a ticket typed in by staff, or one the shop opened from its contact form). See `search(needs_reply=…)`.
NEWEST_DIRECTION = (select(TicketMessage.direction).where(TicketMessage.ticket_id == Ticket.id)
                    .order_by(TicketMessage.id.desc()).limit(1).scalar_subquery())
# When we are the ones being waited on, how long the wait has been (message ids are handed out in time
# order, so the newest inbound id is also the most recent thing the customer said).
NEWEST_INBOUND = (select(func.max(TicketMessage.id))
                  .where(TicketMessage.ticket_id == Ticket.id, TicketMessage.direction == "inbound")
                  .scalar_subquery())


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    def search(self, *, q: str | None = None, state: str = "unresolved", status: str | None = None,
               priority: str | None = None, ticket_type: str | None = None, channel: str | None = None,
               assignee_id: int | None = None, unassigned: bool = False, customer_id: int | None = None,
               breached: bool | None = None, needs_reply: bool | None = None) -> Select[tuple[Ticket]]:
        """The queue. `needs_reply` is the inbox's own question — is the customer's message the last thing
        said, nobody having replied since? (True: yes; False: we answered or nobody has spoken; None: don't
        ask.) It is asked of the newest message, so a reply of ours settles it and a later email re-opens it."""
        stmt = self.query()
        if state == "unresolved":
            stmt = stmt.where(Ticket.status.in_(OPEN_STATUSES))
        elif state == "resolved":
            stmt = stmt.where(Ticket.status.in_(("resolved", "closed")))
        if status:
            stmt = stmt.where(Ticket.status == status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if ticket_type:
            stmt = stmt.where(Ticket.ticket_type == ticket_type)
        if channel:
            stmt = stmt.where(Ticket.channel == channel)
        if assignee_id is not None:
            stmt = stmt.where(Ticket.assignee_id == assignee_id)
        if unassigned:
            stmt = stmt.where(Ticket.assignee_id.is_(None))
        if customer_id is not None:
            stmt = stmt.where(Ticket.customer_id == customer_id)
        if breached is not None:
            cond = or_(Ticket.resolve_breached.is_(True), Ticket.first_response_breached.is_(True))
            stmt = stmt.where(cond if breached else ~cond)
        if needs_reply is not None:
            waiting = func.coalesce(NEWEST_DIRECTION, "") == "inbound"
            stmt = stmt.where(waiting if needs_reply else ~waiting)
        if q:
            words = [w for w in q.strip().lower().split() if w][:5]
            for word in words:
                p = f"%{escape_like(word)}%"
                stmt = stmt.where(or_(
                    func.lower(Ticket.subject).like(p),
                    func.lower(Ticket.description).like(p),
                    func.lower(Ticket.number).like(p),
                ))
        if needs_reply:
            # "Waiting on us" is a question about the wait, so it is answered in wait order: whatever has
            # been sitting unanswered longest comes first.
            return stmt.order_by(NEWEST_INBOUND.asc(), Ticket.id.asc())
        if state == "resolved":
            return stmt.order_by(func.coalesce(Ticket.closed_at, Ticket.resolved_at, Ticket.updated_at).desc(), Ticket.id.desc())
        # open work: soonest deadline first, undated last, then oldest first
        return stmt.order_by(Ticket.resolve_due_at.asc().nullslast(), Ticket.id.asc())

    async def count_where(self, *conditions) -> int:
        stmt = select(func.count()).select_from(Ticket).where(Ticket.deleted_at.is_(None), *conditions)
        return int((await self.session.execute(stmt)).scalar_one())

    async def unresolved_with_due(self, limit: int = 500) -> list[Ticket]:
        stmt = (self.query()
                .where(Ticket.status.in_(OPEN_STATUSES))
                .where(or_(Ticket.first_response_due_at.is_not(None), Ticket.resolve_due_at.is_not(None)))
                .limit(limit))
        return list((await self.session.execute(stmt)).scalars())

    async def by_number(self, number: str) -> Ticket | None:
        """A ticket by its `T-000123` number (a customer's subject line says which ticket they mean)."""
        return (await self.session.execute(self.query().where(Ticket.number == number))).scalars().first()


class TicketMessageRepository(BaseRepository[TicketMessage]):
    model = TicketMessage

    def for_ticket(self, ticket_id: int) -> Select[tuple[TicketMessage]]:
        return self.query().where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.id.asc())

    async def for_ticket_list(self, ticket_id: int) -> list[TicketMessage]:
        return list((await self.session.execute(self.for_ticket(ticket_id))).scalars())

    async def ticket_for_ids(self, external_ids: Sequence[str]) -> int | None:
        """The newest ticket one of these `Message-ID`s belongs to — our threading and our dedupe."""
        ids = [i for i in external_ids if i]
        if not ids:
            return None
        stmt = (select(TicketMessage.ticket_id).where(TicketMessage.external_id.in_(ids))
                .order_by(TicketMessage.id.desc()).limit(1))
        return (await self.session.execute(stmt)).scalars().first()

    async def last_inbound_id(self, ticket_id: int) -> str | None:
        """The id of the customer's last message, which a reply of ours should answer."""
        stmt = (select(TicketMessage.external_id)
                .where(TicketMessage.ticket_id == ticket_id, TicketMessage.direction == "inbound",
                       TicketMessage.external_id.is_not(None))
                .order_by(TicketMessage.id.desc()).limit(1))
        return (await self.session.execute(stmt)).scalars().first()


class SlaPolicyRepository(BaseRepository[SlaPolicy]):
    model = SlaPolicy

    def ordered(self) -> Select[tuple[SlaPolicy]]:
        return self.query().order_by(SlaPolicy.id.asc())

    async def active(self) -> list[SlaPolicy]:
        return list((await self.session.execute(self.query().where(SlaPolicy.is_active.is_(True)))).scalars())


class CannedResponseRepository(BaseRepository[CannedResponse]):
    model = CannedResponse

    def ordered(self) -> Select[tuple[CannedResponse]]:
        return self.query().order_by(CannedResponse.title.asc(), CannedResponse.id.asc())

    async def list_all(self) -> list[CannedResponse]:
        return list((await self.session.execute(self.ordered())).scalars())
