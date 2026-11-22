from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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
