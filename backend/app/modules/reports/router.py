from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require

from .schemas import CustomerReport, ReportsOverview, SupplierReport, TicketReport
from .service import ReportsService

router = APIRouter(prefix="/reports", tags=["reports"],
                   dependencies=[Depends(require(Permission.REPORTS_VIEW))])


@router.get("/overview", response_model=ReportsOverview)
async def reports_overview(
    session: SessionDep,
    user: CurrentUser,
    campaign_days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> ReportsOverview:
    return await ReportsService(session).overview(user, campaign_days=campaign_days)


@router.get("/customers", response_model=CustomerReport)
async def customer_report(session: SessionDep) -> CustomerReport:
    return await ReportsService(session).customers()


@router.get("/tickets", response_model=TicketReport)
async def ticket_report(session: SessionDep) -> TicketReport:
    return await ReportsService(session).tickets()


@router.get("/suppliers", response_model=SupplierReport)
async def supplier_report(session: SessionDep) -> SupplierReport:
    return await ReportsService(session).suppliers()