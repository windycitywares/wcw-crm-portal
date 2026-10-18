"""Support tickets (SPEC §3.5): conversations with customers, with response-time targets (SLA).

Four tables:
- `sla_policies` — response/resolution targets, counted in *business* minutes (see business_hours.py);
- `canned_responses` — saved answers staff can drop into a reply (Admin → Settings → Canned responses);
- `tickets` — one conversation, linked to a customer (and optionally a shop order), assigned to a person;
- `ticket_messages` — the thread: internal notes, replies emailed to the customer, and the customer's emails in.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, CustomFieldsMixin, IdMixin, SoftDeleteMixin, TimestampMixin

STATUSES = ("new", "open", "pending", "resolved", "closed")
OPEN_STATUSES = ("new", "open", "pending")  # not finished yet
DIRECTIONS = ("internal", "outbound", "inbound")


class SlaPolicy(IdMixin, TimestampMixin, AuthorMixin, Base):
    """A response-time target (SPEC §3.5 / §9), editable in Admin → Settings → SLA policies.

    `first_response_minutes` / `resolve_minutes` are *business* minutes (the Business hours settings
    decide which minutes count). A policy with no `priority`/`ticket_type` is the fallback; the most
    specific match wins (type + priority > type only / priority only > global).
    """

    __tablename__ = "sla_policies"
    __table_args__ = (Index("ix_sla_policies_match", "priority", "ticket_type"),)

    name: Mapped[str] = mapped_column(String(80))
    ticket_type: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind ticket_type); NULL = any
    priority: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind ticket_priority); NULL = any
    first_response_minutes: Mapped[int] = mapped_column(Integer)
    resolve_minutes: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class CannedResponse(IdMixin, TimestampMixin, AuthorMixin, Base):
    """A saved answer (SPEC §3.5) staff can drop into a reply, edited in Admin → Settings → Canned responses.

    Kept as plain text on purpose: a reply is a message body, so there is nothing to template beyond the text.
    """

    __tablename__ = "canned_responses"

    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Ticket(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, CustomFieldsMixin, Base):
    """A support ticket. `number` (e.g. T-000123) is set from the id right after insert, so it's unique
    and human-friendly. `assignee_id` is who is handling it (unlike customers/tasks there's no "own vs
    any" split: `tickets:edit` may change any ticket)."""

    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_priority", "status", "priority"),
        Index("ix_tickets_customer", "customer_id"),
        Index("ix_tickets_assignee_open", "assignee_id",
              postgresql_where=text("deleted_at IS NULL AND status IN ('new','open','pending')")),
        Index("ix_tickets_resolve_due", "resolve_due_at",
              postgresql_where=text("deleted_at IS NULL AND status IN ('new','open','pending')")),
    )

    number: Mapped[str | None] = mapped_column(String(16), unique=True)  # NULL only for the instant before flush
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    ticket_type: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind ticket_type)
    priority: Mapped[str] = mapped_column(String(60), default="normal", server_default="normal")  # lookup key
    channel: Mapped[str] = mapped_column(String(30), default="manual", server_default="manual")  # kind ticket_channel
    status: Mapped[str] = mapped_column(String(10), default="new", server_default="new")

    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="SET NULL"))
    shop_order_id: Mapped[int | None] = mapped_column(BigInteger)  # the shop order it's about (soft link)
    assignee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    sla_policy_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sla_policies.id", ondelete="SET NULL"))
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolve_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_breached: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    resolve_breached: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


class TicketMessage(IdMixin, TimestampMixin, AuthorMixin, Base):
    """One entry in a ticket's conversation. `direction` says what it is:
    `internal` (a staff note), `outbound` (a reply emailed to the customer), `inbound` (the customer's email).

    `external_id` is the email's own `Message-ID` (brackets off), for both directions: it is unique, so a
    re-poll can never store the same message twice, and it is how a customer's answer finds its ticket
    again (their `In-Reply-To`/`References` point back at the id our reply went out with). Notes have none.
    """

    __tablename__ = "ticket_messages"
    __table_args__ = (Index("ix_ticket_messages_ticket", "ticket_id", "id"),)

    ticket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(10), default="internal", server_default="internal")
    body: Mapped[str] = mapped_column(Text)
    from_email: Mapped[str | None] = mapped_column(String(320))
    to_email: Mapped[str | None] = mapped_column(String(320))
    external_id: Mapped[str | None] = mapped_column(String(400), unique=True)
