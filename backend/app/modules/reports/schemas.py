from pydantic import BaseModel

from app.modules.campaigns.schemas import CampaignStats
from app.modules.sales.schemas import SalesSummary
from app.modules.tickets.schemas import TicketSummary


class ReportBucket(BaseModel):
    label: str
    count: int


class TrendPoint(BaseModel):
    date: str  # ISO date
    count: int
    value: str | int | float | None = None


class TrendReport(BaseModel):
    points: list[TrendPoint]


class CustomerReport(BaseModel):
    total: int
    by_type: list[ReportBucket]
    by_source: list[ReportBucket]
    by_status: list[ReportBucket]


class TicketReport(BaseModel):
    total: int
    by_type: list[ReportBucket]
    by_status: list[ReportBucket]
    by_priority: list[ReportBucket]
    first_response_breached: int
    resolution_breached: int
    open_overdue: int


class SupplierReport(BaseModel):
    total: int
    by_type: list[ReportBucket]
    by_status: list[ReportBucket]
    average_rating: float | None


class ReportsOverview(BaseModel):
    sales: SalesSummary
    tickets: TicketSummary
    campaigns: CampaignStats
    active_customers: int
    active_suppliers: int