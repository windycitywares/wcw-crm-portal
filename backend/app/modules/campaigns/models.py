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
"""

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, SoftDeleteMixin, TimestampMixin

# Why an address may not be emailed any more (SPEC §3.6 "suppression list").
REASONS = ("unsubscribed", "bounced", "complained", "manual")

# What kind of audience a list is. `segment` (rules, re-evaluated at send time) lands in the next batch.
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
    """An audience: the customers a campaign goes to. Static lists hold their members in a table; a segment
    (next batch) holds the rules that pick them."""

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

