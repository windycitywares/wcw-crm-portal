from collections.abc import Sequence

from sqlalchemy import Select

from app.shared.repository import BaseRepository

from .models import Attachment


class AttachmentRepository(BaseRepository[Attachment]):
    model = Attachment

    def for_entity(self, entity_type: str, entity_id: int) -> Select[tuple[Attachment]]:
        stmt = self.query().where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
        return stmt.order_by(Attachment.created_at.asc(), Attachment.id.asc())  # oldest first: reads like the thread

    async def list_for(self, entity_type: str, entity_id: int) -> Sequence[Attachment]:
        return await self.list(self.for_entity(entity_type, entity_id))

    def by_sha256(self, sha256: str) -> Select[tuple[Attachment]]:
        return self.query().where(Attachment.sha256 == sha256)

    async def count_stored(self, sha256: str) -> int:
        """How many rows still point at these bytes (soft-deleted ones don't: their file may go)."""
        return await self.count(self.by_sha256(sha256))
