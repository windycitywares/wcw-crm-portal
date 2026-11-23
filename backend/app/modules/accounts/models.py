from datetime import date
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import (
    AuthorMixin, Base, CustomFieldsMixin, IdMixin, OwnedMixin, SoftDeleteMixin, TimestampMixin,
)

STATUSES = ("active", "inactive")


class Account(IdMixin, TimestampMixin, AuthorMixin, OwnedMixin, SoftDeleteMixin, CustomFieldsMixin, Base):
    """An organisation: a customer's company, a supplier, a partner, a marketplace."""

    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_accounts_type_status", "account_type", "status"),
    )

    name: Mapped[str] = mapped_column(String(160), index=True)
    account_type: Mapped[str] = mapped_column(String(60), index=True)  # lookup key (kind account_type)
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active", index=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    # The person to talk to first (what the shop shows as a supplier's contact). Contacts point back with account_id.
    primary_contact_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("contacts.id", ondelete="SET NULL", use_alter=True))


class AccountContact(TimestampMixin, Base):
    """A person's link to an organisation, with their role there and when it held. A person can be at several
    accounts; one active link is their main one (it mirrors `contacts.account_id`). A link that ends keeps its
    dates, so when someone changes company the history stays."""

    __tablename__ = "account_contacts"
    __table_args__ = (
        Index("ix_account_contacts_account", "account_id", "ended_on"),
        Index("ix_account_contacts_contact", "contact_id", "ended_on"),
        Index("uq_account_contacts_active", "account_id", "contact_id", unique=True,
              postgresql_where=text("ended_on IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contacts.id", ondelete="CASCADE"))
    role: Mapped[str | None] = mapped_column(String(80))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    started_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)

    # Set (never read) so a link can be made in the same flush as a brand-new contact.
    contact = relationship("Contact", lazy="raise", viewonly=False)
