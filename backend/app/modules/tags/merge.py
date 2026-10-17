from sqlalchemy import delete, select, update

from app.core.entities import RecordsMerged

from .models import Tagging


async def move_to_survivor(event: RecordsMerged, session) -> None:
    """A merged record's tags are added to the record it was merged into."""
    t = event.entity_type
    has = select(Tagging.tag_id).where(Tagging.entity_type == t, Tagging.entity_id == event.into_id)
    await session.execute(update(Tagging)
                          .where(Tagging.entity_type == t, Tagging.entity_id == event.from_id, Tagging.tag_id.not_in(has))
                          .values(entity_id=event.into_id))
    await session.execute(delete(Tagging).where(Tagging.entity_type == t, Tagging.entity_id == event.from_id))
