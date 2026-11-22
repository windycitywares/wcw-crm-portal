"""Supplier payments for marketplace (Etsy) orders: what is pending and settled per supplier, recording and undoing a payment
(one order or a whole invoice at once), and exports. Every payment is in the order's history and the audit log."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.accounts.service import AccountService
from app.modules.audit.service import AuditService
from app.modules.users.service import UserService

from .connection import CHANNEL
from .etsy import payments as pay
from .models import ChannelOrder as EtsyOrder
from .models import ChannelOrderEvent as EtsyOrderEvent
from .models import ChannelOrderItem as EtsyOrderItem

ZERO = Decimal("0.00")
NONE_SUPPLIER = "none"


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, timezone.utc)


def _row(o: EtsyOrder, items: list[EtsyOrderItem], names: dict[int, str], people: dict[int, str]) -> dict[str, Any]:
    paid = o.supplier_paid_at is not None
    return {
        "id": o.id, "external_id": o.external_id, "ordered_at": o.ordered_at, "status": o.status,
        "buyer_name": o.buyer_name, "supplier_account_id": o.supplier_account_id,
        "supplier": names.get(o.supplier_account_id) if o.supplier_account_id else None,
        "supplier_order_number": o.supplier_order_number,
        "items": ", ".join(f"{i.quantity}× {i.title}" for i in items),
        "purchase_cost": o.purchase_cost, "shipping_cost": o.shipping_cost,
        "owed": pay.owed(o.purchase_cost, o.shipping_cost),
        "payment_status": pay.status(order_status=o.status, purchase_cost=o.purchase_cost, paid=paid),
        "paid_at": o.supplier_paid_at, "paid_amount": o.supplier_paid_amount, "payment_ref": o.supplier_payment_ref,
        "paid_by": people.get(o.supplier_paid_by) if o.supplier_paid_by else None,
    }


class SupplierPayments:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _conditions(self, state: str, supplier: str | None, date_from: date | None, date_to: date | None) -> list:
        cond: list = [EtsyOrder.channel == CHANNEL]
        if state == pay.PENDING:
            cond += [EtsyOrder.supplier_paid_at.is_(None), EtsyOrder.purchase_cost.is_not(None), EtsyOrder.status != "cancelled"]
        elif state == pay.SETTLED:
            cond.append(EtsyOrder.supplier_paid_at.is_not(None))
        elif state == pay.COST_MISSING:
            cond += [EtsyOrder.supplier_paid_at.is_(None), EtsyOrder.purchase_cost.is_(None), EtsyOrder.status != "cancelled",
                     EtsyOrder.past_order.is_(False)]
        else:  # everything that is, or was, owed
            cond.append(or_(EtsyOrder.supplier_paid_at.is_not(None),
                            and_(EtsyOrder.purchase_cost.is_not(None), EtsyOrder.status != "cancelled")))
        if supplier == NONE_SUPPLIER:
            cond.append(EtsyOrder.supplier_account_id.is_(None))
        elif supplier and supplier.isdigit():
            cond.append(EtsyOrder.supplier_account_id == int(supplier))
        # Settled payments are found by the day they were paid; everything else by the order date.
        column = EtsyOrder.supplier_paid_at if state == pay.SETTLED else EtsyOrder.ordered_at
        if date_from:
            cond.append(column >= _day_start(date_from))
        if date_to:
            cond.append(column < _day_start(date_to + timedelta(days=1)))
        return cond

    async def _items(self, ids: list[int]) -> dict[int, list[EtsyOrderItem]]:
        out: dict[int, list[EtsyOrderItem]] = {}
        if ids:
            for it in (await self.session.execute(select(EtsyOrderItem).where(EtsyOrderItem.order_id.in_(ids)).order_by(EtsyOrderItem.id))).scalars():
                out.setdefault(it.order_id, []).append(it)
        return out

    async def rows(self, state: str, supplier: str | None, date_from: date | None, date_to: date | None,
                   limit: int | None = None, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        cond = self._conditions(state, supplier, date_from, date_to)
        total = (await self.session.execute(select(func.count()).select_from(EtsyOrder).where(*cond))).scalar_one()
        order = EtsyOrder.supplier_paid_at.desc() if state == pay.SETTLED else EtsyOrder.ordered_at.asc()
        q = select(EtsyOrder).where(*cond).order_by(order, EtsyOrder.id)
        if limit:
            q = q.limit(limit).offset(offset)
        orders = (await self.session.execute(q)).scalars().all()
        items = await self._items([o.id for o in orders])
        names = await AccountService(self.session).names(sorted({o.supplier_account_id for o in orders if o.supplier_account_id}))
        people = {u.id: u.full_name for u in await UserService(self.session).directory()}
        return [_row(o, items.get(o.id, []), names, people) for o in orders], total

    async def overview(self, supplier: str | None, date_from: date | None, date_to: date | None) -> dict[str, Any]:
        """Per supplier: pending (count, amount owed) and settled (count, amount paid) for the filters; orders whose
        cost is still missing are counted so nobody forgets them."""
        owed_expr = EtsyOrder.purchase_cost + func.coalesce(EtsyOrder.shipping_cost, 0)
        pending = dict(((s, (n, a)) for s, n, a in (await self.session.execute(
            select(EtsyOrder.supplier_account_id, func.count(), func.coalesce(func.sum(owed_expr), 0))
            .where(*self._conditions(pay.PENDING, supplier, date_from, date_to))
            .group_by(EtsyOrder.supplier_account_id))).all()))
        settled = dict(((s, (n, a)) for s, n, a in (await self.session.execute(
            select(EtsyOrder.supplier_account_id, func.count(), func.coalesce(func.sum(EtsyOrder.supplier_paid_amount), 0))
            .where(*self._conditions(pay.SETTLED, supplier, date_from, date_to))
            .group_by(EtsyOrder.supplier_account_id))).all()))
        missing = (await self.session.execute(select(func.count()).select_from(EtsyOrder)
                                              .where(*self._conditions(pay.COST_MISSING, supplier, date_from, date_to)))).scalar_one()
        ids = set(pending) | set(settled)
        labels = await AccountService(self.session).names(sorted(i for i in ids if i))
        names = sorted(ids, key=lambda s: (s is None, (labels.get(s, "") if s else "").lower()))
        suppliers = [{
            "supplier_account_id": s, "supplier": labels.get(s) if s else None,
            "pending_count": pending.get(s, (0, ZERO))[0], "pending_amount": Decimal(pending.get(s, (0, ZERO))[1]),
            "settled_count": settled.get(s, (0, ZERO))[0], "settled_amount": Decimal(settled.get(s, (0, ZERO))[1]),
        } for s in names]
        return {
            "suppliers": suppliers,
            "pending_count": sum(r["pending_count"] for r in suppliers),
            "pending_amount": sum((r["pending_amount"] for r in suppliers), ZERO),
            "settled_count": sum(r["settled_count"] for r in suppliers),
            "settled_amount": sum((r["settled_amount"] for r in suppliers), ZERO),
            "cost_missing": missing,
        }

    async def settle(self, actor, order_ids: list[int], paid_on: date, reference: str | None, note: str | None,
                     amount: Decimal | None) -> dict[str, Any]:
        """Mark orders paid. Each is recorded at what it owes, unless one order is settled with a different amount."""
        ids = list(dict.fromkeys(order_ids))
        if not ids:
            raise ValidationFailedError("Choose at least one order")
        if amount is not None and len(ids) != 1:
            raise ValidationFailedError("A different amount can only be entered for one order at a time")
        orders = (await self.session.execute(select(EtsyOrder).where(EtsyOrder.id.in_(ids),
                                                                     EtsyOrder.channel == CHANNEL))).scalars().all()
        if len(orders) != len(ids):
            raise NotFoundError("Order not found")
        for o in orders:
            if o.supplier_paid_at is not None:
                raise ValidationFailedError(f"Order {o.external_id} is already settled")
            if o.purchase_cost is None:
                raise ValidationFailedError(f"Order {o.external_id} has no purchase cost yet")
        when = datetime.combine(paid_on, time(12), timezone.utc)
        if when > datetime.now(timezone.utc) + timedelta(days=1):
            raise ValidationFailedError("The payment date can't be in the future")
        who = actor.full_name or actor.email
        ref = (reference or "").strip() or None
        total = ZERO
        for o in orders:
            paid = amount if amount is not None else pay.owed(o.purchase_cost, o.shipping_cost)
            o.supplier_paid_at, o.supplier_paid_amount, o.supplier_payment_ref, o.supplier_paid_by = when, paid, ref, actor.id
            total += paid
            msg = f"Supplier paid ${paid:.2f} on {paid_on.isoformat()}" + (f" (ref {ref})" if ref else "") + \
                  (f": {note.strip()}" if note and note.strip() else "")
            self.session.add(EtsyOrderEvent(order_id=o.id, kind="payment", message=msg[:500], source="team",
                                            actor_id=actor.id, actor_name=who))
        await AuditService(self.session).record(
            "channel.supplier_paid", actor=actor, entity_type="channel_order",
            entity_id=orders[0].id if len(orders) == 1 else None,
            changes={"orders": [o.external_id for o in orders], "total": str(total), "reference": ref})
        await self.session.commit()
        return {"settled": len(orders), "total": total}

    async def unsettle(self, actor, order_id: int, reason: str | None) -> None:
        o = await self.session.get(EtsyOrder, order_id)
        if o is None or o.channel != CHANNEL:
            raise NotFoundError("Order not found")
        if o.supplier_paid_at is None:
            raise ValidationFailedError("This order isn't marked paid")
        who = actor.full_name or actor.email
        msg = f"Supplier payment of ${o.supplier_paid_amount or 0:.2f} undone" + (f": {reason.strip()}" if reason and reason.strip() else "")
        o.supplier_paid_at = o.supplier_paid_amount = o.supplier_payment_ref = o.supplier_paid_by = None
        self.session.add(EtsyOrderEvent(order_id=o.id, kind="payment", message=msg[:500], source="team", actor_id=actor.id, actor_name=who))
        await AuditService(self.session).record("channel.supplier_unpaid", actor=actor, entity_type="channel_order",
                                                entity_id=o.id, changes={"order": o.external_id, "message": msg})
        await self.session.commit()

    # ---- exports ----------------------------------------------------------------------------------------------

    COLUMNS = (
        ("Etsy order", "external_id"), ("Order date", "ordered_at"), ("Supplier", "supplier"),
        ("Supplier order #", "supplier_order_number"), ("Items", "items"), ("Purchase cost", "purchase_cost"),
        ("Shipping cost", "shipping_cost"), ("Owed", "owed"), ("Payment", "payment_status"), ("Paid on", "paid_at"),
        ("Amount paid", "paid_amount"), ("Reference", "payment_ref"), ("Paid by", "paid_by"),
    )

    @classmethod
    def _cells(cls, r: dict[str, Any]) -> list[Any]:
        out = []
        for _, k in cls.COLUMNS:
            v = r[k]
            if k == "payment_status":
                v = pay.LABELS.get(v, v)
            elif isinstance(v, datetime):
                v = v.date().isoformat()
            out.append(v)
        return out

    def csv_bytes(self, rows: list[dict[str, Any]]) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([c for c, _ in self.COLUMNS])
        for r in rows:
            w.writerow(["" if v is None else v for v in self._cells(r)])
        return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM: Excel opens it with the right characters

    def xlsx_bytes(self, rows: list[dict[str, Any]], title: str) -> bytes:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]
        ws.append([c for c, _ in self.COLUMNS])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        money_cols = {i + 1 for i, (_, k) in enumerate(self.COLUMNS) if k in ("purchase_cost", "shipping_cost", "owed", "paid_amount")}
        for r in rows:
            ws.append([float(v) if isinstance(v, Decimal) else v for v in self._cells(r)])
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column in money_cols:
                    cell.number_format = '"$"#,##0.00'
        widths = [12, 12, 20, 16, 50, 13, 13, 11, 12, 12, 13, 18, 18]
        for i, w in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = w
        ws.freeze_panes = "A2"
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
