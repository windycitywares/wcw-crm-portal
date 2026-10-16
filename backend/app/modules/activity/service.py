"""Notes and the activity timeline for any registered record type.

Other modules write timeline lines with:

    await TimelineService(session).record("customer", 42, "order.created", "Order #1042 placed", actor=user,
                                          data={"order_id": 1042, "total": "58.00"})

inside their own transaction (the caller commits).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import check_entity_access
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.modules.audit.service import AuditService

from .models import Activity, Note
from .repository import ActivityRepository, NoteRepository
from .schemas import ActivityOut, ActivityPage, NoteCreate, NoteOut, NoteUpdate

PREVIEW = 140


def preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= PREVIEW else flat[: PREVIEW - 1].rstrip() + "…"


class TimelineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ActivityRepository(session)

    async def record(self, entity_type: str, entity_id: int, kind: str, title: str, *, actor: Any = None,
                     data: dict[str, Any] | None = None) -> Activity:
        return await self.repo.add(Activity(
            entity_type=entity_type, entity_id=entity_id, kind=kind, title=title[:200],
            actor_id=getattr(actor, "id", None), data=data,
        ))

    async def page(self, user, entity_type: str, entity_id: int, params: PageParams, kind: str | None = None) -> ActivityPage:
        await check_entity_access(self.session, user, entity_type, entity_id, write=False)
        rows, total = await self.repo.paginate(self.repo.for_entity(entity_type, entity_id, kind), params)
        return ActivityPage(items=[ActivityOut.model_validate(r) for r in rows], total=total,
                            page=params.page, page_size=params.page_size)


class NoteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NoteRepository(session)
        self.timeline = TimelineService(session)
        self.audit = AuditService(session)

    async def list(self, user, entity_type: str, entity_id: int) -> list[NoteOut]:
        await check_entity_access(self.session, user, entity_type, entity_id, write=False)
        return [NoteOut.model_validate(n) for n in await self.repo.for_entity(entity_type, entity_id)]

    async def create(self, user, entity_type: str, entity_id: int, data: NoteCreate) -> NoteOut:
        # Anyone who can see a record may add a note to it (a note doesn't change the record itself).
        await check_entity_access(self.session, user, entity_type, entity_id, write=False)
        note = await self.repo.add(Note(entity_type=entity_type, entity_id=entity_id, body=data.body.strip(),
                                        pinned=data.pinned, created_by=user.id, updated_by=user.id))
        await self.timeline.record(entity_type, entity_id, "note.added", "Note added", actor=user,
                                   data={"note_id": note.id, "preview": preview(note.body)})
        await self.session.commit()
        await self.session.refresh(note)
        return NoteOut.model_validate(note)

    async def _own_or_manager(self, user, note_id: int) -> Note:
        note = await self.repo.get(note_id)
        if note is None:
            raise NotFoundError("Note not found")
        await check_entity_access(self.session, user, note.entity_type, note.entity_id, write=False)
        if note.created_by != user.id and not has_permission(user.role, Permission.DATA_EXPORT):
            # Managers/Admins (who can export data) may tidy anyone's notes; others only their own.
            raise PermissionDeniedError("You can only change your own notes")
        return note

    async def update(self, user, note_id: int, data: NoteUpdate) -> NoteOut:
        note = await self._own_or_manager(user, note_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if "body" in changes:
            note.body = changes["body"].strip()
        if "pinned" in changes:
            note.pinned = changes["pinned"]
        note.updated_by = user.id
        await self.session.commit()
        await self.session.refresh(note)
        return NoteOut.model_validate(note)

    async def delete(self, user, note_id: int) -> None:
        note = await self._own_or_manager(user, note_id)
        await self.repo.soft_delete(note)
        await self.audit.record("note.delete", actor=user, entity_type=note.entity_type, entity_id=note.entity_id,
                                changes={"note_id": note.id, "preview": preview(note.body)})
        await self.timeline.record(note.entity_type, note.entity_id, "note.deleted", "Note deleted", actor=user,
                                   data={"note_id": note.id})
        await self.session.commit()
