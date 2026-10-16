from sqlalchemy import Boolean, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, TimestampMixin


class LookupValue(IdMixin, TimestampMixin, AuthorMixin, Base):
    """One value in an admin-editable type list, e.g. kind="customer_type", key="vip", label="VIP".

    Records store the `key`, so renaming the label never breaks them. Values are deactivated, not deleted.
    """

    __tablename__ = "lookup_values"
    __table_args__ = (UniqueConstraint("kind", "key", name="uq_lookup_values_kind_key"),)

    kind: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    color: Mapped[str | None] = mapped_column(String(20))  # a token name (e.g. "success") or #rrggbb
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
