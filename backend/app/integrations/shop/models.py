from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, IdMixin

PENDING, DONE, FAILED, IGNORED = "pending", "done", "failed", "ignored"


class ShopEvent(IdMixin, Base):
    """Every webhook the shop sends, stored once (by its event id) before it is applied."""

    __tablename__ = "shop_events"
    __table_args__ = (Index("ix_shop_events_status_id", "status", "id"),)

    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), default=PENDING, server_default=PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    customer_id: Mapped[int | None] = mapped_column(BigInteger)  # the customer it touched, for the admin list
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShopOrder(Base):
    """A copy of each shop order's headline numbers, so customer totals can be recomputed exactly
    whatever order the events arrive in. The full order stays in the shop (read API, batch 5)."""

    __tablename__ = "shop_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # the shop's order id
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    number: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(20))
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", server_default="unpaid")
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=sql_text("0"))
    refunded_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=sql_text("0"))
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shop_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ignore older events
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
