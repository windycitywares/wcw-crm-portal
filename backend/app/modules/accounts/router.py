from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.contacts.schemas import ContactPage
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .repository import SORTS
from .schemas import AccountIn, AccountOption, AccountOut, AccountPage, AccountUpdate
from .service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"], dependencies=[Depends(require(Permission.CUSTOMERS_VIEW))])
Sort = Literal[tuple(SORTS)]  # type: ignore[valid-type]


@router.get("", response_model=AccountPage)
async def list_accounts(
    session: SessionDep, user: CurrentUser, page: PageDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    type: Annotated[str | None, Query(max_length=60)] = None,
    status_: Annotated[Literal["active", "inactive"] | None, Query(alias="status")] = None,
    owner: Literal["me", "any"] = "any", sort: Sort = "name",
) -> AccountPage:
    return await AccountService(session).list(page, q=q, account_type=type, status=status_,
                                              owner_id=user.id if owner == "me" else None, sort=sort)


@router.get("/options", response_model=list[AccountOption])
async def account_options(
    session: SessionDep, q: Annotated[str | None, Query(max_length=120)] = None,
    type: Annotated[str | None, Query(max_length=60)] = None,
) -> list[AccountOption]:
    """Active accounts for a picker, e.g. `?type=supplier` for "select supplier"."""
    return await AccountService(session).options(q=q, account_type=type)


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    session: SessionDep, actor: Annotated[User, Depends(require(Permission.CUSTOMERS_EDIT_OWN))], data: AccountIn,
) -> AccountOut:
    return await AccountService(session).create(data, actor)


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(session: SessionDep, account_id: int) -> AccountOut:
    return await AccountService(session).get(account_id)


@router.get("/{account_id}/contacts", response_model=ContactPage)
async def account_contacts(session: SessionDep, account_id: int, page: PageDep) -> ContactPage:
    from app.modules.contacts.service import ContactService

    await AccountService(session).get(account_id)
    return await ContactService(session).list(page, account_id=account_id, sort="name")


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(session: SessionDep, actor: CurrentUser, account_id: int, data: AccountUpdate) -> AccountOut:
    return await AccountService(session).update(account_id, data, actor)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(session: SessionDep, actor: CurrentUser, account_id: int) -> None:
    await AccountService(session).delete(account_id, actor)
