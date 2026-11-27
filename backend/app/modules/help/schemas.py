from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    topic_id: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    page: str = Field(default="", max_length=200)
    helpful: bool
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    id: int
    topic_id: str
    page: str
    helpful: bool
    comment: str | None
    user_name: str | None
    created_at: datetime


class TopicSummary(BaseModel):
    topic_id: str
    helpful: int
    not_helpful: int
    last_at: datetime
