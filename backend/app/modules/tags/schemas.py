from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import Color


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None


class TagWithCount(TagOut):
    uses: int


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: Color = None


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: Color = None


class TagsSet(BaseModel):
    """The full set of tag names a record should have; unknown names are created."""

    names: list[str] = Field(default_factory=list, max_length=50)
