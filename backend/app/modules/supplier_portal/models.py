from typing import Any

from sqlalchemy import BigInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TimestampMixin


class SupplierLogin(TimestampMixin, Base):
    """Which supplier a "supplier" user signs in for, and which sales channels they may see."""

    __tablename__ = "supplier_logins"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    channels: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
