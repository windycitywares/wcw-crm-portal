"""Contact request/response shapes.

`types` is the multi-select of contact types (lookup keys). A contact needs at least one; the service
validates the keys against the `contact_type` list.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

Status = Literal["active", "inactive", "blocked"]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


Text80 = Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)]
Text = Annotated[str | None, Field(default=None, max_length=200), AfterValidator(_strip)]


class Address(BaseModel):
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=60)


class ContactBase(BaseModel):
    first_name: Text80 = None
    last_name: Text80 = None
    company: Annotated[str | None, Field(default=None, max_length=160), AfterValidator(_strip)] = None
    title: Annotated[str | None, Field(default=None, max_length=120), AfterValidator(_strip)] = None
    email: EmailStr | None = None
    alt_emails: list[EmailStr] | None = Field(default=None, max_length=10)
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_strip)] = None
    address: Address | None = None
    types: list[str] | None = Field(default=None, max_length=10)
    notes: Text = None
    status: Status | None = None
    owner_id: int | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(ContactBase):
    pass


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    full_name: str
    display_name: str
    company: str | None
    title: str | None
    email: str | None
    alt_emails: list[str]
    phone: str | None
    address: dict[str, Any] | None
    types: list[str]
    notes: str | None
    status: Status
    source: str
    owner_id: int | None
    user_id: int | None
    customer_id: int | None
    subscribed_at: datetime | None = None
    unsubscribed_at: datetime | None = None
    subscribe_source: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    deleted_at: datetime | None


class ContactPage(BaseModel):
    items: list[ContactOut]
    total: int
    page: int
    page_size: int
