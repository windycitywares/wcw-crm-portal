"""Settings groups staff edit in Admin → Settings. One pydantic model per group (add a group = add a model
here and an entry in GROUPS). Defaults apply until someone saves the group.

Secrets (like the SMTP password) are declared in `SECRET_FIELDS`: stored encrypted with DATA_ENCRYPTION_KEY,
never returned by the API (the response says only whether one is set), and kept when a save leaves them empty.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class EmailSettings(BaseModel):
    enabled: bool = False
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls", "none"] = "ssl"
    smtp_user: str = Field(default="", max_length=255)
    smtp_password: str = Field(default="", max_length=500)  # secret
    from_name: str = Field(default="Windy City Wares", max_length=120)
    from_address: EmailStr | Literal[""] = ""
    reply_to: EmailStr | Literal[""] = ""
    footer_address: str = Field(default="", max_length=300)  # postal address for campaign footers (CAN-SPAM)
    daily_limit: int = Field(default=300, ge=1, le=100_000)  # all outgoing email, rolling 24 hours
    per_minute: int = Field(default=10, ge=1, le=600)

    @model_validator(mode="after")
    def _complete_when_enabled(self) -> "EmailSettings":
        if self.enabled:
            missing = [label for label, value in (("SMTP host", self.smtp_host), ("From address", self.from_address)) if not value]
            if missing:
                raise ValueError(f"To turn email on, fill in: {', '.join(missing)}")
        return self


class DayHours(BaseModel):
    open: str = "09:00"
    close: str = "17:00"

    @field_validator("open", "close")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not HHMM.match(v):
            raise ValueError("Use HH:MM (24-hour)")
        return v

    @model_validator(mode="after")
    def _order(self) -> "DayHours":
        if self.close <= self.open:
            raise ValueError("Closing time must be after opening time")
        return self


class BusinessHours(BaseModel):
    """Used for ticket response-time targets (SLA) and 'due in business days'."""

    timezone: str = "America/Chicago"
    days: dict[str, DayHours | None] = Field(default_factory=lambda: {
        d: (DayHours() if d not in ("sat", "sun") else None) for d in DAYS
    })
    holidays: list[date] = Field(default_factory=list, max_length=100)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown time zone (use a name like America/Chicago)") from None
        return v

    @field_validator("days")
    @classmethod
    def _days(cls, v: dict[str, DayHours | None]) -> dict[str, DayHours | None]:
        unknown = set(v) - set(DAYS)
        if unknown:
            raise ValueError(f"Unknown day(s): {', '.join(sorted(unknown))}")
        return {d: v.get(d) for d in DAYS}


GROUPS: dict[str, tuple[str, type[BaseModel]]] = {
    "email": ("Email", EmailSettings),
    "business_hours": ("Business hours", BusinessHours),
}
SECRET_FIELDS: dict[str, tuple[str, ...]] = {"email": ("smtp_password",)}
