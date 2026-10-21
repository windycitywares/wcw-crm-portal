"""Contacts: every person the business deals with.

A contact is the one place a person lives. Staff users and customers are contacts too: the `users` and
`customers` tables stay the systems of record for sign-in and orders, and the contact links to them
(`user_id`, `customer_id`). One person can be both — one row, two types.

`types` holds lookup keys from the `contact_type` list (user, customer, vendor, lead, partner, other), so an
admin can rename or add types without a code change. A contact with `user_id` always carries "user"; one with
`customer_id` always carries "customer" (the services keep that true).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, OwnedMixin, SoftDeleteMixin, TimestampMixin

STATUSES = ("active", "inactive", "blocked")


class Contact(IdMixin, TimestampMixin, AuthorMixin, OwnedMixin, SoftDeleteMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        Index("uq_contacts_email_active", "email", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_contacts_types", "types", postgresql_using="gin"),
        Index("uq_contacts_user_id", "user_id", unique=True, postgresql_where=text("user_id IS NOT NULL")),
        Index("uq_contacts_customer_id", "customer_id", unique=True,
              postgresql_where=text("customer_id IS NOT NULL")),
    )

    first_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    last_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    company: Mapped[str | None] = mapped_column(String(160))
    title: Mapped[str | None] = mapped_column(String(120))  # job title
    email: Mapped[str | None] = mapped_column(String(320))  # lower-case; optional (phone-only contact)
    alt_emails: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    types: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active", index=True)
    # Where we met them: manual, shop, import, user, customer.
    source: Mapped[str] = mapped_column(String(40), default="manual", server_default="manual")

    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="SET NULL"))

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p).strip()

    @property
    def display_name(self) -> str:
        return self.full_name or self.company or self.email or f"Contact #{self.id}"
