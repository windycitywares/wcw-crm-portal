from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .repository import SORTS
from .schemas import CustomerCreate, CustomerOut, CustomerPage, CustomerUpdate, EmailCheck
from .service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"], dependencies=[Depends(require(Permission.CUSTOMERS_VIEW))])
Sort = Literal[tuple(SORTS)]  # type: ignore[valid-type]


@router.get("", response_model=CustomerPage)
async def list_customers(
    session: SessionDep, user: CurrentUser, page: PageDep, q: str | None = None, type: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None, owner: Literal["me", "any"] = "any",
    owner_id: int | None = None, tag_id: int | None = None, has_orders: bool | None = None, deleted: bool = False,
    sort: Sort = "-updated",
) -> CustomerPage:
    return await CustomerService(session).list(
        page, q=q, customer_type=type, status=status_, owner_id=user.id if owner == "me" else owner_id,
        tag_id=tag_id, has_orders=has_orders, deleted=deleted, sort=sort,
    )


@router.get("/check-email", response_model=EmailCheck)
async def check_email(session: SessionDep, email: Annotated[str, Query(max_length=320)], exclude_id: int | None = None) -> EmailCheck:
    return await CustomerService(session).check_email(email, exclude_id)


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(session: SessionDep, actor: Annotated[User, Depends(require(Permission.CUSTOMERS_EDIT_OWN))],
                          data: CustomerCreate) -> CustomerOut:
    return await CustomerService(session).create(data, actor)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(session: SessionDep, customer_id: int, deleted: bool = False) -> CustomerOut:
    return await CustomerService(session).get(customer_id, include_deleted=deleted)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(session: SessionDep, actor: CurrentUser, customer_id: int, data: CustomerUpdate) -> CustomerOut:
    return await CustomerService(session).update(customer_id, data, actor)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(session: SessionDep, actor: CurrentUser, customer_id: int) -> None:
    await CustomerService(session).delete(customer_id, actor)


@router.post("/{customer_id}/restore", response_model=CustomerOut)
async def restore_customer(session: SessionDep, actor: CurrentUser, customer_id: int) -> CustomerOut:
    return await CustomerService(session).restore(customer_id, actor)
