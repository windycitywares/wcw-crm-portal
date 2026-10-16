"""Declarative base and the mixins every business table uses (SPEC §4).

    class Customer(Base, IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, OwnedMixin, CustomFieldsMixin):
        __tablename__ = "customers"

Mixins keep each concern in one place (single responsibility) and let generic code
(BaseRepository, audit, timeline) work on any model that has them.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Stable constraint names, so Alembic autogenerate produces predictable migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {dict[str, Any]: JSONB}


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuthorMixin:
    """Who created / last changed the row. Set by services from the current user."""

    @declared_attr
    def created_by(cls) -> Mapped[int | None]:
        return mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    @declared_attr
    def updated_by(cls) -> Mapped[int | None]:
        return mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))


class OwnedMixin:
    """Record owner, for the "own vs any" permission rule."""

    @declared_attr
    def owner_id(cls) -> Mapped[int | None]:
        return mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class CustomFieldsMixin:
    """Admin-defined extra fields (SPEC §3.1) — never add a column for a one-off field."""

    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
