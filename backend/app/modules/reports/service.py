from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.service import CampaignService
from app.modules.customers.models import Customer
from app.modules.sales.service import SalesService
from app.modules.suppliers.models import Supplier
from app.modules.tickets.service import TicketService

from .repository import ReportsRepository
from .schemas import CustomerReport, ReportsOverview, SupplierReport, TicketReport


class ReportsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReportsRepository(session)

    async def overview(self, user, *, campaign_days: int = 30) -> ReportsOverview:
        return ReportsOverview(
            sales=await SalesService(self.session).summary(user),
            tickets=await TicketService(self.session).summary(user),
            campaigns=await CampaignService(self.session).stats(days=campaign_days),
            active_customers=await self.repo.total(Customer, Customer.status == "active"),
            active_suppliers=await self.repo.total(Supplier, Supplier.status == "active"),
        )

    async def customers(self) -> CustomerReport:
        return CustomerReport.model_validate(await self.repo.customer_report())

    async def tickets(self) -> TicketReport:
        return TicketReport.model_validate(await self.repo.ticket_report(datetime.now(timezone.utc)))

    async def suppliers(self) -> SupplierReport:
        return SupplierReport.model_validate(await self.repo.supplier_report())