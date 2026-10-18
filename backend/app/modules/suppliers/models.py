from typing import Any
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, CustomFieldsMixin, IdMixin, SoftDeleteMixin, TimestampMixin

STATUSES = ("active", "inactive")


class Supplier(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, CustomFieldsMixin, Base):
    """A business Windy City Wares buys products or services from."""

    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating_range"),
        Index("ix_suppliers_type_status", "supplier_type", "status"),
    )

    name: Mapped[str] = mapped_column(String(160), index=True)
    supplier_type: Mapped[str] = mapped_column(String(60), index=True)  # lookup key (kind supplier_type)
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active", index=True)
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    website: Mapped[str | None] = mapped_column(String(500))
    payment_terms: Mapped[str | None] = mapped_column(String(300))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    rating: Mapped[int | None] = mapped_column(Integer)


class SupplierContact(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A person at a supplier, kept separately so a supplier can have several contacts."""

    __tablename__ = "supplier_contacts"
    __table_args__ = (
        Index("ix_supplier_contacts_supplier_id", "supplier_id"),
        Index("uq_supplier_contacts_primary", "supplier_id", unique=True,
              postgresql_where=text("is_primary IS TRUE AND deleted_at IS NULL")),
    )

    supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("suppliers.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class SupplierProduct(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A product a supplier offers, matched to the shop's SKU without requiring catalog access."""

    __tablename__ = "supplier_products"
    __table_args__ = (
        CheckConstraint("unit_cost >= 0", name="unit_cost_nonnegative"),
        CheckConstraint("minimum_order_quantity IS NULL OR minimum_order_quantity > 0", name="moq_positive"),
        CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="lead_time_nonnegative"),
        Index("ix_supplier_products_supplier_id", "supplier_id"),
        Index("ix_supplier_products_supplier_shop_sku", "supplier_id", "shop_sku"),
        Index("uq_supplier_products_supplier_sku", "supplier_id", "supplier_sku", unique=True,
              postgresql_where=text("supplier_sku IS NOT NULL AND deleted_at IS NULL")),
    )

    supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("suppliers.id", ondelete="CASCADE"))
    shop_sku: Mapped[str] = mapped_column(String(80))
    supplier_sku: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(300))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    minimum_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)