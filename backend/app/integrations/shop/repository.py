from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, or_, select

from app.shared.repository import BaseRepository

from .models import DONE, FAILED, IGNORED, PENDING, ShopEvent, ShopOrder

# Orders that count towards a customer's totals.
COUNTED = ("paid", "processing", "shipped", "delivered", "refunded")


class ShopEventRepository(BaseRepository[ShopEvent]):
    model = ShopEvent

    async def by_event_id(self, event_id: str) -> ShopEvent | None:
        return (await self.session.execute(select(ShopEvent).where(ShopEvent.event_id == event_id))).scalars().first()

    def recent(self, status: str | None = None):
        stmt = select(ShopEvent)
        if status:
            stmt = stmt.where(ShopEvent.status == status)
        return stmt.order_by(ShopEvent.id.desc())

    async def due(self, *, max_attempts: int, older_than: datetime, limit: int) -> list[ShopEvent]:
        stmt = (select(ShopEvent)
                .where(or_(ShopEvent.status == FAILED, ShopEvent.status == PENDING),
                       ShopEvent.attempts < max_attempts, ShopEvent.received_at < older_than)
                .order_by(ShopEvent.id).limit(limit))
        return list((await self.session.execute(stmt)).scalars())

    async def counts_since(self, since: datetime) -> dict[str, int]:
        stmt = select(ShopEvent.status, func.count()).where(ShopEvent.received_at >= since).group_by(ShopEvent.status)
        return {status: n for status, n in (await self.session.execute(stmt)).all()}

    async def last_received(self) -> datetime | None:
        return (await self.session.execute(select(func.max(ShopEvent.received_at)))).scalar()

    async def purge(self, before: datetime) -> int:
        res = await self.session.execute(
            delete(ShopEvent).where(ShopEvent.status.in_((DONE, IGNORED)), ShopEvent.received_at < before))
        return res.rowcount or 0


class ShopOrderRepository(BaseRepository[ShopOrder]):
    model = ShopOrder

    async def get_order(self, order_id: int) -> ShopOrder | None:
        return await self.session.get(ShopOrder, order_id)

    async def by_number(self, number: str | None) -> ShopOrder | None:
        """Find a copy of an order by the number the customer quotes (shop numbers are unique, any case)."""
        number = (number or "").strip()
        if not number:
            return None
        stmt = select(ShopOrder).where(func.lower(ShopOrder.number) == number.lower())
        return (await self.session.execute(stmt)).scalars().first()

    async def stats(self, customer_id: int) -> tuple[int, Decimal, datetime | None, datetime | None]:
        stmt = select(
            func.count(), func.coalesce(func.sum(ShopOrder.grand_total - ShopOrder.refunded_total), 0),
            func.min(ShopOrder.placed_at), func.max(ShopOrder.placed_at),
        ).where(ShopOrder.customer_id == customer_id, ShopOrder.status.in_(COUNTED))
        count, total, first, last = (await self.session.execute(stmt)).one()
        return int(count), Decimal(total), first, last
