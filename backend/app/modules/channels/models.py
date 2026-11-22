"""Sales channels: the external shops (Etsy now; Amazon, Walmart later) the business sells on.

One `channel_connections` row per marketplace holds the app credentials and the access the owner granted —
every secret sealed with DATA_ENCRYPTION_KEY and never returned by the API.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
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
