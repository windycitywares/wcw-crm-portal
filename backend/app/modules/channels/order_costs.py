"""An order's costs from what was sold (SKU costing in the urns module) plus the team's one-off adjustments.

`purchase_cost` is the supplier's part — their prices, their extras and supplier adjustments — so what a supplier
is owed follows it unchanged. `other_costs` is ours and only moves profit. A cost someone typed in by hand
(`cost_source = manual`) is never overwritten; "Use the SKU costs" switches it back. An order the supplier has
already been paid for is never recalculated.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit.service import AuditService

from .models import ChannelOrder, ChannelOrderAdjustment, ChannelOrderEvent, ChannelOrderItem


def _date(o: ChannelOrder) -> date:
    return (o.paid_at or o.ordered_at or datetime.now(timezone.utc)).date()


def item_dicts(items: list[ChannelOrderItem]) -> list[dict[str, Any]]:
    return [{"listing_external_id": i.listing_external_id, "variations": i.variations, "sku": i.sku,
             "quantity": i.quantity, "title": i.title} for i in items]


async def supplier_account(session: AsyncSession, supplier_ids: set[int]) -> int | None:
    """The one supplier's account (orders point at the supplier's account), when the order has exactly one."""
    if len(supplier_ids) != 1:
        return None
    from app.modules.suppliers.models import Supplier

    sup = await session.get(Supplier, next(iter(supplier_ids)))
    return sup.account_id if sup else None


class OrderCostService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _order(self, order_id: int) -> ChannelOrder:
        o = await self.session.get(ChannelOrder, order_id)
        if o is None:
            raise NotFoundError("Order not found")
        return o

    async def _items(self, order_id: int) -> list[ChannelOrderItem]:
        return list((await self.session.execute(select(ChannelOrderItem).where(
            ChannelOrderItem.order_id == order_id).order_by(ChannelOrderItem.id))).scalars())

    async def _adjustments(self, order_id: int) -> list[ChannelOrderAdjustment]:
        return list((await self.session.execute(select(ChannelOrderAdjustment).where(
            ChannelOrderAdjustment.order_id == order_id).order_by(ChannelOrderAdjustment.id))).scalars())

    async def compute(self, o: ChannelOrder) -> dict[str, Any]:
        """The SKU costing for the order today, with its adjustments — not saved."""
        from app.modules.urns.costing import Line, OrderCosting

        costing = await OrderCosting(self.session).compute(item_dicts(await self._items(o.id)), _date(o))
        for a in await self._adjustments(o.id):
            costing.lines.append(Line(a.label, a.amount, a.party, "adjustment"))
        out = costing.out()
        out["supplier_account_id"] = await supplier_account(self.session, costing.supplier_ids)
        return out

    def _event(self, o: ChannelOrder, actor, message: str) -> None:
        self.session.add(ChannelOrderEvent(order_id=o.id, kind="costs", message=message[:500], source="team",
                                           actor_id=actor.id if actor else None,
                                           actor_name=(getattr(actor, "full_name", None) or getattr(actor, "email", None))
                                           if actor else "CRM"))

    def _write(self, o: ChannelOrder, result: dict[str, Any]) -> bool:
        """Put a complete costing on the order. False (and nothing changed) when it isn't complete."""
        if not result["complete"]:
            return False
        o.purchase_cost, o.other_costs = Decimal(result["supplier"]), Decimal(result["ours"])
        o.cost_breakdown = {k: result[k] for k in ("lines", "on", "supplier", "ours")}
        o.cost_source, o.costs_prefilled = "sku", True
        if o.supplier_account_id is None and result.get("supplier_account_id"):
            o.supplier_account_id = result["supplier_account_id"]
        return True

    async def breakdown(self, order_id: int) -> dict[str, Any]:
        o = await self._order(order_id)
        live = await self.compute(o)
        return {
            "source": o.cost_source, "saved": o.cost_breakdown or None,
            "purchase_cost": o.purchase_cost, "other_costs": o.other_costs,
            "live": live, "differs": live["complete"] and (
                Decimal(live["supplier"]) != (o.purchase_cost or Decimal("-1"))
                or Decimal(live["ours"]) != (o.other_costs or Decimal("0"))),
            "locked": o.supplier_paid_at is not None,
            "adjustments": [{"id": a.id, "label": a.label, "amount": a.amount, "party": a.party, "note": a.note,
                             "created_at": a.created_at} for a in await self._adjustments(o.id)],
        }

    def _unlocked(self, o: ChannelOrder) -> None:
        if o.supplier_paid_at is not None:
            raise ConflictError("The supplier has been paid for this order: undo the payment first to change its costs")

    async def recalculate(self, order_id: int, actor) -> dict[str, Any]:
        """Use the SKU costs (also after a hand-typed cost: this switches it back)."""
        o = await self._order(order_id)
        self._unlocked(o)
        result = await self.compute(o)
        if not result["complete"]:
            raise ValidationFailedError("Can't work out the costs yet: " + "; ".join(result["missing"][:3]))
        old = (o.purchase_cost, o.other_costs)
        self._write(o, result)
        self._event(o, actor, f"Costs from SKUs: supplier ${o.purchase_cost:.2f}, ours ${o.other_costs:.2f}"
                    + (f" (was ${old[0]:.2f})" if old[0] is not None and old[0] != o.purchase_cost else ""))
        await self.audit.record("channel.order_costs", actor=actor, entity_type="channel_order", entity_id=o.id,
                                changes={"purchase_cost": [str(old[0]) if old[0] is not None else None, str(o.purchase_cost)],
                                         "other_costs": [str(old[1]) if old[1] is not None else None, str(o.other_costs)]})
        await self.session.commit()
        return await self.breakdown(o.id)

    async def add_adjustment(self, order_id: int, values: dict[str, Any], actor) -> dict[str, Any]:
        o = await self._order(order_id)
        self._unlocked(o)
        if o.cost_source == "manual":
            raise ValidationFailedError("This order's cost was typed in by hand. Use the SKU costs first, or change "
                                        "the typed cost.")
        amount = Decimal(values["amount"])
        if amount == 0:
            raise ValidationFailedError("An adjustment needs an amount (minus to subtract)")
        note = (values.get("note") or "").strip()
        if not note:
            raise ValidationFailedError("Say why, in a short note")
        a = ChannelOrderAdjustment(order_id=o.id, label=values["label"].strip()[:120], amount=amount,
                                   party=values.get("party") or "supplier", note=note[:500], created_by=actor.id)
        self.session.add(a)
        await self.session.flush()
        self._event(o, actor, f"Adjustment {a.label}: {'+' if amount > 0 else '−'}${abs(amount):.2f} "
                              f"({'supplier' if a.party == 'supplier' else 'ours'}) — {note}")
        await self._refresh_totals(o)
        await self.audit.record("channel.order_adjustment", actor=actor, entity_type="channel_order", entity_id=o.id,
                                changes={"label": a.label, "amount": str(amount), "party": a.party, "note": note})
        await self.session.commit()
        return await self.breakdown(o.id)

    async def remove_adjustment(self, order_id: int, adjustment_id: int, actor) -> dict[str, Any]:
        o = await self._order(order_id)
        self._unlocked(o)
        a = await self.session.get(ChannelOrderAdjustment, adjustment_id)
        if a is None or a.order_id != o.id:
            raise NotFoundError("Adjustment not found")
        await self.session.delete(a)
        await self.session.flush()
        self._event(o, actor, f"Adjustment {a.label} (${a.amount:.2f}) removed")
        await self._refresh_totals(o)
        await self.audit.record("channel.order_adjustment_remove", actor=actor, entity_type="channel_order",
                                entity_id=o.id, changes={"label": a.label, "amount": str(a.amount)})
        await self.session.commit()
        return await self.breakdown(o.id)

    async def _refresh_totals(self, o: ChannelOrder) -> None:
        if o.cost_source == "manual":
            return
        self._write(o, await self.compute(o))

    async def on_new_order(self, o: ChannelOrder) -> bool:
        """Called by the sync when an order arrives: cost it from its SKUs when every line can be priced."""
        return self._write(o, await self.compute(o))

    async def bulk_preview(self, limit: int = 500) -> list[dict[str, Any]]:
        """Orders not yet paid to the supplier and not typed by hand, whose SKU costs would differ from today's."""
        rows = (await self.session.execute(select(ChannelOrder).where(
            ChannelOrder.supplier_paid_at.is_(None), ChannelOrder.status != "cancelled",
            (ChannelOrder.cost_source.is_(None)) | (ChannelOrder.cost_source != "manual"))
            .order_by(ChannelOrder.ordered_at.desc()).limit(limit))).scalars().all()
        out = []
        for o in rows:
            live = await self.compute(o)
            if not live["complete"]:
                continue
            new_s, new_o = Decimal(live["supplier"]), Decimal(live["ours"])
            if o.purchase_cost == new_s and (o.other_costs or Decimal("0")) == new_o:
                continue
            out.append({"order_id": o.id, "external_id": o.external_id, "ordered_at": o.ordered_at,
                        "source": o.cost_source, "purchase_cost": o.purchase_cost, "other_costs": o.other_costs,
                        "new_purchase_cost": new_s, "new_other_costs": new_o})
        return out

    async def bulk_apply(self, order_ids: list[int], actor) -> int:
        n = 0
        for order_id in dict.fromkeys(order_ids):
            o = await self._order(order_id)
            if o.supplier_paid_at is not None or o.cost_source == "manual":
                continue
            result = await self.compute(o)
            if self._write(o, result):
                self._event(o, actor, f"Costs from SKUs: supplier ${o.purchase_cost:.2f}, ours ${o.other_costs:.2f}")
                n += 1
        if n:
            await self.audit.record("channel.order_costs_bulk", actor=actor, entity_type="channel_order", entity_id=None,
                                    changes={"orders": n})
        await self.session.commit()
        return n
