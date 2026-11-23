from datetime import date, datetime
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
    parent_id: int | None = None
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
    parent_id: int | None = None
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
    parent_id: int | None = None
    parent_name: str | None = None
    children_count: int = 0
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


class AccountLinkIn(BaseModel):
    contact_id: int
    role: str | None = Field(default=None, max_length=80)
    is_primary: bool = False
    started_on: date | None = None


class AccountLinkUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=80)
    is_primary: bool | None = None
    started_on: date | None = None
    ended_on: date | None = None


class AccountLinkOut(BaseModel):
    """A person at an organisation: who, their role there, and when it held. `is_primary` = their main account."""

    id: int
    account_id: int
    account_name: str | None
    account_type: str | None
    contact_id: int
    contact_name: str | None
    email: str | None
    phone: str | None
    title: str | None
    role: str | None
    is_primary: bool
    started_on: date | None
    ended_on: date | None
    active: bool


class AccountTreeNode(BaseModel):
    id: int
    name: str
    account_type: str
    status: str
    depth: int  # 0 = the group's top account
    parent_id: int | None
    contacts_count: int
    open_deals: int
    open_value: float


class AccountGroup(BaseModel):
    """An account with the organisations above it and every account under it, with a roll-up of the whole group."""

    ancestors: list[AccountOption]  # top first
    tree: list[AccountTreeNode]     # this account and everything under it, depth-first
    accounts: int
    people: int
    open_deals: int
    open_value: float
