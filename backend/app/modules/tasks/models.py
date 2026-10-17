from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, OwnedMixin, SoftDeleteMixin, TimestampMixin

STATUSES = ("open", "done", "cancelled")
PRIORITIES = ("low", "normal", "high")
RECURRENCES = ("daily", "weekly", "monthly")


class Task(IdMixin, TimestampMixin, AuthorMixin, OwnedMixin, SoftDeleteMixin, Base):
    """A to-do for someone on the team (SPEC §3.4). `owner_id` is the person it's assigned to.
    It can be about any registered record (customer, ticket, deal …) through (related_type, related_id)."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_open_due", "status", "due_at"),
        Index("ix_tasks_related", "related_type", "related_id"),
        Index("ix_tasks_reminder_due", "reminder_at", postgresql_where=text("reminded_at IS NULL AND status = 'open'")),
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind task_type)
    priority: Mapped[str] = mapped_column(String(10), default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(10), default="open", server_default="open")

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_has_time: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))  # else: all day
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recurrence: Mapped[str | None] = mapped_column(String(10))  # daily | weekly | monthly: next one made on completion

    related_type: Mapped[str | None] = mapped_column(String(40))
    related_id: Mapped[int | None] = mapped_column(BigInteger)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
