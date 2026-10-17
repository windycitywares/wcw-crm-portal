"""Campaigns (SPEC §3.6): the email templates campaigns are written from, and the suppression list that
keeps the CRM out of inboxes that asked it to stop.

Two tables so far (campaigns themselves, lists and segments come in the next batches):

- `email_templates` — subject, preheader, HTML and text bodies, with merge fields rendered through a
  sandboxed Jinja2 environment. `version` goes up on every save; the audit log keeps what changed.
- `suppressions` — addresses that must never be emailed again, and why (unsubscribed, bounced,
  complained, or added by hand). Soft-deleted rather than dropped, so re-adding an address restores its
  row and the history of why it was there.
"""

from sqlalchemy import Index, Integer, String, Text, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, SoftDeleteMixin, TimestampMixin

# Why an address may not be emailed any more (SPEC §3.6 "suppression list").
REASONS = ("unsubscribed", "bounced", "complained", "manual")


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
