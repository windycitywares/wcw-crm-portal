from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Status = Literal["open", "done", "cancelled"]
Priority = Literal["low", "normal", "high"]
Recurrence = Literal["daily", "weekly", "monthly"]


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class TaskBase(BaseModel):
    title: Annotated[str | None, Field(default=None, max_length=200), AfterValidator(_strip)] = None
    description: Annotated[str | None, Field(default=None, max_length=10_000), AfterValidator(_strip)] = None
    task_type: str | None = Field(default=None, max_length=60)
    priority: Priority | None = None
    due_at: datetime | None = None
    due_has_time: bool | None = None
    reminder_at: datetime | None = None
    recurrence: Recurrence | None = None
    owner_id: int | None = None
    related_type: str | None = Field(default=None, max_length=40)
    related_id: int | None = None

    @model_validator(mode="after")
    def _related_pair(self) -> "TaskBase":
        if (self.related_type is None) != (self.related_id is None):
            raise ValueError("Give both related_type and related_id, or neither")
        if self.due_at and self.due_at.tzinfo is None:
            raise ValueError("due_at needs a time zone")
        if self.reminder_at and self.reminder_at.tzinfo is None:
            raise ValueError("reminder_at needs a time zone")
        return self


class TaskCreate(TaskBase):
    title: Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_strip)]


class TaskUpdate(TaskBase):
    status: Status | None = None


class RelatedRef(BaseModel):
    type: str
    id: int
    label: str | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    task_type: str | None
    priority: str
    status: str
    due_at: datetime | None
    due_has_time: bool
    reminder_at: datetime | None
    recurrence: str | None
    owner_id: int | None
    related_type: str | None
    related_id: int | None
    related_label: str | None = None
    completed_at: datetime | None
    completed_by: int | None
    created_at: datetime
    created_by: int | None
    updated_at: datetime
    is_overdue: bool = False


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class TaskSummary(BaseModel):
    open: int
    overdue: int
    due_today: int
