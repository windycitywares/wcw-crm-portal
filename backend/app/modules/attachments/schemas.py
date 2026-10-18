from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    """One kept file. It carries no address of its own: the download route is built from the id, and
    which file it is comes from `filename` — nothing here is a filesystem path."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    filename: str
    content_type: str
    size: int
    source: str
    created_by: int | None
    created_at: datetime
