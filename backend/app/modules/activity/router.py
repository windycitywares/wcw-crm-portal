from fastapi import APIRouter, status

from app.core.pagination import PageDep
from app.modules.users.deps import CurrentUser, SessionDep

from .schemas import ActivityPage, NoteCreate, NoteOut, NoteUpdate
from .service import NoteService, TimelineService

router = APIRouter(tags=["notes & timeline"])
BASE = "/entities/{entity_type}/{entity_id}"


@router.get(BASE + "/notes", response_model=list[NoteOut])
async def list_notes(session: SessionDep, user: CurrentUser, entity_type: str, entity_id: int) -> list[NoteOut]:
    return await NoteService(session).list(user, entity_type, entity_id)


@router.post(BASE + "/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def add_note(session: SessionDep, user: CurrentUser, entity_type: str, entity_id: int, data: NoteCreate) -> NoteOut:
    return await NoteService(session).create(user, entity_type, entity_id, data)


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def update_note(session: SessionDep, user: CurrentUser, note_id: int, data: NoteUpdate) -> NoteOut:
    return await NoteService(session).update(user, note_id, data)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(session: SessionDep, user: CurrentUser, note_id: int) -> None:
    await NoteService(session).delete(user, note_id)


@router.get(BASE + "/timeline", response_model=ActivityPage)
async def timeline(session: SessionDep, user: CurrentUser, entity_type: str, entity_id: int, page: PageDep,
                   kind: str | None = None) -> ActivityPage:
    return await TimelineService(session).page(user, entity_type, entity_id, page, kind)
