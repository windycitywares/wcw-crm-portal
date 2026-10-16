from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Note(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A free-text note on any registered record (customer, ticket, deal …)."""

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_entity", "entity_type", "entity_id"),)

    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    body: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class Activity(IdMixin, Base):
    """One line on a record's timeline: "Note added", "Order #1042 placed", "Status → Resolved".

    Written by any module through `TimelineService.record(...)`; never edited.
    """

    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_entity_at", "entity_type", "entity_id", "at"),)

    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(40))  # e.g. note.added, order.created, ticket.status
    title: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
