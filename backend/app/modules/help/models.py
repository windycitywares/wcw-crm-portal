from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, IdMixin, TimestampMixin


class HelpFeedback(IdMixin, TimestampMixin, Base):
    """One person's answer to "Was this helpful?" on one guide."""

    __tablename__ = "help_feedback"
    __table_args__ = (Index("ix_help_feedback_topic", "topic_id", "created_at"),)

    topic_id: Mapped[str] = mapped_column(String(60))  # the guide's id in the web app, e.g. "etsy-orders"
    page: Mapped[str] = mapped_column(String(200))  # the address the person was on
    helpful: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
