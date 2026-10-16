from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import (
    AuthorMixin, Base, CustomFieldsMixin, IdMixin, OwnedMixin, SoftDeleteMixin, TimestampMixin,
)

STATUSES = ("active", "inactive", "blocked")


class Customer(IdMixin, TimestampMixin, AuthorMixin, OwnedMixin, SoftDeleteMixin, CustomFieldsMixin, Base):
    """A person who buys (or might buy) from Windy City Wares — shop accounts, guest buyers, Etsy buyers,
    people who emailed. One active record per email address."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("uq_customers_email_active", "email", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_customers_last_order_at", "last_order_at"),
    )

    first_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    last_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    company: Mapped[str | None] = mapped_column(String(160))  # B2B later: becomes an Account link
    email: Mapped[str | None] = mapped_column(String(320))  # lower-case; optional (walk-in, phone-only)
    alt_emails: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # line1, line2, city, state, postal_code, country

    customer_type: Mapped[str | None] = mapped_column(String(60), index=True)  # lookup key (kind customer_type)
    source: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind lead_source)
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active", index=True)

    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_source: Mapped[str | None] = mapped_column(String(60))  # e.g. shop checkout, form, import, staff
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Link to the shop (filled by the shop integration, M2 batch 3)
    shop_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    orders_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=text("0"))
    first_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p).strip()

    @property
    def display_name(self) -> str:
        return self.full_name or self.company or self.email or f"Customer #{self.id}"
