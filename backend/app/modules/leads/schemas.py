from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

# `converted` is set by the convert endpoint, so it is never accepted from a form.
LeadStatus = Literal["new", "contacted", "qualified", "unqualified"]
ReadStatus = Literal["new", "contacted", "qualified", "unqualified", "converted"]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


Text80 = Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)]


class LeadBase(BaseModel):
    first_name: Text80 = None
    last_name: Text80 = None
    company: Annotated[str | None, Field(default=None, max_length=160), AfterValidator(_strip)] = None
    email: EmailStr | None = None
    phone: Annotated[str | None, Field(default=None, max_length=40), AfterValidator(_strip)] = None
    source: str | None = Field(default=None, max_length=60)  # lookup key (kind lead_source)
    notes: Annotated[str | None, Field(default=None, max_length=20_000), AfterValidator(_strip)] = None
    owner_id: int | None = None
    custom_fields: dict[str, Any] | None = None


class LeadCreate(LeadBase):
    status: LeadStatus | None = None


class LeadUpdate(LeadBase):
    status: LeadStatus | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str | None
    last_name: str | None
    full_name: str
    display_name: str
    company: str | None
    email: str | None
    phone: str | None
    source: str | None
    status: ReadStatus
    notes: str | None
    owner_id: int | None
    owner_name: str | None = None
    converted_at: datetime | None
    converted_customer_id: int | None
    converted_customer_name: str | None = None
    converted_deal_id: int | None
    converted_deal_title: str | None = None
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LeadPage(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int


class LeadSummary(BaseModel):
    """What is in the funnel: a count per status, plus the leads nobody has picked up yet."""

    new: int
    contacted: int
    qualified: int
    unqualified: int
    converted: int
    total: int
    unassigned: int


class LeadConvert(BaseModel):
    """What converting a lead makes (SPEC §3.3: "Leads (unqualified) → convert to Customer + Deal").

    The customer is an existing one when `customer_id` is given, otherwise it is created from the lead's
    details (or reused when a customer already has that email). `create_deal` opens the first deal for
    them; leave it false for a lead that is only worth keeping as a contact.
    """

    customer_id: int | None = None
    create_deal: bool = True
    deal_title: Annotated[str | None, Field(default=None, max_length=200), AfterValidator(_strip)] = None
    stage_id: int | None = None
    value: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999999.99"))
    currency: str = Field(default="USD", min_length=3, max_length=3)
    expected_close_on: date | None = None
