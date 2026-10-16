from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

Status = Literal["active", "inactive", "blocked"]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


Text80 = Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)]


class Address(BaseModel):
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=60)


class TagRef(BaseModel):
    id: int
    name: str
    color: str | None


class CustomerBase(BaseModel):
    first_name: Text80 = None
    last_name: Text80 = None
    company: Annotated[str | None, Field(default=None, max_length=160), AfterValidator(_strip)] = None
    email: EmailStr | None = None
    alt_emails: list[EmailStr] | None = Field(default=None, max_length=10)
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_strip)] = None
    address: Address | None = None
    customer_type: str | None = Field(default=None, max_length=60)
    source: str | None = Field(default=None, max_length=60)
    status: Status | None = None
    owner_id: int | None = None
    marketing_consent: bool | None = None
    custom_fields: dict[str, Any] | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(CustomerBase):
    pass


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    full_name: str
    display_name: str
    company: str | None
    email: str | None
    alt_emails: list[str]
    phone: str | None
    address: dict[str, Any] | None
    customer_type: str | None
    source: str | None
    status: Status
    owner_id: int | None
    marketing_consent: bool
    consent_at: datetime | None
    consent_source: str | None
    unsubscribed_at: datetime | None
    shop_user_id: int | None
    orders_count: int
    total_spent: Decimal
    first_order_at: datetime | None
    last_order_at: datetime | None
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    deleted_at: datetime | None
    tags: list[TagRef] = []


class CustomerPage(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    page_size: int


class EmailCheck(BaseModel):
    exists: bool
    customer_id: int | None = None
    display_name: str | None = None
