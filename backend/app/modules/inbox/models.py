"""The mailboxes the CRM reads (SPEC §3.9, the unified inbox).

A row here is one mailbox and how to log into it. It is not a record with notes, tags or a timeline —
it is configuration, the same kind of thing as the SMTP account in Admin → Settings → Email — so it is
deleted for real rather than archived, and the password is stored encrypted (`imap_password_enc` holds
the Fernet token, never the words).
"""

from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, TimestampMixin

SECURITIES = ("ssl", "starttls", "none")


class EmailAccount(IdMixin, TimestampMixin, AuthorMixin, Base):
    """A mailbox the CRM logs into and reads."""

    __tablename__ = "email_accounts"

    address: Mapped[str] = mapped_column(String(320), unique=True)  # the mailbox itself
    display_name: Mapped[str | None] = mapped_column(String(160))  # "Windy City Wares Support"
    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993, server_default="993")
    imap_security: Mapped[str] = mapped_column(String(10), default="ssl", server_default="ssl")
    imap_user: Mapped[str | None] = mapped_column(String(320))  # NULL = log in as `address`
    imap_password_enc: Mapped[str] = mapped_column(Text)  # encrypted with DATA_ENCRYPTION_KEY
    folder: Mapped[str] = mapped_column(String(120), default="INBOX", server_default="INBOX")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
