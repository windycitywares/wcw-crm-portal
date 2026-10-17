from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import LeadConvert, LeadCreate, LeadOut, LeadPage, LeadSummary, LeadUpdate
from .service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"], dependencies=[Depends(require(Permission.SALES_VIEW))])

Writer = Annotated[User, Depends(require(Permission.SALES_EDIT_OWN))]


@router.get("/summary", response_model=LeadSummary)
async def leads_summary(session: SessionDep, user: CurrentUser) -> LeadSummary:
    """What is in the funnel: a count per status, plus the leads nobody has picked up."""
    return await LeadService(session).summary()


@router.get("", response_model=LeadPage)
async def list_leads(
    session: SessionDep, user: CurrentUser, page: PageDep,
    view: Literal["all", "mine", "unassigned"] = "all",
    status_: Annotated[Literal["new", "contacted", "qualified", "unqualified", "converted", "all"],
                       Query(alias="status")] = "all",
    source: str | None = None, owner_id: int | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> LeadPage:
    return await LeadService(session).list(
        user, page, view=view, status=None if status_ == "all" else status_, source=source,
        owner_id=owner_id, q=q)


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(session: SessionDep, actor: Writer, data: LeadCreate) -> LeadOut:
    return await LeadService(session).create(data, actor)


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(session: SessionDep, lead_id: int) -> LeadOut:
    return await LeadService(session).get(lead_id)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(session: SessionDep, actor: CurrentUser, lead_id: int, data: LeadUpdate) -> LeadOut:
    return await LeadService(session).update(lead_id, data, actor)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(session: SessionDep, actor: CurrentUser, lead_id: int) -> None:
    await LeadService(session).delete(lead_id, actor)


@router.post("/{lead_id}/convert", response_model=LeadOut)
async def convert_lead(session: SessionDep, actor: CurrentUser, lead_id: int, data: LeadConvert) -> LeadOut:
    """Make the customer (reusing one with the same email) and its first deal, then close the lead."""
    return await LeadService(session).convert(lead_id, data, actor)
