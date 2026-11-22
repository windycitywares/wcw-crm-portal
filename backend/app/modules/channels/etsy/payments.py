"""What the business owes a supplier for an Etsy order, and whether it has been paid (pure).

Owed = purchase cost + actual shipping cost: the supplier buys and ships the item (owner's set-up), so both are paid to
them. The amount actually paid is recorded separately and can differ (a discount, a combined invoice); the order's costs
are never changed by a payment.
"""

from decimal import Decimal

PENDING, SETTLED, COST_MISSING, NOT_DUE = "pending", "settled", "cost_missing", "not_due"
LABELS = {PENDING: "Pending", SETTLED: "Settled", COST_MISSING: "Cost missing", NOT_DUE: "Not due (cancelled)"}


def owed(purchase_cost: Decimal | None, shipping_cost: Decimal | None) -> Decimal | None:
    if purchase_cost is None:
        return None
    return (purchase_cost + (shipping_cost or Decimal("0"))).quantize(Decimal("0.01"))


def status(*, order_status: str, purchase_cost: Decimal | None, paid: bool) -> str:
    if paid:
        return SETTLED
    if order_status == "cancelled":
        return NOT_DUE
    if purchase_cost is None:
        return COST_MISSING
    return PENDING
