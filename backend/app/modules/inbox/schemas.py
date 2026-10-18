from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

Security = Literal["ssl", "starttls", "none"]


def _required_words(value: str) -> str:
    text = " ".join((value or "").split())
    if not text:
        raise ValueError("must not be empty")
    return text


def _words(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return text or None


Host = Annotated[str, Field(min_length=1, max_length=255), AfterValidator(_required_words)]
User = Annotated[str | None, Field(default=None, max_length=320), AfterValidator(_words)]
Folder = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_required_words)]
DisplayName = Annotated[str | None, Field(default=None, max_length=160), AfterValidator(_words)]
Password = Annotated[str, Field(min_length=1, max_length=500)]


class EmailAccountIn(BaseModel):
    address: EmailStr
    display_name: DisplayName = None
    imap_host: Host
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_security: Security = "ssl"
    imap_user: User = None
    imap_password: Password
    folder: Folder = "INBOX"
    is_active: bool = True


class EmailAccountUpdate(BaseModel):
    address: EmailStr | None = None
    display_name: DisplayName = None
    imap_host: Host | None = None
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_security: Security | None = None
    imap_user: User = None
    imap_password: Annotated[str | None, Field(default=None, max_length=500)] = None  # empty = keep the stored one
    folder: Folder | None = None
    is_active: bool | None = None


class EmailAccountOut(BaseModel):
    """The password is not here, and never will be: the API says which mailbox, not its secret."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    address: str
    display_name: str | None
    imap_host: str
    imap_port: int
    imap_security: str
    imap_user: str | None
    folder: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MailboxCheck(BaseModel):
    """What the mailbox answered when we tried to open it just now."""

    ok: bool
    detail: str
    folder: str | None = None
    messages: int | None = None
    unseen: int | None = None
