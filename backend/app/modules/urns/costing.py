"""What an order cost, worked out from what was sold: each line's urn and sizes (its approved variation), the
supplier's price per piece on the order's date, and the extras in force that day.

The result is split in two: the **supplier's** part (their prices plus the extras marked theirs — what they are
owed) and **ours** (our own extras — profit only). Anything that can't be priced is listed in `missing` and the
total is then not used, so a half-known cost never looks like a real one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CostExtra, Urn, UrnSize
from .service import UrnService

CENT = Decimal("0.01")


def _money(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Line:
    label: str
    amount: Decimal
    party: str      # supplier | ours
    kind: str       # price | extra | adjustment

    def out(self) -> dict[str, Any]:
        return {"label": self.label, "amount": str(self.amount), "party": self.party, "kind": self.kind}


@dataclass
class Costing:
    lines: list[Line] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    supplier_ids: set[int] = field(default_factory=set)
    on: date | None = None

    @property
    def complete(self) -> bool:
        return not self.missing and bool(self.lines)

    def total(self, party: str) -> Decimal:
        return _money(sum((l.amount for l in self.lines if l.party == party), Decimal("0")))

    def out(self) -> dict[str, Any]:
        return {"lines": [l.out() for l in self.lines], "missing": self.missing, "on": str(self.on) if self.on else None,
                "supplier": str(self.total("supplier")), "ours": str(self.total("ours")), "complete": self.complete}


def _in_force(e: CostExtra, on: date) -> bool:
    return e.effective_from <= on and (e.effective_to is None or e.effective_to >= on)


class OrderCosting:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.urns = UrnService(session)

    async def compute(self, items: list[dict[str, Any]], on: date) -> Costing:
        """`items`: [{"listing_external_id", "variations", "sku", "quantity", "title"}]."""
        result = Costing(on=on)
        labels = {s.code: s.label for s in (await self.session.execute(select(UrnSize))).scalars()}
        matched: list[tuple[dict[str, Any], Urn, dict[str, int]]] = []
        for it in items:
            v = await self.urns.match(it.get("listing_external_id"), it.get("variations"), it.get("sku"))
            if v is None:
                result.missing.append(f"“{(it.get('title') or 'An item')[:60]}” isn't matched to an approved urn variation")
                continue
            urn = await self.session.get(Urn, v.urn_id)
            q = {k: int(n) for k, n in (v.quantities or {}).items() if int(n) > 0}
            matched.append((it, urn, q))
            if urn.supplier_id:
                result.supplier_ids.add(urn.supplier_id)
        if not matched:
            return result
        urn_ids = list({u.id for _, u, _ in matched})
        prices = await self.urns.prices(urn_ids)
        extras = [e for e in (await self.session.execute(select(CostExtra).where(
            or_(CostExtra.urn_id.is_(None), CostExtra.urn_id.in_(urn_ids))).order_by(CostExtra.id))).scalars()
            if _in_force(e, on)]
        pieces_by_urn: dict[int, dict[str, int]] = {}
        price_by_urn: dict[int, dict[str, Decimal]] = {}
        for it, urn, q in matched:
            n = max(int(it.get("quantity") or 1), 1)
            parts, amount = [], Decimal("0")
            for code, per in q.items():
                p = self.urns.price_on(prices.get(urn.id, []), code, on)
                if p is None:
                    result.missing.append(f"No {labels.get(code, code)} price for {urn.name} on {on:%b %-d, %Y}")
                    continue
                pieces = per * n
                amount += p.amount * pieces
                parts.append(f"{pieces} × {labels.get(code, code)} at ${p.amount:.2f}")
                pieces_by_urn.setdefault(urn.id, {}).setdefault(code, 0)
                pieces_by_urn[urn.id][code] += pieces
                price_by_urn.setdefault(urn.id, {}).setdefault(code, p.amount)
            if parts:
                result.lines.append(Line(f"{urn.name}: {', '.join(parts)}", _money(amount), "supplier", "price"))
        # Extras: per piece (of one size or any), a % of the supplier price, or once per order.
        once_done: set[int] = set()
        for e in extras:
            for urn_id, pieces in pieces_by_urn.items():
                if e.urn_id is not None and e.urn_id != urn_id:
                    continue
                codes = [c for c in pieces if e.size_code in (None, c)]
                if e.applies == "order":
                    if e.id in once_done or not codes:
                        continue
                    once_done.add(e.id)
                    result.lines.append(Line(e.name, _money(e.value), e.party, "extra"))
                    continue
                count = sum(pieces[c] for c in codes)
                if not count:
                    continue
                if e.mode == "percent":
                    base = sum((price_by_urn[urn_id][c] * pieces[c] for c in codes), Decimal("0"))
                    amount = _money(base * e.value / Decimal(100))
                    label = f"{e.name} ({format(e.value.normalize(), 'f')}%)"
                else:
                    amount = _money(e.value * count)
                    label = f"{e.name} ({count} × ${e.value:.2f})"
                if amount:
                    result.lines.append(Line(label, amount, e.party, "extra"))
        return result
