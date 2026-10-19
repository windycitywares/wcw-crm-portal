from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.shared.schemas import Color

Status = Literal["open", "won", "lost"]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class StageIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_strip)]
    probability: int = Field(default=0, ge=0, le=100)
    is_won: bool = False
    is_lost: bool = False
    color: Color = None  # a theme tone (neutral, accent, success, warning, danger, info) or #rrggbb


class StageUpdate(BaseModel):
    name: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)] = None
    probability: int | None = Field(default=None, ge=0, le=100)
    is_won: bool | None = None
    is_lost: bool | None = None
    color: Color = None
    position: int | None = Field(default=None, ge=0)


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    name: str
    position: int
    probability: int
    is_won: bool
    is_lost: bool
    color: str | None


class PipelineIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_strip)]
    is_default: bool = False
    stages: list[StageIn] | None = None  # left empty, a starter set is created


class PipelineUpdate(BaseModel):
    name: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)] = None
    is_default: bool | None = None


class PipelineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
    stages: list[StageOut] = Field(default_factory=list)


class DealBase(BaseModel):
    title: Annotated[str | None, Field(default=None, max_length=200), AfterValidator(_strip)] = None
    description: Annotated[str | None, Field(default=None, max_length=20_000), AfterValidator(_strip)] = None
    customer_id: int | None = None
    stage_id: int | None = None
    status: Status | None = None
    value: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999999.99"))
    currency: str = Field(default="USD", min_length=3, max_length=3)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_on: date | None = None
    owner_id: int | None = None
    source: str | None = Field(default=None, max_length=60)  # lookup key (kind lead_source)
    lost_reason: str | None = Field(default=None, max_length=60)  # lookup key (kind lost_reason)
    position: int | None = Field(default=None, ge=0)
    custom_fields: dict[str, Any] | None = None


class DealCreate(DealBase):
    title: Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_strip)]


class DealUpdate(DealBase):
    pass


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    customer_id: int | None
    customer_name: str | None = None
    pipeline_id: int | None = None
    pipeline_name: str | None = None
    stage_id: int | None
    stage_name: str | None = None
    status: str
    value: Decimal
    currency: str
    probability: int
    weighted_value: Decimal = Decimal("0")
    expected_close_on: date | None
    closed_at: datetime | None
    owner_id: int | None
    owner_name: str | None = None
    source: str | None
    lost_reason: str | None
    position: int
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DealPage(BaseModel):
    items: list[DealOut]
    total: int
    page: int
    page_size: int


class BoardStage(BaseModel):
    """One kanban column: its stage, the open deals on it (in order) and the column's money."""

    stage: StageOut
    deals: list[DealOut]
    total_value: Decimal = Decimal("0")
    weighted_value: Decimal = Decimal("0")


class Board(BaseModel):
    pipeline_id: int
    pipeline_name: str
    stages: list[BoardStage]


class SalesSummary(BaseModel):
    """The dashboard/header numbers: open pipeline and what was won or lost since the start of the month."""

    open_count: int
    open_value: Decimal
    weighted_value: Decimal
    won_count: int
    won_value: Decimal
    lost_count: int


class DealItemIn(BaseModel):
    """A line added to a deal. `quantity` may be fractional (1.5 hours of work is a line too)."""

    name: Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_strip)]
    sku: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)] = None
    shop_product_id: int | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0, le=Decimal("999999.99"))
    unit_price: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999999.99"))
    position: int | None = Field(default=None, ge=0)


class DealItemUpdate(BaseModel):
    name: Annotated[str | None, Field(default=None, max_length=200), AfterValidator(_strip)] = None
    sku: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)] = None
    shop_product_id: int | None = None
    quantity: Decimal | None = Field(default=None, gt=0, le=Decimal("999999.99"))
    unit_price: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))
    position: int | None = Field(default=None, ge=0)


class DealItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deal_id: int
    name: str
    sku: str | None
    shop_product_id: int | None
    quantity: Decimal
    unit_price: Decimal
    total: Decimal
    position: int
    created_at: datetime
    updated_at: datetime


class DealItems(BaseModel):
    """Every line on a deal and what they add up to — put it next to the deal's own value."""

    items: list[DealItemOut]
    count: int
    total: Decimal


class ShopProductOut(BaseModel):
    """A line the shop's catalog offers, as the picker on a deal reads it (shop docs/CRM_SYNC.md).

    `price` is the catalog's base price — a starting unit price the salesperson may change on the line.
    """

    id: int
    parent_id: int | None = None
    sku: str
    name: str
    price: Decimal = Decimal("0")
    compare_at_price: Decimal | None = None
    currency: str = "USD"
    stock_status: str | None = None
    image: str | None = None
