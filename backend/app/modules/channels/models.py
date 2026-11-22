"""Sales channels: the external shops (Etsy now; Amazon, Walmart later) the business sells on.

One `channel_connections` row per marketplace holds the app credentials and the access the owner granted —
every secret sealed with DATA_ENCRYPTION_KEY and never returned by the API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TimestampMixin


class ChannelConnection(TimestampMixin, Base):
    __tablename__ = "channel_connections"

    channel: Mapped[str] = mapped_column(String(20), primary_key=True)  # "etsy"
    client_id: Mapped[str | None] = mapped_column(String(100))  # the app's keystring (not secret)
    client_secret_enc: Mapped[str | None] = mapped_column(Text)
    external_shop_id: Mapped[int | None] = mapped_column(BigInteger)
    shop_name: Mapped[str | None] = mapped_column(String(200))
    access_token_enc: Mapped[str | None] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(String(500))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    oauth_state: Mapped[str | None] = mapped_column(String(200))
    oauth_verifier_enc: Mapped[str | None] = mapped_column(Text)
    listings_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orders_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelListing(TimestampMixin, Base):
    """A product as the marketplace lists it. The marketplace owns every column except the team's own three:
    who supplies it (a Supplier account), what it costs us, and notes. A listing the marketplace stops returning
    is marked `removed`, never deleted, so old orders still point at it."""

    __tablename__ = "channel_listings"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_channel_listings_channel_external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[int] = mapped_column(BigInteger)  # Etsy listing_id
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="active", server_default="active", index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    quantity: Mapped[int | None] = mapped_column(Integer)
    skus: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    url: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    variations: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    tags: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # the team's own
    supplier_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class ChannelOrder(TimestampMixin, Base):
    """A marketplace order (an Etsy receipt), created when the marketplace says it is paid. Marketplace columns are
    refreshed on every sync; the team's columns (costs, supplier, tracking, notes, supplier payment) never are.

    Buyer details are kept for fulfilment only: they are never copied into Customers or used for campaigns."""

    __tablename__ = "channel_orders"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_channel_orders_channel_external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[int] = mapped_column(BigInteger)  # Etsy receipt_id
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new", index=True)
    external_state: Mapped[str | None] = mapped_column(String(30))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ship_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyer_name: Mapped[str | None] = mapped_column(String(200))
    external_buyer_id: Mapped[int | None] = mapped_column(BigInteger)
    buyer_email: Mapped[str | None] = mapped_column(String(320))
    buyer_phone: Mapped[str | None] = mapped_column(String(50))
    ship_address: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    gift_message: Mapped[str | None] = mapped_column(Text)
    buyer_note: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    items_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    shipping_charged: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    discounts: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    marketplace_fees: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    marketplace_fees_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # the team's own
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    costs_prefilled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    past_order: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    supplier_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    supplier_order_number: Mapped[str | None] = mapped_column(String(100))
    supplier_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    supplier_paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    supplier_payment_ref: Mapped[str | None] = mapped_column(String(100))
    supplier_paid_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    carrier: Mapped[str | None] = mapped_column(String(60))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    tracking_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tracking_error: Mapped[str | None] = mapped_column(String(300))
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelOrderItem(Base):
    __tablename__ = "channel_order_items"
    __table_args__ = (UniqueConstraint("order_id", "external_id", name="uq_channel_order_items_order_external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channel_orders.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[int] = mapped_column(BigInteger)  # Etsy transaction_id
    listing_external_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(300))
    sku: Mapped[str | None] = mapped_column(String(100))
    variations: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")


class ChannelOrderEvent(Base):
    """An order's history: what changed, who changed it (the team or the marketplace) and when."""

    __tablename__ = "channel_order_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channel_orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(10), default="team", server_default="team")
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    actor_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
