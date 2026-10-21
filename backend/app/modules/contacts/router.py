from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .repository import SORTS
from .schemas import ContactCreate, ContactOut, ContactPage, ContactUpdate
from .service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"], dependencies=[Depends(require(Permission.CUSTOMERS_VIEW))])
Sort = Literal[tuple(SORTS)]  # type: ignore[valid-type]


@router.get("", response_model=ContactPage)
async def list_contacts(
    session: SessionDep, user: CurrentUser, page: PageDep, q: str | None = None, type: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None, owner: Literal["me", "any"] = "any",
    owner_id: int | None = None, sort: Sort = "-updated",
) -> ContactPage:
    return await ContactService(session).list(
        page, q=q, type=type, status=status_, owner_id=user.id if owner == "me" else owner_id, sort=sort)


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(session: SessionDep, contact_id: int) -> ContactOut:
    return await ContactService(session).get(contact_id)


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    session: SessionDep, actor: Annotated[User, Depends(require(Permission.CUSTOMERS_EDIT_OWN))], data: ContactCreate,
) -> ContactOut:
    return await ContactService(session).create(data, actor)


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(session: SessionDep, actor: CurrentUser, contact_id: int, data: ContactUpdate) -> ContactOut:
    return await ContactService(session).update(contact_id, data, actor)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(session: SessionDep, actor: CurrentUser, contact_id: int) -> None:
    await ContactService(session).delete(contact_id, actor)
