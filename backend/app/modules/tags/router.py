from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import TagCreate, TagOut, TagsSet, TagUpdate, TagWithCount
from .service import TagService

router = APIRouter(tags=["tags"])
Manager = Annotated[User, Depends(require(Permission.LOOKUPS_MANAGE))]


@router.get("/tags", response_model=list[TagWithCount])
async def search_tags(session: SessionDep, _: CurrentUser, q: str | None = None,
                      limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[TagWithCount]:
    return await TagService(session).search(q, limit)


@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(session: SessionDep, actor: Manager, data: TagCreate) -> TagOut:
    return await TagService(session).create(data, actor)


@router.patch("/tags/{tag_id}", response_model=TagOut)
async def update_tag(session: SessionDep, actor: Manager, tag_id: int, data: TagUpdate) -> TagOut:
    return await TagService(session).update(tag_id, data, actor)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(session: SessionDep, actor: Manager, tag_id: int) -> None:
    await TagService(session).delete(tag_id, actor)


@router.get("/entities/{entity_type}/{entity_id}/tags", response_model=list[TagOut])
async def record_tags(session: SessionDep, user: CurrentUser, entity_type: str, entity_id: int) -> list[TagOut]:
    return await TagService(session).list_for(user, entity_type, entity_id)


@router.put("/entities/{entity_type}/{entity_id}/tags", response_model=list[TagOut])
async def set_record_tags(session: SessionDep, user: CurrentUser, entity_type: str, entity_id: int,
                          data: TagsSet) -> list[TagOut]:
    return await TagService(session).set_for(user, entity_type, entity_id, data.names)
