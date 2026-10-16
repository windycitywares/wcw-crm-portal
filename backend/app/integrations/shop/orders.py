from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ShopOrder


class ShopOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    status: str
    payment_status: str
    currency: str
    grand_total: Decimal
    refunded_total: Decimal
    placed_at: datetime | None


async def orders_for_customer(session: AsyncSession, customer_id: int, limit: int = 100) -> list[ShopOrderOut]:
    rows = (await session.execute(
        select(ShopOrder).where(ShopOrder.customer_id == customer_id)
        .order_by(ShopOrder.placed_at.desc().nullslast(), ShopOrder.id.desc()).limit(limit)
    )).scalars()
    return [ShopOrderOut.model_validate(r) for r in rows]
