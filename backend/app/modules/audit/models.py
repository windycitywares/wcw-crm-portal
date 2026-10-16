from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, IdMixin


class AuditLog(IdMixin, Base):
    """Append-only record of who changed what. Never updated or deleted by the app."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(320))  # kept even if the user is deleted
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. user.create, auth.login_failed
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # {"field": [before, after]} or details
    ip: Mapped[str | None] = mapped_column(String(64))
