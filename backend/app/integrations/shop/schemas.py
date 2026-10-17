"""What the shop sends. Unknown fields are ignored so the shop can add more without breaking the CRM."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Envelope(_Loose):
    id: str = Field(min_length=8, max_length=64)
    type: str = Field(min_length=3, max_length=60)
    occurred_at: datetime | None = None
    data: dict[str, Any]


class ShopAddress(_Loose):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None

    def for_crm(self) -> dict[str, str | None]:
        return {"line1": self.line1, "line2": self.line2, "city": self.city, "state": self.region,
                "postal_code": self.postal_code, "country": self.country}


class CustomerData(_Loose):
    id: int  # shop user id
    email: str = Field(max_length=320)
    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)


class OrderData(_Loose):
    id: int
    number: str = Field(max_length=32)
    user_id: int | None = None
    email: str = Field(max_length=320)
    customer_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    status: str = Field(max_length=20)
    payment_status: str = Field(default="unpaid", max_length=20)
    currency: str = Field(default="USD", max_length=3)
    grand_total: Decimal = Decimal("0")
    refunded_total: Decimal = Decimal("0")
    placed_at: datetime | None = None
    updated_at: datetime | None = None
    marketing_opt_in: bool = False
    billing_address: ShopAddress | None = None
    shipping_address: ShopAddress | None = None


class NewsletterData(_Loose):
    email: str = Field(max_length=320)
    source: str | None = Field(default=None, max_length=20)


class ContactData(_Loose):
    """A shop contact-form message (SPEC §3.5). The CRM opens a ticket for it, so `email` and `message`
    are required; the rest is used when present."""

    email: str = Field(max_length=320)
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=20_000)
    order_number: str | None = Field(default=None, max_length=32)


class ShopStatus(BaseModel):
    enabled: bool
    secret_set: bool
    webhook_url: str
    last_event_at: datetime | None
    counts: dict[str, int]


class ShopEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    event_type: str
    status: str
    attempts: int
    error: str | None
    customer_id: int | None
    occurred_at: datetime | None
    received_at: datetime
    processed_at: datetime | None


class ShopEventPage(BaseModel):
    items: list[ShopEventOut]
    total: int
    page: int
    page_size: int
