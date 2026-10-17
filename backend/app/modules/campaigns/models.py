"""Campaigns (SPEC §3.6): the email templates campaigns are written from, the audiences they go to, and the
suppression list that keeps the CRM out of inboxes that asked it to stop.

- `email_templates` — subject, preheader, HTML and text bodies, with merge fields rendered through a
  sandboxed Jinja2 environment. `version` goes up on every save; the audit log keeps what changed.
- `target_lists` + `target_list_members` — *who* a campaign goes to. A static list holds its members in the
  member table (put on by hand); a segment is the same row with `kind="segment"` and `rules` (a small rule
  set, see `segments.py`) and no member rows, so it is evaluated fresh every time.
- `suppressions` — addresses that must never be emailed again, and why (unsubscribed, bounced,
  complained, or added by hand). Soft-deleted rather than dropped, so re-adding an address restores its
  row and the history of why it was there.
- `campaigns` + `campaign_recipients` — one send: a template, an audience and a time. When a campaign
  starts, the audience is copied into recipient rows (a segment is evaluated then, once) and every
  recipient is followed through the email outbox: queued, sent, skipped with a reason, or failed.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, SoftDeleteMixin, TimestampMixin

# Why an address may not be emailed any more (SPEC §3.6 "suppression list").
REASONS = ("unsubscribed", "bounced", "complained", "manual")

# The life of a campaign (SPEC §3.6): written, waiting for its time, going out, held, done.
DRAFT, SCHEDULED, SENDING, PAUSED, SENT = "draft", "scheduled", "sending", "paused", "sent"
CAMPAIGN_STATUSES = (DRAFT, SCHEDULED, SENDING, PAUSED, SENT)

# Where one recipient is: waiting to be looked at, in the outbox, sent, given up on, or skipped.
PENDING, QUEUED, RECIPIENT_SENT, RECIPIENT_FAILED, SKIPPED = "pending", "queued", "sent", "failed", "skipped"
RECIPIENT_STATUSES = (PENDING, QUEUED, RECIPIENT_SENT, RECIPIENT_FAILED, SKIPPED)

# What kind of audience a list is: a static list holds its members in a table, a segment holds the rules
# that pick them (see segments.py).
KINDS = ("static", "segment")


class EmailTemplate(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A campaign email as it is written: one subject, one HTML body, one text body, merge fields."""

    __tablename__ = "email_templates"

    name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(300))
    preheader: Mapped[str | None] = mapped_column(String(300))  # the grey line next to the subject
    html: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)  # always filled: derived from the HTML when it is left empty
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=sql_text("1"))


class Suppression(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """An address campaigns must skip: it unsubscribed, bounced, complained, or staff added it."""

    __tablename__ = "suppressions"
    __table_args__ = (
        Index("uq_suppressions_email_active", "email", unique=True,
              postgresql_where=sql_text("deleted_at IS NULL")),
    )

    email: Mapped[str] = mapped_column(String(320))  # lower-case
    reason: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    source: Mapped[str | None] = mapped_column(String(60))  # where it came from: campaign, shop, staff…
    note: Mapped[str | None] = mapped_column(String(300))  # what happened, in a human's words


class TargetList(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """An audience: the customers a campaign goes to. A static list holds its members in a table; a segment
    holds the rules that pick them."""

    __tablename__ = "target_lists"

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(10), default="static", server_default="static")
    # A segment's rules (see segments.py); NULL for a static list, which keeps its members in the table below.
    rules: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class TargetListMember(IdMixin, TimestampMixin, Base):
    """One customer on one list. Removing a customer from the CRM (GDPR erase) takes the membership with it,
    and the row remembers who put them on the list."""

    __tablename__ = "target_list_members"
    __table_args__ = (
        UniqueConstraint("list_id", "customer_id", name="uq_target_list_members_list_customer"),
        Index("ix_target_list_members_customer", "customer_id"),
    )

    list_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("target_lists.id", ondelete="CASCADE"))
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="CASCADE"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))


class Campaign(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """One send: the template it is written from, the audience it goes to, and when (SPEC §3.6).

    The two foreign keys are RESTRICT: a campaign is a record of something that was sent, so a template or
    an audience it used is soft-deleted (the rows stay, hidden from the pickers) rather than dropped.
    """

    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_status_scheduled", "status", "scheduled_at"),)

    name: Mapped[str] = mapped_column(String(120))
    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("email_templates.id", ondelete="RESTRICT"))
    target_list_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("target_lists.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(10), default=DRAFT, server_default=DRAFT)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # when it should go out
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # when its audience was copied
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # when nothing was left to send


class CampaignRecipient(IdMixin, TimestampMixin, Base):
    """One customer in one campaign.

    The audience is copied in when the campaign starts — a segment is evaluated at that moment, once, so what
    went out is what was true then. Each row then follows its message through the outbox (`outbox_id`), which
    is what the per-campaign report (next batch) counts.
    """

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "customer_id", name="uq_campaign_recipients_campaign_customer"),
        Index("ix_campaign_recipients_campaign_status", "campaign_id", "status"),
        Index("ix_campaign_recipients_customer", "customer_id"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("campaigns.id", ondelete="CASCADE"))
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320))  # the address it went to (the customer may change theirs)
    status: Mapped[str] = mapped_column(String(10), default=PENDING, server_default=PENDING)
    reason: Mapped[str | None] = mapped_column(String(80))  # why it was skipped, or why sending gave up
    outbox_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("email_outbox.id", ondelete="SET NULL"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

