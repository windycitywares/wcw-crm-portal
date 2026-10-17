from sqlalchemy import update

from app.core.entities import RecordsMerged

from .models import ShopEvent, ShopOrder
from .repository import ShopOrderRepository


async def move_orders(event: RecordsMerged, session) -> None:
    """A merged customer's shop orders move to the surviving customer, whose totals are recomputed."""
    if event.entity_type != "customer":
        return
    from app.modules.customers.service import CustomerService

    await session.execute(update(ShopOrder).where(ShopOrder.customer_id == event.from_id).values(customer_id=event.into_id))
    await session.execute(update(ShopEvent).where(ShopEvent.customer_id == event.from_id).values(customer_id=event.into_id))
    count, total, first, last = await ShopOrderRepository(session).stats(event.into_id)
    customers = CustomerService(session)
    await customers.set_order_stats(event.into_id, count=count, total=total, first=first, last=last)
    await customers.set_order_stats(event.from_id, count=0, total=0, first=None, last=None)
