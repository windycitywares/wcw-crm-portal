from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import KindOut, LookupCreate, LookupOut, LookupUpdate, ReorderIn
from .service import LookupService

router = APIRouter(prefix="/lookups", tags=["lookups"])
Manager = Annotated[User, Depends(require(Permission.LOOKUPS_MANAGE))]


@router.get("", response_model=list[KindOut])
async def list_kinds(session: SessionDep, _: CurrentUser) -> list[KindOut]:
    """Every type list with its values (inactive ones included, flagged) — forms filter `is_active`."""
    return await LookupService(session).kinds()


@router.get("/{kind}", response_model=list[LookupOut])
async def list_values(session: SessionDep, _: CurrentUser, kind: str, active_only: bool = False) -> list[LookupOut]:
    return await LookupService(session).values(kind, include_inactive=not active_only)


@router.post("/{kind}", response_model=LookupOut, status_code=status.HTTP_201_CREATED)
async def create_value(session: SessionDep, actor: Manager, kind: str, data: LookupCreate) -> LookupOut:
    return await LookupService(session).create(kind, data, actor)


@router.patch("/{kind}/{value_id}", response_model=LookupOut)
async def update_value(session: SessionDep, actor: Manager, kind: str, value_id: int, data: LookupUpdate) -> LookupOut:
    return await LookupService(session).update(kind, value_id, data, actor)


@router.put("/{kind}/order", response_model=list[LookupOut])
async def reorder_values(session: SessionDep, actor: Manager, kind: str, data: ReorderIn) -> list[LookupOut]:
    return await LookupService(session).reorder(kind, data.ids, actor)
