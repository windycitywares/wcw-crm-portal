"""Urns: the products the business buys from suppliers and sells on Etsy, priced per size.

One Etsy listing is one urn. A urn has a supplier, a supplier price per piece of each size (dated, so a sold order
keeps the price it sold at), and its listing's variations mapped to how many pieces of each size they hold — which
is what its SKU is made of and what an order costs. Extra costs (packaging, a supplier discount…) add or subtract
on top, for one urn or for all of them.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, SoftDeleteMixin, TimestampMixin


class UrnSize(IdMixin, TimestampMixin, Base):
    """A size urns come in (10 inch, 3 inch…). `code` is what the SKU writes; `aliases` are the words that mean
    this size in Etsy variation names ("large", "keepsake")."""

    __tablename__ = "urn_sizes"

    code: Mapped[str] = mapped_column(String(10), unique=True)
    label: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    aliases: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Urn(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """The id is the urn's number in its SKU (never reused). Draft until it has a supplier."""

    __tablename__ = "urns"
    __table_args__ = (
        Index("uq_urns_listing", "listing_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )

    name: Mapped[str] = mapped_column(String(120), index=True)
    supplier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("suppliers.id", ondelete="SET NULL"),
                                                    index=True)
    listing_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("channel_listings.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)


class UrnPrice(IdMixin, AuthorMixin, Base):
    """What the supplier charges for one piece of a size, from a date on. The newest row on or before a sale's date
    is the price that sale used."""

    __tablename__ = "urn_prices"
    __table_args__ = (Index("uq_urn_prices_urn_size_from", "urn_id", "size_code", "effective_from", unique=True),)

    urn_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("urns.id", ondelete="CASCADE"))
    size_code: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    effective_from: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CostExtra(IdMixin, TimestampMixin, AuthorMixin, Base):
    """A cost that adds (packaging, a box) or subtracts (a supplier discount) on top of the supplier price.

    `urn_id` empty = every urn. `mode`: a fixed `amount` or a `percent` of the supplier price. `applies`: once per
    `piece` (of `size_code`, or of any size when empty) or once per `order`. `party`: `supplier` = part of what the
    supplier is owed; `ours` = our own cost, in profit only. Dated like prices."""

    __tablename__ = "cost_extras"

    urn_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("urns.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(10), default="amount", server_default="amount")
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    applies: Mapped[str] = mapped_column(String(10), default="piece", server_default="piece")
    size_code: Mapped[str | None] = mapped_column(String(10))
    party: Mapped[str] = mapped_column(String(10), default="supplier", server_default="supplier")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)


class UrnVariation(IdMixin, TimestampMixin, Base):
    """One variation of a urn's listing and how many pieces of each size it holds. `state`: `proposed` (read from the
    words, waiting for a look), `unclear` (couldn't be read: a person must fill it in), `approved`. `sku` is what
    the CRM would write; `etsy_sku` what Etsy has now."""

    __tablename__ = "urn_variations"
    __table_args__ = (
        Index("uq_urn_variations_urn_key", "urn_id", "key", unique=True),
        Index("ix_urn_variations_sku", "sku"),
    )

    urn_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("urns.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(400))  # options_key(): "" for a listing without variations
    label: Mapped[str] = mapped_column(String(300))
    quantities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    state: Mapped[str] = mapped_column(String(10), default="proposed", server_default="proposed", index=True)
    note: Mapped[str | None] = mapped_column(String(300))
    sku: Mapped[str | None] = mapped_column(String(64))
    etsy_sku: Mapped[str | None] = mapped_column(String(100))
    removed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
