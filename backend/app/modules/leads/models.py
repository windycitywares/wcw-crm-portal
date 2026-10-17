"""Leads (SPEC §3.3, §4.2): someone who might become a customer.

A lead is the top of the sales funnel — a name from a form, a trade show, a referral. It is deliberately
lighter than a customer: a person (or just a company/email/phone), where they came from, who is chasing
them, and free notes. When it is worth pursuing it *converts*: the same call creates the customer (or
links to one that already exists) and, unless asked not to, opens the first deal for them. The lead keeps
the links so the history stays traceable.

`status` is a fixed set, not an admin lookup (the lookups that matter here are `lead_source` and, on the
deal, `lost_reason`): new → contacted → qualified → unqualified, and `converted` is set by the convert
endpoint, never by hand.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, CustomFieldsMixin, IdMixin, OwnedMixin, SoftDeleteMixin, TimestampMixin

# `converted` is reached only through POST /leads/{id}/convert.
STATUSES = ("new", "contacted", "qualified", "unqualified", "converted")


class Lead(IdMixin, TimestampMixin, AuthorMixin, OwnedMixin, SoftDeleteMixin, CustomFieldsMixin, Base):
    """A possible customer (SPEC §3.3). `owner_id` is whoever is working it — the own/any rule uses that.
    `converted_*` are filled when the lead becomes a customer and a deal."""

    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_status", "status"),)

    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    company: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(320))  # lower-case; optional (a phone enquiry has none)
    phone: Mapped[str | None] = mapped_column(String(40))

    source: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind lead_source)
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new")
    notes: Mapped[str | None] = mapped_column(Text)

    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="SET NULL"))
    converted_deal_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="SET NULL"))

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p).strip()

    @property
    def display_name(self) -> str:
        return self.full_name or self.company or self.email or f"Lead #{self.id}"

    @property
    def is_converted(self) -> bool:
        return self.status == "converted"
