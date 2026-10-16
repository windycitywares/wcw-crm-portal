import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

COLOR = re.compile(r"^(#[0-9a-fA-F]{6}|neutral|accent|success|warning|danger|info)$")


def _color(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not COLOR.match(value):
        raise ValueError("Use #rrggbb or one of neutral, accent, success, warning, danger, info")
    return value


Color = Annotated[str | None, AfterValidator(_color)]


class LookupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    key: str
    label: str
    color: str | None
    sort_order: int
    is_active: bool
    updated_at: datetime


class KindOut(BaseModel):
    key: str
    label: str
    description: str
    values: list[LookupOut]


class LookupCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    key: str | None = Field(default=None, max_length=60, pattern=r"^[a-z0-9_]+$")
    color: Color = None


class LookupUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    color: Color = None
    is_active: bool | None = None


class ReorderIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
