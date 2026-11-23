from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.contacts.schemas import ContactPage
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .repository import SORTS
from .links import LinkService
from .schemas import AccountIn, AccountLinkIn, AccountLinkOut, AccountLinkUpdate, AccountOption, AccountOut, AccountPage, AccountUpdate
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


@router.get("/links", response_model=list[AccountLinkOut])
async def contact_links(session: SessionDep, contact_id: int) -> list[AccountLinkOut]:
    """A person's organisations, current ones first, then the ones they have left (with dates)."""
    return [AccountLinkOut(**row) for row in await LinkService(session).for_contact(contact_id)]


@router.patch("/links/{link_id}", response_model=AccountLinkOut)
async def update_link(session: SessionDep, actor: CurrentUser, link_id: int, data: AccountLinkUpdate) -> AccountLinkOut:
    """Change the role or start date, make it the person's main account, or end it on a date (`ended_on`)."""
    return AccountLinkOut(**await LinkService(session).update(link_id, data.model_dump(exclude_unset=True), actor))


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_link(session: SessionDep, actor: CurrentUser, link_id: int) -> None:
    """End the link today. It isn't deleted: the person's history at the account stays."""
    await LinkService(session).end(link_id, actor)


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(session: SessionDep, account_id: int) -> AccountOut:
    return await AccountService(session).get(account_id)


@router.get("/{account_id}/contacts", response_model=ContactPage)
async def account_contacts(session: SessionDep, account_id: int, page: PageDep) -> ContactPage:
    from app.modules.contacts.service import ContactService

    await AccountService(session).get(account_id)
    return await ContactService(session).list(page, account_id=account_id, sort="name")


@router.get("/{account_id}/people", response_model=list[AccountLinkOut])
async def account_people(session: SessionDep, account_id: int, include_ended: bool = False) -> list[AccountLinkOut]:
    """Everyone linked to the account with their role there; `include_ended=true` adds the people who have left."""
    await AccountService(session).get(account_id)
    return [AccountLinkOut(**r) for r in await LinkService(session).for_account(account_id, include_ended=include_ended)]


@router.post("/{account_id}/people", response_model=AccountLinkOut, status_code=status.HTTP_201_CREATED)
async def link_person(session: SessionDep, actor: CurrentUser, account_id: int, data: AccountLinkIn) -> AccountLinkOut:
    """Link an existing contact to this account too. It becomes their main account if they had none or `is_primary`."""
    await AccountService(session).get(account_id)
    return AccountLinkOut(**await LinkService(session).add(account_id, data.contact_id, role=data.role,
                                                          is_primary=data.is_primary, started_on=data.started_on,
                                                          actor=actor))


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(session: SessionDep, actor: CurrentUser, account_id: int, data: AccountUpdate) -> AccountOut:
    return await AccountService(session).update(account_id, data, actor)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(session: SessionDep, actor: CurrentUser, account_id: int) -> None:
    await AccountService(session).delete(account_id, actor)
