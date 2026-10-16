import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class DeployConfig(BaseModel):
    mode: Literal["auto", "schedule", "paused"]
    interval_minutes: int = Field(default=10, ge=1, le=1440)
    schedule_times: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("schedule_times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        for t in v:
            if not HHMM.match(t):
                raise ValueError("Use HH:MM (24-hour) times")
        return sorted(set(v))


class Version(BaseModel):
    commit: str | None
    subject: str | None
    date: str | None


class DeployStatus(DeployConfig):
    timezone: str
    requested_at: datetime | None
    requested_by: str | None
    last_check_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    running: bool
    last_reason: str | None
    last_result: str | None
    api: Version
    web_build: str | None
    cron_seen: bool  # the server's cron has called in within the last few minutes
