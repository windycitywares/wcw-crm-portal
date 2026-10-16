from typing import Any

from sqlalchemy import Boolean, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, TimestampMixin


class CustomFieldDef(IdMixin, TimestampMixin, AuthorMixin, Base):
    """An extra field admins add to a record type. Values live in that record's `custom_fields` JSONB
    under `key`. The type can't change after creation (stored values must stay valid); deactivate instead."""

    __tablename__ = "custom_field_defs"
    __table_args__ = (UniqueConstraint("entity_type", "key", name="uq_custom_field_defs_entity_type_key"),)

    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(20))
    options: Mapped[list[Any] | None] = mapped_column(JSONB)  # for select / multiselect
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    help_text: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
