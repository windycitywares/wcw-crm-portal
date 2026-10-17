"""Request and response bodies for campaigns (SPEC §3.6).

A name or subject is trimmed and refused when it is blank; the bodies are trimmed at the ends but keep their
inner whitespace, because that whitespace is the email.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

Reason = Literal["unsubscribed", "bounced", "complained", "manual"]


def _words(v: str | None) -> str | None:
    """One line of words: whitespace squeezed, blank becomes None (a field the caller may leave out)."""
    v = " ".join((v or "").split())
    return v or None


def _required_words(v: str) -> str:
    v = " ".join((v or "").split())
    if not v:
        raise ValueError("must not be empty")
    return v


def _required_text(v: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError("must not be empty")
    return v


def _trim(v: str | None) -> str | None:
    return (v or "").strip() or None


Name = Annotated[str, Field(max_length=120), AfterValidator(_required_words)]
Subject = Annotated[str, Field(max_length=300), AfterValidator(_required_words)]
Preheader = Annotated[str | None, Field(default=None, max_length=300), AfterValidator(_words)]
Html = Annotated[str, Field(max_length=200_000), AfterValidator(_required_text)]
Body = Annotated[str | None, Field(default=None, max_length=200_000), AfterValidator(_trim)]
Note = Annotated[str | None, Field(default=None, max_length=300), AfterValidator(_words)]


class TemplateIn(BaseModel):
    """A campaign email as it is written. Merge fields are checked when it is saved.

    An empty `text` body is filled in from the HTML (`render.plain_text`), so every email has a text part.
    """

    name: Name
    subject: Subject
    preheader: Preheader = None
    html: Html
    text: Body = None


class TemplateUpdate(BaseModel):
    """PATCH. A field left out is not changed; an emptied `preheader` clears it, and an emptied `text` body
    is derived from the HTML again — so is any HTML edit that arrives without a text body."""

    name: Name | None = None
    subject: Subject | None = None
    preheader: Preheader = None
    html: Html | None = None
    text: Body = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str
    preheader: str | None
    html: str
    text: str
    version: int
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class TemplateSummary(BaseModel):
    """A row in the template list: everything but the bodies, which can be large."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str
    preheader: str | None
    version: int
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class TemplatePage(BaseModel):
    items: list[TemplateSummary]
    total: int
    page: int
    page_size: int


class MergeField(BaseModel):
    """One merge field the editor offers: `{{ customer.first_name }}`."""

    name: str
    description: str


class RenderedEmail(BaseModel):
    """Exactly what an inbox would get, footer and all."""

    subject: str
    preheader: str | None
    html: str
    text: str


class TestIn(BaseModel):
    """Send the rendered email — for one customer, or for the sample when none is chosen — to an address
    of your choosing (SPEC §3.6 "test send")."""

    to: EmailStr
    customer_id: int | None = None


class TestSent(BaseModel):
    """A test send is queued in the outbox (202): it goes now when email is on, otherwise with the job."""

    to: str
    subject: str


class SuppressionIn(BaseModel):
    """Stop emailing an address, with a reason."""

    email: EmailStr
    reason: Reason = "manual"
    note: Note = None


class SuppressionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    reason: str
    source: str | None
    note: str | None
    created_at: datetime


class SuppressionPage(BaseModel):
    items: list[SuppressionOut]
    total: int
    page: int
    page_size: int
