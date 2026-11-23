"""Numbers for one shop's dashboard (Etsy first), from plain order rows. Pure: no database, no clock.

Money rules are the order rules (etsy/profit.py): revenue = items + shipping charged − discounts; tax is not
revenue. Profit and margin are only counted for orders that have a purchase cost — an order without one would show its
whole revenue as profit — and the share of orders that do is reported as "cost coverage", so a thin number is visible.
Etsy fees are not included until a later phase (the screen says so).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from . import profit as etsy_profit

ZERO = Decimal("0")


@dataclass(frozen=True)
class Item:
    listing_id: int | None
    title: str
    quantity: int
    line_total: Decimal


@dataclass(frozen=True)
class Order:
    status: str
    ordered_at: datetime
    paid_at: datetime | None
    shipped_at: datetime | None
    ship_by: datetime | None
    items_total: Decimal
    shipping_charged: Decimal
    discounts: Decimal
    purchase_cost: Decimal | None
    shipping_cost: Decimal | None
    etsy_fees: Decimal | None
    supplier: int | None  # supplier account id
    state: str | None
    country: str | None
    items: tuple[Item, ...] = field(default_factory=tuple)
    other_costs: Decimal | None = None  # our own extras (packaging, labels…): profit only

    @property
    def revenue(self) -> Decimal:
        return etsy_profit.revenue(self.items_total, self.shipping_charged, self.discounts)

    @property
    def has_cost(self) -> bool:
        return self.purchase_cost is not None

    @property
    def cost(self) -> Decimal:
        return ((self.purchase_cost or ZERO) + (self.shipping_cost or ZERO) + (self.etsy_fees or ZERO)
                + (self.other_costs or ZERO))

    @property
    def profit(self) -> Decimal:
        return self.revenue - self.cost


def _f(v: Decimal | float | int | None) -> float:
    return round(float(v or 0), 2)


@dataclass
class Totals:
    orders: int = 0
    cancelled: int = 0
    units: int = 0
    revenue: Decimal = ZERO
    costed_orders: int = 0
    costed_revenue: Decimal = ZERO
    cost: Decimal = ZERO
    profit: Decimal = ZERO
    shipped: int = 0
    ship_days: int = 0
    on_time: int = 0
    with_ship_by: int = 0

    def add(self, o: Order) -> None:
        if o.status == "cancelled":
            self.cancelled += 1
            return
        self.orders += 1
        self.units += sum(i.quantity for i in o.items)
        self.revenue += o.revenue
        if o.has_cost:
            self.costed_orders += 1
            self.costed_revenue += o.revenue
            self.cost += o.cost
            self.profit += o.profit
        if o.shipped_at and o.paid_at:
            self.shipped += 1
            self.ship_days += max(0, (o.shipped_at - o.paid_at).days)
            if o.ship_by:
                self.with_ship_by += 1
                self.on_time += o.shipped_at <= o.ship_by

    def summary(self) -> dict[str, float | int | None]:
        return {
            "orders": self.orders,
            "cancelled": self.cancelled,
            "units": self.units,
            "revenue": _f(self.revenue),
            "aov": _f(self.revenue / self.orders) if self.orders else None,
            "cost": _f(self.cost),
            "profit": _f(self.profit) if self.costed_orders else None,
            "margin": round(float(self.profit / self.costed_revenue), 6) if self.costed_revenue else None,
            "cost_coverage": round(self.costed_orders / self.orders, 6) if self.orders else None,
            "costed_orders": self.costed_orders,
            "avg_days_to_ship": round(self.ship_days / self.shipped, 1) if self.shipped else None,
            "on_time_rate": round(self.on_time / self.with_ship_by, 6) if self.with_ship_by else None,
            "cancel_rate": round(self.cancelled / (self.orders + self.cancelled), 6) if self.orders + self.cancelled else None,
        }


def build(orders: Iterable[Order], previous: Iterable[Order], buckets: list[date], bucket_of: Callable[[datetime], date]) -> dict[str, Any]:
    orders = list(orders)
    now_t, prev_t = Totals(), Totals()
    for o in orders:
        now_t.add(o)
    for o in previous:
        prev_t.add(o)

    per_bucket: dict[date, Totals] = defaultdict(Totals)
    products: dict[Any, dict[str, Any]] = {}
    suppliers: dict[int | None, Totals] = defaultdict(Totals)
    places: dict[str, dict[str, Any]] = {}
    statuses: dict[str, int] = defaultdict(int)
    for o in orders:
        statuses[o.status] += 1
        per_bucket[bucket_of(o.ordered_at)].add(o)
        if o.status == "cancelled":
            continue
        suppliers[o.supplier].add(o)
        place = o.state if (o.country or "US") == "US" and o.state else (o.country or "Unknown")
        p = places.setdefault(place, {"label": place, "orders": 0, "revenue": ZERO})
        p["orders"] += 1
        p["revenue"] += o.revenue
        lines_total = sum((i.line_total for i in o.items), ZERO)
        for i in o.items:
            key = i.listing_id or i.title
            row = products.setdefault(key, {"listing_id": i.listing_id, "title": i.title, "units": 0, "orders": 0,
                                            "revenue": ZERO, "profit": ZERO, "costed": 0})
            share = (i.line_total / lines_total) if lines_total else Decimal(1) / len(o.items)
            row["units"] += i.quantity
            row["orders"] += 1
            row["revenue"] += o.revenue * share
            if o.has_cost:  # an order's profit is split over its items by their share of the price
                row["profit"] += o.profit * share
                row["costed"] += 1

    series = []
    for b in buckets:
        t = per_bucket.get(b, Totals())
        series.append({"bucket": b.isoformat(), "orders": t.orders, "units": t.units, "revenue": _f(t.revenue), "cost": _f(t.cost),
                       "profit": _f(t.profit) if t.costed_orders else None})

    top_products = sorted(products.values(), key=lambda r: r["revenue"], reverse=True)[:10]
    return {
        "totals": now_t.summary(),
        "previous": prev_t.summary(),
        "series": series,
        "statuses": dict(statuses),
        "top_products": [{**r, "revenue": _f(r["revenue"]), "profit": _f(r["profit"]) if r["costed"] else None,
                          "margin": round(float(r["profit"] / r["revenue"]), 6) if r["costed"] and r["revenue"] else None}
                         for r in top_products],
        "suppliers": sorted(
            ({"supplier_account_id": key, **t.summary()} for key, t in suppliers.items()),
            key=lambda r: r["revenue"], reverse=True),
        "places": [{**p, "revenue": _f(p["revenue"])} for p in sorted(places.values(), key=lambda p: p["revenue"], reverse=True)[:10]],
    }
