from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, HttpUrl

Status = Literal["active", "inactive"]


def _required(value: str) -> str:
    text = " ".join((value or "").split())
    if not text:
        raise ValueError("must not be empty")
    return text


def _words(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return text or None


Name = Annotated[str, Field(max_length=160), AfterValidator(_required)]
Key = Annotated[str, Field(min_length=1, max_length=60), AfterValidator(_required)]


class AccountAddress(BaseModel):
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=100)


class AccountIn(BaseModel):
    name: Name
    account_type: Key
    status: Status = "active"
    industry: Annotated[str | None, Field(default=None, max_length=120), AfterValidator(_words)] = None
    website: HttpUrl | None = None
    email: EmailStr | None = None
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_words)] = None
    address: AccountAddress | None = None
    notes: Annotated[str | None, Field(default=None, max_length=5000)] = None
    owner_id: int | None = None
    custom_fields: dict[str, Any] | None = None


class AccountUpdate(BaseModel):
    name: Name | None = None
    account_type: Key | None = None
    status: Status | None = None
    industry: Annotated[str | None, Field(default=None, max_length=120), AfterValidator(_words)] = None
    website: HttpUrl | None = None
    email: EmailStr | None = None
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_words)] = None
    address: AccountAddress | None = None
    notes: Annotated[str | None, Field(default=None, max_length=5000)] = None
    owner_id: int | None = None
    custom_fields: dict[str, Any] | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    account_type: str
    status: str
    industry: str | None
    website: str | None
    email: str | None
    phone: str | None
    address: dict[str, Any] | None
    notes: str | None
    owner_id: int | None
    primary_contact_id: int | None = None
    custom_fields: dict[str, Any]
    contacts_count: int = 0
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class AccountPage(BaseModel):
    items: list[AccountOut]
    total: int
    page: int
    page_size: int


class AccountOption(BaseModel):
    """A short row for pickers (supplier select, contact's account)."""

    id: int
    name: str
    account_type: str
