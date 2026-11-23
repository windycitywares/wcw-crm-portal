from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from datetime import datetime

from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .service import TrashService

router = APIRouter(prefix="/trash", tags=["trash"])
Manager = Annotated[User, Depends(require(Permission.TRASH_MANAGE))]


class TrashItem(BaseModel):
    type: str
    label: str
    id: int
    title: str
    deleted_at: datetime
    deleted_by: int | None
    purge_after: datetime


class TrashPage(BaseModel):
    items: list[TrashItem]
    total: int
    page: int
    page_size: int
    retention_days: int


class TrashCount(BaseModel):
    type: str
    label: str
    count: int


class Restored(BaseModel):
    type: str
    id: int
    title: str


@router.get("", response_model=TrashPage)
async def list_trash(session: SessionDep, _: Manager, type: Annotated[str | None, Query(max_length=40)] = None,
                     page: Annotated[int, Query(ge=1)] = 1,
                     page_size: Annotated[int, Query(ge=1, le=200)] = 50) -> TrashPage:
    """Deleted records, newest first, with the date each one is removed for good."""
    return TrashPage(**await TrashService(session).list(type=type, page=page, page_size=page_size))


@router.get("/summary", response_model=list[TrashCount])
async def trash_summary(session: SessionDep, _: Manager) -> list[TrashCount]:
    return [TrashCount(**r) for r in await TrashService(session).summary()]


@router.get("/blockers/{type}/{item_id}", response_model=list[str])
async def blockers(session: SessionDep, _: Annotated[User, Depends(require(Permission.CUSTOMERS_VIEW))],
                   type: str, item_id: int) -> list[str]:
    """What still hangs off a record ("2 deals") — the screen asks this before offering Delete."""
    return await TrashService(session).blockers(type, item_id)


@router.post("/{type}/{item_id}/restore", response_model=Restored)
async def restore(session: SessionDep, actor: Manager, type: str, item_id: int) -> Restored:
    return Restored(**await TrashService(session).restore(type, item_id, actor))


@router.delete("/{type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def purge(session: SessionDep, actor: Annotated[User, Depends(require(Permission.DATA_DELETE))],
                type: str, item_id: int) -> None:
    """Delete for good now, without waiting for the retention period. Admin only; can't be undone."""
    await TrashService(session).purge(type, item_id, actor)
