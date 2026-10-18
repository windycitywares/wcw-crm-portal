from sqlalchemy import update

from app.core.entities import RecordsMerged

from .models import Attachment


async def move_to_survivor(event: RecordsMerged, session) -> None:
    """Files on a merged record belong to the record it was merged into, exactly as its notes do."""
    await session.execute(update(Attachment)
                          .where(Attachment.entity_type == event.entity_type, Attachment.entity_id == event.from_id)
                          .values(entity_id=event.into_id))
