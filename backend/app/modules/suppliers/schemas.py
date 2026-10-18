from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, HttpUrl

def _required_words(value: str) -> str:
    text = " ".join((value or "").split())
    if not text:
        raise ValueError("must not be empty")
    return text


def _words(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return text or None


Name = Annotated[str, Field(max_length=160), AfterValidator(_required_words)]
Sku = Annotated[str, Field(max_length=80), AfterValidator(_required_words)]
Status = Literal["active", "inactive"]


class SupplierAddress(BaseModel):
    line1: str | None = Field(default=None, max_length=160)
    line2: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=100)


class SupplierContactIn(BaseModel):
    name: Name
    title: Annotated[str | None, Field(default=None, max_length=120), AfterValidator(_words)] = None
    email: EmailStr | None = None
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_words)] = None
    is_primary: bool = False


class SupplierContactUpdate(BaseModel):
    name: Name | None = None
    title: Annotated[str | None, Field(default=None, max_length=120), AfterValidator(_words)] = None
    email: EmailStr | None = None
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_words)] = None
    is_primary: bool | None = None


class SupplierContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    name: str
    title: str | None
    email: str | None
    phone: str | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class SupplierIn(BaseModel):
    name: Name
    supplier_type: Annotated[str, Field(min_length=1, max_length=60), AfterValidator(_required_words)]
    status: Status = "active"
    address: SupplierAddress | None = None
    website: HttpUrl | None = None
    payment_terms: Annotated[str | None, Field(default=None, max_length=300), AfterValidator(_words)] = None
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    rating: int | None = Field(default=None, ge=1, le=5)
    custom_fields: dict[str, Any] | None = None
    contacts: list[SupplierContactIn] = Field(default_factory=list, max_length=50)


class SupplierUpdate(BaseModel):
    name: Name | None = None
    supplier_type: Annotated[str | None, Field(default=None, max_length=60), AfterValidator(_words)] = None
    status: Status | None = None
    address: SupplierAddress | None = None
    website: HttpUrl | None = None
    payment_terms: Annotated[str | None, Field(default=None, max_length=300), AfterValidator(_words)] = None
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    rating: int | None = Field(default=None, ge=1, le=5)
    custom_fields: dict[str, Any] | None = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    supplier_type: str
    status: str
    address: dict[str, Any] | None
    website: str | None
    payment_terms: str | None
    lead_time_days: int | None
    currency: str
    rating: int | None
    custom_fields: dict[str, Any]
    contacts: list[SupplierContactOut] = Field(default_factory=list)
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class SupplierPage(BaseModel):
    items: list[SupplierOut]
    total: int
    page: int
    page_size: int


class SupplierProductIn(BaseModel):
    shop_sku: Sku
    supplier_sku: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_words)] = None
    description: Annotated[str | None, Field(default=None, max_length=300), AfterValidator(_words)] = None
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    notes: Annotated[str | None, Field(default=None), AfterValidator(_words)] = None


class SupplierProductUpdate(BaseModel):
    shop_sku: Sku | None = None
    supplier_sku: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_words)] = None
    description: Annotated[str | None, Field(default=None, max_length=300), AfterValidator(_words)] = None
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    notes: Annotated[str | None, Field(default=None), AfterValidator(_words)] = None


class SupplierProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    shop_sku: str
    supplier_sku: str | None
    description: str | None
    unit_cost: Decimal
    currency: str
    minimum_order_quantity: Decimal | None
    lead_time_days: int | None
    notes: str | None
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class SupplierProductsPage(BaseModel):
    items: list[SupplierProductOut]
    total: int
    page: int
    page_size: int