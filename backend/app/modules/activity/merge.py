from sqlalchemy import update

from app.core.entities import RecordsMerged

from .models import Activity, Note


async def move_to_survivor(event: RecordsMerged, session) -> None:
    """Notes and timeline lines of a merged record move to the record it was merged into."""
    for model in (Note, Activity):
        await session.execute(update(model)
                              .where(model.entity_type == event.entity_type, model.entity_id == event.from_id)
                              .values(entity_id=event.into_id))
