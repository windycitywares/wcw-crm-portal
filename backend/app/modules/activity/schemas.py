from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Write something first")
    return value


Body = Annotated[str, Field(max_length=20_000), AfterValidator(_text)]


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    body: str
    pinned: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    body: Body
    pinned: bool = False


class NoteUpdate(BaseModel):
    body: Body | None = None
    pinned: bool | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    actor_id: int | None
    kind: str
    title: str
    data: dict[str, Any] | None


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    page: int
    page_size: int
