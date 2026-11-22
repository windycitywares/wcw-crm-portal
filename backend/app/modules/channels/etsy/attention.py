"""Why an Etsy order needs someone's attention (pure; the list filter in channels/orders.py mirrors it in SQL).

Phase 1 covers what the shop already knows; tracking failures, unanswered messages and the email alerts come in phase 3.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from . import profit as etsy_profit

NOT_PURCHASED_AFTER = timedelta(hours=24)
WAITING = ("new", "purchased")  # still to be sent
DONE_SHIPPING = ("shipped", "delivered", "closed")

REASONS = {
    "not_purchased": "Paid more than 24 hours ago and not purchased yet",
    "late": "Past Etsy's ship-by date and not shipped",
    "cost_missing": "Purchase cost missing",
    "shipping_cost_missing": "Shipping cost missing",
    "negative_profit": "Losing money on this order",
}


@dataclass(frozen=True)
class OrderFacts:
    status: str
    paid_at: datetime | None
    ship_by: datetime | None
    purchase_cost: Decimal | None
    shipping_cost: Decimal | None
    etsy_fees: Decimal | None
    items_total: Decimal
    shipping_charged: Decimal
    discounts: Decimal
    past_order: bool = False  # already shipped when it arrived from Etsy (kept for history, never flagged)


def reasons(o: OrderFacts, now: datetime) -> list[str]:
    if o.status == "cancelled" or o.past_order:
        return []
    out = []
    if o.status == "new" and o.paid_at and now - o.paid_at > NOT_PURCHASED_AFTER:
        out.append("not_purchased")
    if o.status in WAITING and o.ship_by and now > o.ship_by:
        out.append("late")
    if o.purchase_cost is None:
        out.append("cost_missing")
    if o.shipping_cost is None and o.status in DONE_SHIPPING:
        out.append("shipping_cost_missing")
    if o.purchase_cost is not None:
        p = etsy_profit.compute(items_total=o.items_total, shipping_charged=o.shipping_charged, discounts=o.discounts,
                                purchase_cost=o.purchase_cost, shipping_cost=o.shipping_cost, etsy_fees=o.etsy_fees)
        if p.net_profit < 0:
            out.append("negative_profit")
    return out
