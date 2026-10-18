from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.models import Customer
from app.modules.suppliers.models import Supplier
from app.modules.tickets.models import OPEN_STATUSES, Ticket


class ReportsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def total(self, model: Any, *conditions: Any) -> int:
        stmt = select(func.count()).select_from(model).where(model.deleted_at.is_(None), *conditions)
        return int((await self.session.execute(stmt)).scalar_one())

    async def breakdown(self, model: Any, column: Any) -> list[dict[str, Any]]:
        stmt = (
            select(column, func.count(model.id))
            .where(model.deleted_at.is_(None))
            .group_by(column)
            .order_by(func.count(model.id).desc(), column.asc().nulls_last())
        )
        return [
            {"label": value if value is not None else "Not set", "count": int(count)}
            for value, count in (await self.session.execute(stmt)).all()
        ]

    async def customer_report(self) -> dict[str, Any]:
        return {
            "total": await self.total(Customer),
            "by_type": await self.breakdown(Customer, Customer.customer_type),
            "by_source": await self.breakdown(Customer, Customer.source),
            "by_status": await self.breakdown(Customer, Customer.status),
        }

    async def ticket_report(self, now: datetime) -> dict[str, Any]:
        return {
            "total": await self.total(Ticket),
            "by_type": await self.breakdown(Ticket, Ticket.ticket_type),
            "by_status": await self.breakdown(Ticket, Ticket.status),
            "by_priority": await self.breakdown(Ticket, Ticket.priority),
            "first_response_breached": await self.total(Ticket, Ticket.first_response_breached.is_(True)),
            "resolution_breached": await self.total(Ticket, Ticket.resolve_breached.is_(True)),
            "open_overdue": await self.total(
                Ticket, Ticket.status.in_(OPEN_STATUSES), Ticket.resolve_due_at < now,
            ),
        }

    async def supplier_report(self) -> dict[str, Any]:
        average = await self.session.scalar(
            select(func.avg(Supplier.rating)).where(Supplier.deleted_at.is_(None), Supplier.rating.is_not(None))
        )
        return {
            "total": await self.total(Supplier),
            "by_type": await self.breakdown(Supplier, Supplier.supplier_type),
            "by_status": await self.breakdown(Supplier, Supplier.status),
            "average_rating": float(average) if average is not None else None,
        }