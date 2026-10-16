from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    actor_id: int | None
    actor_email: str | None
    action: str
    entity_type: str | None
    entity_id: int | None
    changes: dict[str, Any] | None
    ip: str | None


class AuditPage(BaseModel):
    items: list[AuditOut]
    total: int
    page: int
    page_size: int
