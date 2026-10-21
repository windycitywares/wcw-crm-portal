"""App mode (live/test) table — one row, id = 1."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class AppMode(Base):

    __tablename__ = "app_mode"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text("1"))
    mode: Mapped[str] = mapped_column(String(8), nullable=False, server_default=text("'live'"))
    test_mail_to: Mapped[str | None] = mapped_column(String(320))
    test_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    test_login_emails: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    changed_by_email: Mapped[str | None] = mapped_column(String(320))
