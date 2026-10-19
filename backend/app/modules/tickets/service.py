"""Support tickets (SPEC §3.5): conversations with customers, response-time targets and a message thread.

Rules:
- `tickets:view` reads every ticket; `tickets:edit` changes any ticket, notes and replies; `tickets:assign`
  gives a ticket to someone else (otherwise you may only assign it to yourself);
- a ticket about a customer needs read access to that customer; the customer's timeline shows the ticket
  being opened, resolved, closed, reopened and replied to (the ticket keeps its own timeline too);
- a `note` is internal; a `reply` emails the customer (through the outbox) and stamps the first response,
  which is what the SLA first-response target measures;
- `canned_responses` are saved answers staff can drop into a reply, managed only by `lookups:manage`;
- a shop contact-form message opens a ticket for the customer (integration §6, `contact_message.created`):
  it is created by the system, so it lands unassigned;
- a customer's email arriving on a mailbox the CRM reads (SPEC §3.9, the inbox job) joins the thread as
  `inbound` and reopens a ticket that was waiting or finished with; replies of ours go out carrying our own
  `Message-ID` and answer theirs, which is how their answer finds this ticket again;
- SLA due times are counted in business hours (Admin → Settings → Business hours); the `ticket-sla` job
  flags breaches and shows in the queue.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, check_entity_access, entity_labels, register_entity
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.integrations.email import EmailSender, Mail, get_email_sender
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customers.service import CustomerService
from app.modules.customfields.service import CustomFieldService
from app.modules.lookups.service import LookupService
from app.modules.settings.groups import BusinessHours, EmailSettings
from app.modules.settings.service import SettingsService
from app.modules.users.service import UserService
from app.shared.snapshot import snapshot
from app.shared.time import utcnow

from .business_hours import add_business_minutes
from .models import OPEN_STATUSES, CannedResponse, SlaPolicy, Ticket, TicketMessage
from .repository import CannedResponseRepository, SlaPolicyRepository, TicketMessageRepository, TicketRepository
from .schemas import (
    CannedResponseCreate, CannedResponseOut, CannedResponseUpdate, SlaPolicyCreate, SlaPolicyOut, SlaPolicyUpdate,
    TicketCreate, TicketMessageIn, TicketMessageOut, TicketOut, TicketPage, TicketSummary, TicketUpdate,
)

ENTITY = "ticket"
TRACKED = ("subject", "description", "ticket_type", "priority", "channel", "status", "customer_id",
           "shop_order_id", "assignee_id")
LABELS = {"ticket_type": "type", "assignee_id": "assignee", "customer_id": "customer"}

TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"open", "pending", "resolved", "closed"}),
    "open": frozenset({"pending", "resolved", "closed"}),
    "pending": frozenset({"open", "resolved", "closed"}),
    "resolved": frozenset({"open", "closed"}),
    "closed": frozenset({"open"}),
}
STATUS_WORDS = {"resolved": "resolved", "closed": "closed", "open": "reopened", "pending": "put on hold", "new": "reopened"}
STATUS_KINDS = {"resolved": "ticket.resolved", "closed": "ticket.closed", "open": "ticket.reopened"}

# Starter policies (SPEC §9). Minutes are business minutes; 8 hours = one business day.
SLA_SEED: tuple[tuple[str, str, int, int], ...] = (
    ("Urgent", "urgent", 120, 480),   # 2 hours / 1 business day
    ("High", "high", 240, 960),       # 4 hours / 2 business days
    ("Normal", "normal", 480, 1440),  # 1 / 3 business days
    ("Low", "low", 960, 2400),        # 2 / 5 business days
)



async def _exists(session, entity_id: int) -> bool:
    return await TicketRepository(session).get(entity_id) is not None


async def _can_edit(session, user, entity_id: int) -> bool:
    return has_permission(user.role, Permission.TICKETS_EDIT)


async def _labels(session, ids: list[int]) -> dict[int, str]:
    rows = await TicketRepository(session).list(
        TicketRepository(session).query(include_deleted=True).where(Ticket.id.in_(ids)))
    return {t.id: f"{t.number or '#' + str(t.id)} {t.subject}" for t in rows}


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Ticket", view=(Permission.TICKETS_VIEW,), edit=(Permission.TICKETS_EDIT,),
        exists=_exists, can_edit=_can_edit, labels=_labels,
    ))


class TicketService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TicketRepository(session)
        self.messages = TicketMessageRepository(session)
        self.sla = SlaPolicyRepository(session)
        self.canned = CannedResponseRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)
        self.fields = CustomFieldService(session)

    # ---- helpers ------------------------------------------------------------------------
    async def _hours(self) -> BusinessHours:
        return await SettingsService(self.session).get_model("business_hours", factory=BusinessHours)

    async def _policy_for(self, ticket_type: str | None, priority: str | None) -> SlaPolicy | None:
        best: tuple[int, SlaPolicy] | None = None
        for policy in await self.sla.active():
            if policy.priority and policy.priority != priority:
                continue
            if policy.ticket_type and policy.ticket_type != ticket_type:
                continue
            score = (1 if policy.priority else 0) + (1 if policy.ticket_type else 0)
            if best is None or score > best[0]:
                best = (score, policy)
        return best[1] if best else None

    async def _apply_sla(self, ticket: Ticket, anchor: datetime) -> None:
        policy = await self._policy_for(ticket.ticket_type, ticket.priority)
        if policy is None:
            ticket.sla_policy_id = ticket.first_response_due_at = ticket.resolve_due_at = None
            return
        hours = await self._hours()
        ticket.sla_policy_id = policy.id
        ticket.first_response_due_at = add_business_minutes(anchor, policy.first_response_minutes, hours)
        ticket.resolve_due_at = add_business_minutes(anchor, policy.resolve_minutes, hours)
        ticket.first_response_breached = ticket.resolve_breached = False

    async def _out(self, tickets: list[Ticket]) -> list[TicketOut]:
        customer_ids = [t.customer_id for t in tickets if t.customer_id]
        names = await entity_labels(self.session, "customer", customer_ids) if customer_ids else {}
        people = {u.id: u.full_name for u in await UserService(self.session).directory()}
        now = utcnow()
        out = []
        for t in tickets:
            item = TicketOut.model_validate(t)
            item.customer_name = names.get(t.customer_id) if t.customer_id else None
            item.assignee_name = people.get(t.assignee_id) if t.assignee_id else None
            item.is_overdue = t.status in OPEN_STATUSES and t.resolve_due_at is not None and t.resolve_due_at < now
            out.append(item)
        return out

    async def _get(self, ticket_id: int) -> Ticket:
        ticket = await self.repo.get(ticket_id)
        if ticket is None:
            raise NotFoundError("Ticket not found")
        return ticket

    def _check_assignee(self, user, assignee_id: int | None) -> None:
        if assignee_id is not None and assignee_id != user.id and not has_permission(user.role, Permission.TICKETS_ASSIGN):
            raise PermissionDeniedError("Only managers and support can assign tickets to someone else")

    async def _record(self, ticket: Ticket, kind: str, title: str, actor, *, customer_title: str | None = None) -> None:
        await self.timeline.record(ENTITY, ticket.id, kind, title, actor=actor)
        if ticket.customer_id:
            await self.timeline.record("customer", ticket.customer_id, kind, customer_title or title, actor=actor,
                                       data={"ticket_id": ticket.id})

    # ---- reads --------------------------------------------------------------------------
    async def list(self, user, params: PageParams, *, view: str = "all", state: str = "unresolved",
                   status: str | None = None, priority: str | None = None, ticket_type: str | None = None,
                   channel: str | None = None, customer_id: int | None = None, breached: bool | None = None,
                   needs_reply: bool | None = None, q: str | None = None) -> TicketPage:
        filters: dict[str, Any] = {"state": state, "status": status, "priority": priority,
                                   "ticket_type": ticket_type, "channel": channel, "customer_id": customer_id,
                                   "breached": breached, "needs_reply": needs_reply, "q": q}
        if view == "mine":
            filters["assignee_id"] = user.id
        elif view == "unassigned":
            filters["unassigned"] = True
        rows, total = await self.repo.paginate(self.repo.search(**filters), params)
        return TicketPage(items=await self._out(list(rows)), total=total, page=params.page, page_size=params.page_size)

    async def get(self, ticket_id: int) -> TicketOut:
        return (await self._out([await self._get(ticket_id)]))[0]

    async def summary(self, user) -> TicketSummary:
        now = utcnow()
        open_states = (Ticket.status.in_(OPEN_STATUSES),)
        return TicketSummary(
            open=await self.repo.count_where(*open_states),
            unassigned=await self.repo.count_where(*open_states, Ticket.assignee_id.is_(None)),
            overdue=await self.repo.count_where(*open_states, Ticket.resolve_due_at < now),
            mine=await self.repo.count_where(*open_states, Ticket.assignee_id == user.id),
        )

    async def messages_for(self, ticket_id: int) -> list[TicketMessageOut]:
        await self._get(ticket_id)
        people = {u.id: u.full_name for u in await UserService(self.session).directory()}
        out = []
        for m in await self.messages.for_ticket_list(ticket_id):
            item = TicketMessageOut.model_validate(m)
            item.author_name = people.get(m.created_by) if m.created_by else None
            out.append(item)
        return out

    # ---- writes -------------------------------------------------------------------------
    async def create(self, data: TicketCreate, actor=None, *, commit: bool = True,
                     opened_at: datetime | None = None) -> TicketOut:
        """Open a ticket. `actor` is the staff user, or None for a system ticket (the shop webhook, the
        inbox job), which skips the permission checks and lands unassigned. Shop callers pass `commit=False`,
        so the ticket is committed together with the rest of the shop event; the inbox passes `opened_at`
        when it knows the mail arrived earlier than this (a poll after a quiet night), which is also what
        its response-time targets are counted from."""
        values = data.model_dump(exclude_unset=True)
        if not values.get("subject"):
            raise ValidationFailedError("A ticket needs a subject")
        if actor is not None:
            if values.get("customer_id") is not None:
                await check_entity_access(self.session, actor, "customer", values["customer_id"], write=False)
            if "assignee_id" not in values:
                values["assignee_id"] = actor.id
            self._check_assignee(actor, values.get("assignee_id"))
        values["priority"] = await self.lookups.require("ticket_priority", values.get("priority") or "normal")
        if values.get("ticket_type"):
            values["ticket_type"] = await self.lookups.require("ticket_type", values["ticket_type"])
        # Who opened it and how: a system caller (the shop webhook, the inbox job) says which channel its
        # message arrived on; anything typed in here is `manual` unless the caller says otherwise.
        values["channel"] = await self.lookups.require("ticket_channel", values.get("channel") or "manual")
        if values.get("custom_fields") is not None:
            values["custom_fields"] = await self.fields.validate(ENTITY, values["custom_fields"] or {})
        who = actor.id if actor is not None else None
        ticket = Ticket(**{k: v for k, v in values.items() if v is not None}, created_by=who, updated_by=who)
        if opened_at is not None:  # the mail's own time, not the moment we got round to reading it
            ticket.created_at = ticket.updated_at = opened_at
        await self.repo.add(ticket)
        ticket.number = f"T-{ticket.id:06d}"
        await self._apply_sla(ticket, ticket.created_at or utcnow())
        await self.session.flush()
        await self.audit.record("ticket.create", actor=actor, entity_type=ENTITY, entity_id=ticket.id,
                                changes=diff({}, snapshot(ticket, TRACKED)))
        await self._record(ticket, "ticket.created", f"Ticket {ticket.number} opened", actor,
                           customer_title=f"Ticket {ticket.number} opened: {ticket.subject}")
        if commit:
            await self.session.commit()
        return await self.get(ticket.id)

    async def update(self, ticket_id: int, data: TicketUpdate, actor) -> TicketOut:
        ticket = await self._get(ticket_id)
        values = data.model_dump(exclude_unset=True)
        if "subject" in values and not values["subject"]:
            raise ValidationFailedError("A ticket needs a subject")
        if "assignee_id" in values:
            self._check_assignee(actor, values["assignee_id"])
        if values.get("customer_id") is not None and values["customer_id"] != ticket.customer_id:
            await check_entity_access(self.session, actor, "customer", values["customer_id"], write=False)
        if "priority" in values:
            values["priority"] = await self.lookups.require(
                "ticket_priority", values["priority"] or ticket.priority, allow_inactive_key=ticket.priority)
        if "ticket_type" in values:
            values["ticket_type"] = await self.lookups.require(
                "ticket_type", values["ticket_type"], allow_inactive_key=ticket.ticket_type)
        if "channel" in values:
            values["channel"] = await self.lookups.require(
                "ticket_channel", values["channel"] or ticket.channel, allow_inactive_key=ticket.channel)
        if values.get("custom_fields") is not None:
            values["custom_fields"] = await self.fields.validate(ENTITY, values["custom_fields"], existing=ticket.custom_fields)
        new_status = values.pop("status", None)
        resla = any(k in values for k in ("priority", "ticket_type"))
        before = snapshot(ticket, TRACKED)
        self.repo.apply(ticket, values)
        if resla:
            await self._apply_sla(ticket, ticket.created_at or utcnow())
        if new_status is not None and new_status != ticket.status:
            await self._set_status(ticket, new_status, actor)
        ticket.updated_by = actor.id
        await self.session.flush()
        changes = diff(before, snapshot(ticket, TRACKED))
        if changes:
            await self.audit.record("ticket.update", actor=actor, entity_type=ENTITY, entity_id=ticket.id, changes=changes)
        await self.session.commit()
        return await self.get(ticket.id)

    async def _set_status(self, ticket: Ticket, status: str, actor) -> None:
        if status == ticket.status:
            return
        if status not in TRANSITIONS.get(ticket.status, frozenset()):
            raise ValidationFailedError(f"A {ticket.status} ticket can't be marked {status}")
        ticket.status = status
        if status == "resolved":
            ticket.resolved_at = ticket.resolved_at or utcnow()
        elif status == "closed":
            ticket.resolved_at = ticket.resolved_at or utcnow()
            ticket.closed_at = utcnow()
        elif status == "open":
            ticket.resolved_at = ticket.closed_at = None
        kind = STATUS_KINDS.get(status, "ticket.status")
        await self._record(ticket, kind, f"Ticket {ticket.number} {STATUS_WORDS[status]}", actor)

    async def add_message(self, ticket_id: int, data: TicketMessageIn, actor, sender: EmailSender | None = None) -> TicketMessageOut:
        ticket = await self._get(ticket_id)
        email: str | None = None
        if data.kind == "reply":
            if ticket.customer_id is None:
                raise ValidationFailedError("Link a customer before emailing a reply")
            customer = await CustomerService(self.session).get(ticket.customer_id)
            email = customer.email
            if not email:
                raise ValidationFailedError("This customer has no email address")
        direction = "outbound" if data.kind == "reply" else "internal"
        message = await self.messages.add(TicketMessage(
            ticket_id=ticket.id, direction=direction, body=data.body, to_email=email,
            created_by=actor.id, updated_by=actor.id,
        ))
        if data.kind == "reply":
            message.external_id = await self._reply_id(ticket, message)
            headers = {"Message-ID": f"<{message.external_id}>"}
            answered = await self.messages.last_inbound_id(ticket.id)
            if answered:
                # Answer the customer's last message, so their reply comes back to this ticket.
                headers["In-Reply-To"] = headers["References"] = f"<{answered}>"
            await (sender or get_email_sender(self.session)).send(Mail(
                to=email or "", subject=f"Re: [{ticket.number}] {ticket.subject}", text=data.body,
                headers=headers))
            if ticket.first_responded_at is None:
                ticket.first_responded_at = utcnow()
        if ticket.status == "new":
            await self._set_status(ticket, "open", actor)
        ticket.updated_by = actor.id
        kind = "ticket.reply" if data.kind == "reply" else "ticket.note"
        title = "Replied to the customer" if data.kind == "reply" else "Internal note added"
        await self._record(ticket, kind, f"{title} on {ticket.number} ({ticket.subject})", actor)
        await self.audit.record("ticket.message", actor=actor, entity_type=ENTITY, entity_id=ticket.id,
                                changes={"kind": data.kind})
        await self.session.commit()
        item = TicketMessageOut.model_validate(message)
        item.author_name = getattr(actor, "full_name", None)
        return item

    async def _reply_id(self, ticket: Ticket, message: TicketMessage) -> str:
        """Our own `Message-ID` for a reply, built from the ticket and the message so that a retry keeps
        the same one — a second attempt must not look like a second message in the customer's mail client."""
        settings: EmailSettings = await SettingsService(self.session).get_model("email", factory=EmailSettings)
        domain = str(settings.from_address).split("@")[-1] or "windycitywares.com"
        return f"{ticket.number or ticket.id}.{message.id}@{domain}"

    # ---- the inbox (SPEC §3.9) ----------------------------------------------------------
    async def thread_for(self, external_ids: Sequence[str]) -> int | None:
        """Which ticket a message belongs to, when we have seen one of these `Message-ID`s before: the
        `In-Reply-To`/`References` chain of a customer's answer, or the message's own id (it is already
        stored, so it must not be stored twice)."""
        return await self.messages.ticket_for_ids(list(external_ids))

    async def ticket_by_number(self, number: str) -> int | None:
        ticket = await self.repo.by_number(number)
        return ticket.id if ticket else None

    async def add_inbound(self, ticket_id: int, *, body: str, external_id: str, from_email: str | None = None,
                          to_email: str | None = None, from_phone: str | None = None, when: datetime | None = None,
                          opened: bool = False) -> int:
        """A customer's own message arriving on a mailbox the CRM reads, or on a channel that isn't one
        (the inbox job and its intake). It joins the thread as `inbound` and reopens a ticket that was
        waiting or finished with. No actor: the system brought it in, so it lands as "System" like a shop
        event.

        `opened=True` is the message the ticket was opened by: the ticket is already new and nobody has
        picked it up, so there is nothing to reopen, and the message simply becomes the first thing said.
        Storing it is what makes the ticket *waiting on us* (`TicketRepository.NEWEST_DIRECTION`) and gives
        our reply something to answer (`last_inbound_id`), so the customer's next message finds its way back.

        It deliberately leaves the SLA clock alone: `first_response_due_at` measures how fast *we* answered
        this ticket, and a customer writing again does not erase that. The resolve target still applies, so
        a reopened ticket nobody picks up goes overdue as usual. The caller commits.
        """
        ticket = await self._get(ticket_id)
        if ticket.status != "open" and not opened:
            await self._set_status(ticket, "open", None)
        values: dict[str, Any] = {"ticket_id": ticket.id, "direction": "inbound", "body": body,
                                  "from_email": from_email, "to_email": to_email, "from_phone": from_phone,
                                  "external_id": external_id}
        if when is not None:  # the mail's own time, so a poll after a quiet weekend reads honestly
            values["created_at"] = values["updated_at"] = when
        message = await self.messages.add(TicketMessage(**values))
        ticket.updated_by = None
        await self._record(ticket, "ticket.inbound",
                           f"Customer wrote in on {ticket.number} ({ticket.subject})", None)
        await self.audit.record("ticket.inbound", entity_type=ENTITY, entity_id=ticket.id,
                                changes={"from": from_email, "from_phone": from_phone, "external_id": external_id})
        await self.session.flush()
        return message.id

    async def delete(self, ticket_id: int, actor) -> None:
        ticket = await self._get(ticket_id)
        await self.repo.soft_delete(ticket)
        await self.audit.record("ticket.delete", actor=actor, entity_type=ENTITY, entity_id=ticket.id,
                                changes={"number": ticket.number})
        await self._record(ticket, "ticket.deleted", f"Ticket {ticket.number} deleted", actor)
        await self.session.commit()

    # ---- SLA policies (Admin → Settings → SLA policies) ---------------------------------
    async def list_sla(self) -> list[SlaPolicyOut]:
        return [SlaPolicyOut.model_validate(p) for p in await self.sla.list(self.sla.ordered())]

    async def _get_sla(self, policy_id: int) -> SlaPolicy:
        policy = await self.sla.get(policy_id)
        if policy is None:
            raise NotFoundError("SLA policy not found")
        return policy

    async def create_sla(self, data: SlaPolicyCreate, actor) -> SlaPolicyOut:
        values = data.model_dump()
        values["ticket_type"] = await self.lookups.require("ticket_type", values.get("ticket_type"))
        values["priority"] = await self.lookups.require("ticket_priority", values.get("priority"))
        policy = await self.sla.add(SlaPolicy(**values, created_by=actor.id, updated_by=actor.id))
        await self.audit.record("sla_policy.create", actor=actor, entity_type="sla_policy", entity_id=policy.id,
                                changes=diff({}, values))
        await self.session.commit()
        return SlaPolicyOut.model_validate(policy)

    async def update_sla(self, policy_id: int, data: SlaPolicyUpdate, actor) -> SlaPolicyOut:
        policy = await self._get_sla(policy_id)
        changes = data.model_dump(exclude_unset=True)
        if "ticket_type" in changes:
            changes["ticket_type"] = await self.lookups.require("ticket_type", changes["ticket_type"],
                                                                allow_inactive_key=policy.ticket_type)
        if "priority" in changes:
            changes["priority"] = await self.lookups.require("ticket_priority", changes["priority"],
                                                             allow_inactive_key=policy.priority)
        before = {"name": policy.name, "ticket_type": policy.ticket_type, "priority": policy.priority,
                  "first_response_minutes": policy.first_response_minutes, "resolve_minutes": policy.resolve_minutes,
                  "is_active": policy.is_active}
        self.sla.apply(policy, changes)
        policy.updated_by = actor.id
        await self.audit.record("sla_policy.update", actor=actor, entity_type="sla_policy", entity_id=policy.id,
                                changes=diff(before, {**before, **changes}))
        await self.session.commit()
        await self.session.refresh(policy)  # `updated_at` is written by the database; read it back, don't lazy-load
        return SlaPolicyOut.model_validate(policy)

    # ---- canned responses (Admin → Settings → Canned responses) -------------------------
    async def list_canned(self) -> list[CannedResponseOut]:
        return [CannedResponseOut.model_validate(r) for r in await self.canned.list_all()]

    async def _get_canned(self, response_id: int) -> CannedResponse:
        row = await self.canned.get(response_id)
        if row is None:
            raise NotFoundError("Canned response not found")
        return row

    async def create_canned(self, data: CannedResponseCreate, actor) -> CannedResponseOut:
        values = data.model_dump()
        if not values.get("title"):
            raise ValidationFailedError("A canned response needs a title")
        if not values.get("body"):
            raise ValidationFailedError("A canned response needs a body")
        row = await self.canned.add(CannedResponse(**values, created_by=actor.id, updated_by=actor.id))
        await self.audit.record("canned_response.create", actor=actor, entity_type="canned_response", entity_id=row.id,
                                changes=diff({}, values))
        await self.session.commit()
        return CannedResponseOut.model_validate(row)

    async def update_canned(self, response_id: int, data: CannedResponseUpdate, actor) -> CannedResponseOut:
        row = await self._get_canned(response_id)
        changes = data.model_dump(exclude_unset=True)
        if "title" in changes and not changes["title"]:
            raise ValidationFailedError("A canned response needs a title")
        if "body" in changes and not changes["body"]:
            raise ValidationFailedError("A canned response needs a body")
        before = {"title": row.title, "body": row.body, "is_active": row.is_active}
        self.canned.apply(row, changes)
        row.updated_by = actor.id
        await self.audit.record("canned_response.update", actor=actor, entity_type="canned_response", entity_id=row.id,
                                changes=diff(before, {**before, **changes}))
        await self.session.commit()
        await self.session.refresh(row)  # `updated_at` is written by the database; read it back, don't lazy-load
        return CannedResponseOut.model_validate(row)

    async def delete_canned(self, response_id: int, actor) -> None:
        row = await self._get_canned(response_id)
        await self.audit.record("canned_response.delete", actor=actor, entity_type="canned_response", entity_id=row.id,
                                changes={"title": row.title})
        await self.canned.hard_delete(row)
        await self.session.commit()

    # ---- jobs ---------------------------------------------------------------------------
    async def check_sla(self) -> str | None:
        """`ticket-sla` job: flag first-response and resolve targets that have been missed."""
        now = utcnow()
        first = resolve = 0
        for ticket in await self.repo.unresolved_with_due():
            if ticket.first_response_due_at and ticket.first_responded_at is None \
                    and not ticket.first_response_breached and ticket.first_response_due_at < now:
                ticket.first_response_breached, first = True, first + 1
                await self.audit.record("ticket.sla_breach", entity_type=ENTITY, entity_id=ticket.id,
                                        changes={"first_response": "missed"})
            if ticket.resolve_due_at and not ticket.resolve_breached and ticket.resolve_due_at < now:
                ticket.resolve_breached, resolve = True, resolve + 1
                await self.audit.record("ticket.sla_breach", entity_type=ENTITY, entity_id=ticket.id,
                                        changes={"resolve": "missed"})
        if not (first or resolve):
            return None
        await self.session.commit()
        return f"SLA breaches flagged: {first} first response, {resolve} resolve"
