from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, IdMixin

QUEUED, SENT, FAILED = "queued", "sent", "failed"


class EmailOutbox(IdMixin, Base):
    """Every email the CRM sends goes through here: queued, then sent (now if possible, else by the job)."""

    __tablename__ = "email_outbox"
    __table_args__ = (Index("ix_email_outbox_due", "status", "send_after"),)

    to_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    html: Mapped[str | None] = mapped_column(Text)
    reply_to: Mapped[str | None] = mapped_column(String(320))
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    category: Mapped[str] = mapped_column(String(20), default="system", server_default="system")  # system | campaign
    status: Mapped[str] = mapped_column(String(10), default=QUEUED, server_default=QUEUED, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    send_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
