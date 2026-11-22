"""Profit of an Etsy order (pure rules).

Revenue = items + shipping charged − discounts. Sales tax is collected for the state and is not revenue.
Costs = purchase cost + actual shipping cost + Etsy fees + replacements and refunds. Original numbers are never overwritten;
extra costs are passed in separately. Missing figures count as zero but are reported so the screen can say "incomplete".
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def _d(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal("0")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Profit:
    revenue: Decimal
    total_cost: Decimal
    net_profit: Decimal
    margin_pct: Decimal | None  # None when there is no revenue
    missing: tuple[str, ...]  # what is not entered yet: "purchase_cost", "shipping_cost", "etsy_fees"
    fees_estimated: bool  # always False: fees come from Etsy or stay missing, never guessed


def revenue(items_total, shipping_charged, discounts) -> Decimal:
    return _money(_d(items_total) + _d(shipping_charged) - _d(discounts))


def compute(
    *, items_total, shipping_charged, discounts, purchase_cost=None, shipping_cost=None, etsy_fees=None,
    extra_costs=0,
) -> Profit:
    rev = revenue(items_total, shipping_charged, discounts)
    cost = _d(purchase_cost) + _d(shipping_cost) + _d(etsy_fees) + _d(extra_costs)
    cost = _money(cost)
    net = _money(rev - cost)
    margin = _money(net / rev * 100) if rev > 0 else None
    missing = tuple(
        name for name, v in (("purchase_cost", purchase_cost), ("shipping_cost", shipping_cost), ("etsy_fees", etsy_fees))
        if v is None
    )
    return Profit(rev, cost, net, margin, missing, False)


def days_to_ship(paid_at: datetime | None, shipped_at: datetime | None) -> int | None:
    """Whole days from payment to shipping; None until both are known."""
    if paid_at is None or shipped_at is None:
        return None
    return max(0, (shipped_at - paid_at).days)
