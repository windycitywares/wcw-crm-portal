"""Sales channels: the external shops (Etsy now; Amazon, Walmart later) the business sells on.

One `channel_connections` row per marketplace holds the app credentials and the access the owner granted —
every secret sealed with DATA_ENCRYPTION_KEY and never returned by the API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
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
