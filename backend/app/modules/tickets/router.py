from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, EmailSenderDep, SessionDep, require
from app.modules.users.models import User

from .schemas import SlaPolicyCreate, SlaPolicyOut, SlaPolicyUpdate, TicketCreate, TicketMessageIn, TicketMessageOut, TicketOut, TicketPage, TicketSummary, TicketUpdate
from .service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(require(Permission.TICKETS_VIEW))])

Editor = Annotated[User, Depends(require(Permission.TICKETS_EDIT))]
SlaAdmin = Annotated[User, Depends(require(Permission.LOOKUPS_MANAGE))]


# ---- static paths first, so they aren't read as a ticket id --------------------------------

@router.get("", response_model=TicketPage)
async def list_tickets(
    session: SessionDep, user: CurrentUser, page: PageDep,
    view: Literal["all", "mine", "unassigned"] = "all",
    state: Literal["unresolved", "resolved", "all"] = "unresolved",
    status_: Annotated[Literal["new", "open", "pending", "resolved", "closed"] | None, Query(alias="status")] = None,
    priority: str | None = None, type: str | None = None, customer_id: int | None = None,
    breached: bool | None = None, q: Annotated[str | None, Query(max_length=100)] = None,
) -> TicketPage:
    return await TicketService(session).list(
        user, page, view=view, state=state, status=status_, priority=priority, ticket_type=type,
        customer_id=customer_id, breached=breached, q=q)


@router.get("/summary", response_model=TicketSummary)
async def ticket_summary(session: SessionDep, user: CurrentUser) -> TicketSummary:
    """Counts for the queue header and the sidebar badge."""
    return await TicketService(session).summary(user)


@router.get("/sla-policies", response_model=list[SlaPolicyOut])
async def list_sla_policies(session: SessionDep) -> list[SlaPolicyOut]:
    return await TicketService(session).list_sla()


@router.post("/sla-policies", response_model=SlaPolicyOut, status_code=status.HTTP_201_CREATED)
async def create_sla_policy(session: SessionDep, actor: SlaAdmin, data: SlaPolicyCreate) -> SlaPolicyOut:
    return await TicketService(session).create_sla(data, actor)


@router.patch("/sla-policies/{policy_id}", response_model=SlaPolicyOut)
async def update_sla_policy(session: SessionDep, actor: SlaAdmin, policy_id: int, data: SlaPolicyUpdate) -> SlaPolicyOut:
    return await TicketService(session).update_sla(policy_id, data, actor)


# ---- tickets -------------------------------------------------------------------------------

@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(session: SessionDep, actor: Editor, data: TicketCreate) -> TicketOut:
    return await TicketService(session).create(data, actor)


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(session: SessionDep, ticket_id: int) -> TicketOut:
    return await TicketService(session).get(ticket_id)


@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(session: SessionDep, actor: Editor, ticket_id: int, data: TicketUpdate) -> TicketOut:
    return await TicketService(session).update(ticket_id, data, actor)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(session: SessionDep, actor: Editor, ticket_id: int) -> None:
    await TicketService(session).delete(ticket_id, actor)


@router.get("/{ticket_id}/messages", response_model=list[TicketMessageOut])
async def list_messages(session: SessionDep, ticket_id: int) -> list[TicketMessageOut]:
    return await TicketService(session).messages_for(ticket_id)


@router.post("/{ticket_id}/messages", response_model=TicketMessageOut, status_code=status.HTTP_201_CREATED)
async def add_message(session: SessionDep, actor: Editor, sender: EmailSenderDep, ticket_id: int,
                      data: TicketMessageIn) -> TicketMessageOut:
    """Add an internal note (`kind: note`) or email the customer a reply (`kind: reply`)."""
    return await TicketService(session).add_message(ticket_id, data, actor, sender=sender)
