from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Status = Literal["new", "open", "pending", "resolved", "closed"]
MessageKind = Literal["note", "reply"]
View = Literal["all", "mine", "unassigned"]
State = Literal["unresolved", "resolved", "all"]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class TicketBase(BaseModel):
    subject: Annotated[str | None, Field(default=None, max_length=200), AfterValidator(_strip)] = None
    description: Annotated[str | None, Field(default=None, max_length=20_000), AfterValidator(_strip)] = None
    ticket_type: str | None = Field(default=None, max_length=60)
    priority: str | None = Field(default=None, max_length=60)
    customer_id: int | None = None
    shop_order_id: int | None = None
    assignee_id: int | None = None
    custom_fields: dict[str, Any] | None = None


class TicketCreate(TicketBase):
    subject: Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_strip)]


class TicketUpdate(TicketBase):
    status: Status | None = None


class TicketMessageIn(BaseModel):
    body: Annotated[str, Field(min_length=1, max_length=20_000), AfterValidator(_strip)]
    kind: MessageKind = "note"


class TicketMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: str
    body: str
    from_email: str | None
    to_email: str | None
    created_by: int | None
    created_at: datetime
    author_name: str | None = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str | None
    subject: str
    description: str | None
    ticket_type: str | None
    priority: str
    status: str
    customer_id: int | None
    customer_name: str | None = None
    shop_order_id: int | None
    assignee_id: int | None
    assignee_name: str | None = None
    sla_policy_id: int | None
    first_response_due_at: datetime | None
    resolve_due_at: datetime | None
    first_responded_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    first_response_breached: bool
    resolve_breached: bool
    is_overdue: bool = False
    custom_fields: dict[str, Any]
    created_at: datetime
    created_by: int | None
    updated_at: datetime


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int
    page: int
    page_size: int


class TicketSummary(BaseModel):
    open: int
    unassigned: int
    overdue: int
    mine: int


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ticket_type: str | None
    priority: str | None
    first_response_minutes: int
    resolve_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SlaPolicyCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_strip)]
    ticket_type: str | None = Field(default=None, max_length=60)
    priority: str | None = Field(default=None, max_length=60)
    first_response_minutes: int = Field(ge=1, le=60 * 24 * 60)
    resolve_minutes: int = Field(ge=1, le=60 * 24 * 60)
    is_active: bool = True


class SlaPolicyUpdate(BaseModel):
    name: Annotated[str | None, Field(default=None, max_length=80), AfterValidator(_strip)] = None
    ticket_type: str | None = Field(default=None, max_length=60)
    priority: str | None = Field(default=None, max_length=60)
    first_response_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 60)
    resolve_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 60)
    is_active: bool | None = None
