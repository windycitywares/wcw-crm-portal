from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from .types import FIELD_TYPES


def _options(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cleaned, seen = [], set()
    for v in value:
        v = " ".join(str(v).split())[:120]
        if v and v.lower() not in seen:
            seen.add(v.lower())
            cleaned.append(v)
    return cleaned


def _field_type(value: str) -> str:
    if value not in FIELD_TYPES:
        raise ValueError(f"Use one of: {', '.join(FIELD_TYPES)}")
    return value


Options = Annotated[list[str] | None, Field(max_length=200), AfterValidator(_options)]


class FieldDefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    key: str
    label: str
    field_type: str
    options: list[Any] | None
    required: bool
    help_text: str | None
    sort_order: int
    is_active: bool
    updated_at: datetime


class FieldDefCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    key: str | None = Field(default=None, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    field_type: Annotated[str, AfterValidator(_field_type)]
    options: Options = None
    required: bool = False
    help_text: str | None = Field(default=None, max_length=255)


class FieldDefUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    options: Options = None
    required: bool | None = None
    help_text: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class FieldTypeOut(BaseModel):
    key: str
    label: str


class ReorderIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
