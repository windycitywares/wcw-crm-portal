from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import (
    SupplierContactIn, SupplierContactOut, SupplierContactUpdate, SupplierIn, SupplierOut, SupplierPage,
    SupplierUpdate,
)
from .service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"],
                   dependencies=[Depends(require(Permission.SUPPLIERS_VIEW))])
Editor = Annotated[User, Depends(require(Permission.SUPPLIERS_EDIT))]


@router.get("", response_model=SupplierPage)
async def list_suppliers(
    session: SessionDep,
    page: PageDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    supplier_type: Annotated[str | None, Query(max_length=60)] = None,
    status_: Annotated[Literal["active", "inactive"] | None, Query(alias="status")] = None,
) -> SupplierPage:
    return await SupplierService(session).list(page, q=q, supplier_type=supplier_type, status=status_)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(session: SessionDep, actor: Editor, data: SupplierIn) -> SupplierOut:
    return await SupplierService(session).create(data, actor)


@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(session: SessionDep, supplier_id: int) -> SupplierOut:
    return await SupplierService(session).get(supplier_id)


@router.patch("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(session: SessionDep, actor: Editor, supplier_id: int,
                          data: SupplierUpdate) -> SupplierOut:
    return await SupplierService(session).update(supplier_id, data, actor)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(session: SessionDep, actor: Editor, supplier_id: int) -> None:
    await SupplierService(session).delete(supplier_id, actor)


@router.post("/{supplier_id}/contacts", response_model=SupplierContactOut, status_code=status.HTTP_201_CREATED)
async def add_contact(session: SessionDep, actor: Editor, supplier_id: int,
                      data: SupplierContactIn) -> SupplierContactOut:
    return await SupplierService(session).add_contact(supplier_id, data, actor)


@router.patch("/{supplier_id}/contacts/{contact_id}", response_model=SupplierContactOut)
async def update_contact(session: SessionDep, actor: Editor, supplier_id: int, contact_id: int,
                         data: SupplierContactUpdate) -> SupplierContactOut:
    return await SupplierService(session).update_contact(supplier_id, contact_id, data, actor)


@router.delete("/{supplier_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(session: SessionDep, actor: Editor, supplier_id: int, contact_id: int) -> None:
    await SupplierService(session).delete_contact(supplier_id, contact_id, actor)