from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from .filing import MAX_BODY, MAX_FILES, MAX_SUBJECT

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
    last_polled_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class MailboxCheck(BaseModel):
    """What the mailbox answered when we tried to open it just now."""

    ok: bool
    detail: str
    folder: str | None = None
    messages: int | None = None
    unseen: int | None = None


# ---- channels that aren't mailboxes (SPEC §3.9) ---------------------------------------------------
# A connector posts one message at a time, signed (docs/INBOX_CHANNELS.md). The limits here are the
# request's own, so a connector is told at the door what a mailbox is told later: `MAX_FILES` files, a
# body no longer than a ticket message, and a whole request small enough to be handled in one breath.
MAX_REQUEST = 24 * 1024 * 1024    # the posted JSON, files and all: base64 room for one 15 MB file
MAX_FILE_CHARS = 21_000_000       # base64 of one file, about 15 MB once decoded (attachments' ceiling)


class InboundFile(BaseModel):
    """A file that came with the message, base64 as it crossed the wire."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=120)
    data: str = Field(min_length=1, max_length=MAX_FILE_CHARS)


class InboundSender(BaseModel):
    """Who wrote in. A chat visitor may be signed in, or somebody the CRM can't name yet.

    A phone is for channels that have no address to give (a text, a live chat). It never creates a
    customer on its own — `CustomerService.find_by_phone` only looks; an address, when present,
    always outranks a number.
    """

    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[\d\s()+.-]+$")
    name: str | None = Field(default=None, max_length=200)


class InboundMessageIn(BaseModel):
    """One message from a channel that isn't a mailbox (docs/INBOX_CHANNELS.md)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=200)      # the channel's own id: a re-post is a duplicate
    channel: str = Field(min_length=1, max_length=60)  # a ticket channel key: live_chat, etsy, ...
    body: str = Field(default="", max_length=MAX_BODY)
    subject: str | None = Field(default=None, max_length=MAX_SUBJECT)
    at: datetime | None = None
    sender: InboundSender = Field(default_factory=InboundSender, alias="from")
    thread: str | None = Field(default=None, max_length=200)  # the id of the message this one answers
    files: list[InboundFile] = Field(default_factory=list, max_length=MAX_FILES)


class IntakeOut(BaseModel):
    """What the CRM did with the message: filed it (on this ticket) or seen it before."""

    status: Literal["filed", "duplicate"]
    ticket_id: int | None = None
    files: int = 0
