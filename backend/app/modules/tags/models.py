from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, TimestampMixin


class Tag(IdMixin, TimestampMixin, AuthorMixin, Base):
    """A free-form label shared by every record type ("Christmas buyer", "Needs follow-up")."""

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(60), unique=True)  # lower-cased, for uniqueness/search
    color: Mapped[str | None] = mapped_column(String(20))


class Tagging(Base):
    """Tag ↔ record link. `entity_type` is a key from app.core.entities."""

    __tablename__ = "taggings"
    __table_args__ = (Index("ix_taggings_entity", "entity_type", "entity_id"),)

    tag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
