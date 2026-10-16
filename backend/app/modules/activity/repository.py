from collections.abc import Sequence

from sqlalchemy import Select, select

from app.shared.repository import BaseRepository

from .models import Activity, Note


class NoteRepository(BaseRepository[Note]):
    model = Note

    async def for_entity(self, entity_type: str, entity_id: int) -> Sequence[Note]:
        stmt = (self.query().where(Note.entity_type == entity_type, Note.entity_id == entity_id)
                .order_by(Note.pinned.desc(), Note.created_at.desc(), Note.id.desc()))
        return await self.list(stmt)


class ActivityRepository(BaseRepository[Activity]):
    model = Activity

    def for_entity(self, entity_type: str, entity_id: int, kind: str | None = None) -> Select[tuple[Activity]]:
        stmt = select(Activity).where(Activity.entity_type == entity_type, Activity.entity_id == entity_id)
        if kind:
            stmt = stmt.where(Activity.kind.startswith(kind))
        return stmt.order_by(Activity.at.desc(), Activity.id.desc())
