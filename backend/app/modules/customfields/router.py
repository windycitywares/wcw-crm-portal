from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.entities import entity_types
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import FieldDefCreate, FieldDefOut, FieldDefUpdate, FieldTypeOut, ReorderIn
from .service import CustomFieldService

router = APIRouter(prefix="/custom-fields", tags=["custom fields"])
Manager = Annotated[User, Depends(require(Permission.LOOKUPS_MANAGE))]


@router.get("/types", response_model=list[FieldTypeOut])
async def field_types(_: CurrentUser) -> list[FieldTypeOut]:
    return CustomFieldService.field_types()


@router.get("/record-types", response_model=list[dict])
async def record_types(_: CurrentUser) -> list[dict]:
    """Record types that can have custom fields (filled in as modules are installed)."""
    return [{"key": e.key, "label": e.label} for e in entity_types()]


@router.get("/{entity_type}", response_model=list[FieldDefOut])
async def list_fields(session: SessionDep, _: CurrentUser, entity_type: str, active_only: bool = False) -> list[FieldDefOut]:
    return await CustomFieldService(session).list(entity_type, active_only=active_only)


@router.post("/{entity_type}", response_model=FieldDefOut, status_code=status.HTTP_201_CREATED)
async def create_field(session: SessionDep, actor: Manager, entity_type: str, data: FieldDefCreate) -> FieldDefOut:
    return await CustomFieldService(session).create(entity_type, data, actor)


@router.patch("/{entity_type}/{field_id}", response_model=FieldDefOut)
async def update_field(session: SessionDep, actor: Manager, entity_type: str, field_id: int,
                       data: FieldDefUpdate) -> FieldDefOut:
    return await CustomFieldService(session).update(entity_type, field_id, data, actor)


@router.put("/{entity_type}/order", response_model=list[FieldDefOut])
async def reorder_fields(session: SessionDep, actor: Manager, entity_type: str, data: ReorderIn) -> list[FieldDefOut]:
    return await CustomFieldService(session).reorder(entity_type, data.ids, actor)
