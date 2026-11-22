"""What the team does with marketplace orders: find them, enter costs, supplier and tracking, change status.
Every change goes to the order's history (who, when, what) and to the audit log. The marketplace's own fields are
never edited here."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.accounts.service import AccountService
from app.modules.audit.service import AuditService

from .connection import CHANNEL
from .etsy import attention as etsy_attention
from .etsy import payments as etsy_payments
from .etsy import profit as etsy_profit
from .etsy import status as etsy_status
from .models import ChannelListing, ChannelOrder, ChannelOrderEvent, ChannelOrderItem

COST_FIELDS = ("purchase_cost", "shipping_cost", "supplier_account_id", "supplier_order_number")
TRACKING_FIELDS = ("carrier", "tracking_number")
OTHER_FIELDS = ("notes", "buyer_phone")
EDITABLE = COST_FIELDS + TRACKING_FIELDS + OTHER_FIELDS
LABEL = {
    "purchase_cost": "purchase cost", "shipping_cost": "shipping cost", "supplier_account_id": "supplier",
    "supplier_order_number": "supplier order number", "carrier": "carrier", "tracking_number": "tracking number",
    "notes": "notes", "buyer_phone": "buyer phone",
}


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def facts(o: ChannelOrder) -> etsy_attention.OrderFacts:
    return etsy_attention.OrderFacts(
        status=o.status, paid_at=o.paid_at, ship_by=o.ship_by, purchase_cost=o.purchase_cost,
        shipping_cost=o.shipping_cost, etsy_fees=o.marketplace_fees, items_total=o.items_total,
        shipping_charged=o.shipping_charged, discounts=o.discounts, past_order=o.past_order)


def profit(o: ChannelOrder) -> dict[str, Any]:
    p = etsy_profit.compute(items_total=o.items_total, shipping_charged=o.shipping_charged, discounts=o.discounts,
                            purchase_cost=o.purchase_cost, shipping_cost=o.shipping_cost, etsy_fees=o.marketplace_fees)
    return {"revenue": p.revenue, "total_cost": p.total_cost, "net_profit": p.net_profit, "margin_pct": p.margin_pct,
            "missing": ["marketplace_fees" if m == "etsy_fees" else m for m in p.missing],
            "days_to_ship": etsy_profit.days_to_ship(o.paid_at, o.shipped_at)}


def attention_sql(now: datetime):
    revenue = ChannelOrder.items_total + ChannelOrder.shipping_charged - ChannelOrder.discounts
    cost = (func.coalesce(ChannelOrder.purchase_cost, 0) + func.coalesce(ChannelOrder.shipping_cost, 0)
            + func.coalesce(ChannelOrder.marketplace_fees, 0))
    return and_(ChannelOrder.status != "cancelled", ChannelOrder.past_order.is_(False), or_(
        and_(ChannelOrder.status == "new", ChannelOrder.paid_at < now - etsy_attention.NOT_PURCHASED_AFTER),
        and_(ChannelOrder.status.in_(etsy_attention.WAITING), ChannelOrder.ship_by < now),
        ChannelOrder.purchase_cost.is_(None),
        and_(ChannelOrder.shipping_cost.is_(None), ChannelOrder.status.in_(etsy_attention.DONE_SHIPPING)),
        and_(ChannelOrder.purchase_cost.is_not(None), revenue - cost < 0),
    ))


def _show(v: Any) -> str:
    if v is None:
        return "empty"
    if isinstance(v, Decimal):
        return f"${v:.2f}"
    return str(v)[:60]


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)
        self.accounts = AccountService(session)

    async def search(
        self, *, q: str | None = None, status: str | None = None, attention: bool = False, supplier: str | None = None,
        listing_id: int | None = None, date_from: date | None = None, date_to: date | None = None, page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        base = [ChannelOrder.channel == CHANNEL]
        cond = list(base)
        if q:
            term = q.strip().lstrip("#")
            like = _like(term.lower())
            parts = [func.lower(func.coalesce(ChannelOrder.buyer_name, "")).like(like, escape="\\"),
                     func.lower(func.coalesce(ChannelOrder.tracking_number, "")).like(like, escape="\\"),
                     func.lower(func.coalesce(ChannelOrder.supplier_order_number, "")).like(like, escape="\\"),
                     exists().where(ChannelOrderItem.order_id == ChannelOrder.id,
                                    or_(func.lower(ChannelOrderItem.title).like(like, escape="\\"),
                                        func.lower(func.coalesce(ChannelOrderItem.sku, "")).like(like, escape="\\")))]
            if term.isdigit():
                parts.append(ChannelOrder.external_id == int(term))
            cond.append(or_(*parts))
        if status == "open":
            cond.append(ChannelOrder.status.in_(etsy_status.OPEN_STATUSES))
        elif status:
            cond.append(ChannelOrder.status == status)
        if attention:
            cond.append(attention_sql(now))
        if supplier == "none":
            cond.append(ChannelOrder.supplier_account_id.is_(None))
        elif supplier and supplier.isdigit():
            cond.append(ChannelOrder.supplier_account_id == int(supplier))
        if listing_id:
            cond.append(exists().where(ChannelOrderItem.order_id == ChannelOrder.id,
                                       ChannelOrderItem.listing_external_id == listing_id))
        if date_from:
            cond.append(ChannelOrder.ordered_at >= datetime.combine(date_from, time.min, timezone.utc))
        if date_to:
            cond.append(ChannelOrder.ordered_at < datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc))
        total = (await self.session.execute(select(func.count()).select_from(ChannelOrder).where(*cond))).scalar_one()
        rows = list((await self.session.execute(
            select(ChannelOrder).where(*cond).order_by(ChannelOrder.ordered_at.desc(), ChannelOrder.id.desc())
            .limit(page_size).offset((page - 1) * page_size))).scalars().all())
        items = await self._items([r.id for r in rows])
        images = await self._images([i for its in items.values() for i in its])
        names = await self._supplier_names(rows)
        counts = dict((await self.session.execute(select(ChannelOrder.status, func.count()).where(*base)
                                                  .group_by(ChannelOrder.status))).all())
        needing = (await self.session.execute(select(func.count()).select_from(ChannelOrder)
                                              .where(*base, attention_sql(now)))).scalar_one()
        return {"items": [self.summary(r, items.get(r.id, []), now, images, names) for r in rows], "total": total,
                "page": page, "page_size": page_size, "counts": counts, "attention": needing}

    async def _supplier_names(self, rows: list[ChannelOrder]) -> dict[int, str]:
        return await self.accounts.names(sorted({r.supplier_account_id for r in rows if r.supplier_account_id}))

    async def _items(self, ids: list[int]) -> dict[int, list[ChannelOrderItem]]:
        out: dict[int, list[ChannelOrderItem]] = {}
        if ids:
            for it in (await self.session.execute(select(ChannelOrderItem).where(ChannelOrderItem.order_id.in_(ids))
                                                  .order_by(ChannelOrderItem.id))).scalars():
                out.setdefault(it.order_id, []).append(it)
        return out

    async def _images(self, items: list[ChannelOrderItem]) -> dict[int, str]:
        ids = {i.listing_external_id for i in items if i.listing_external_id}
        if not ids:
            return {}
        rows = (await self.session.execute(select(ChannelListing.external_id, ChannelListing.images).where(
            ChannelListing.channel == CHANNEL, ChannelListing.external_id.in_(ids)))).all()
        return {lid: imgs[0] for lid, imgs in rows if imgs}

    @staticmethod
    def summary(o: ChannelOrder, items: list[ChannelOrderItem], now: datetime, images: dict[int, str] | None = None,
                names: dict[int, str] | None = None) -> dict[str, Any]:
        images, names = images or {}, names or {}
        return {
            "id": o.id, "channel": o.channel, "external_id": o.external_id, "status": o.status,
            "ordered_at": o.ordered_at, "paid_at": o.paid_at, "ship_by": o.ship_by, "buyer_name": o.buyer_name,
            "supplier_account_id": o.supplier_account_id,
            "supplier_name": names.get(o.supplier_account_id) if o.supplier_account_id else None,
            "currency": o.currency, "tracking_number": o.tracking_number, "past_order": o.past_order,
            "items": [{"title": i.title, "quantity": i.quantity, "image": images.get(i.listing_external_id or 0)}
                      for i in items],
            "profit": profit(o), "attention": etsy_attention.reasons(facts(o), now),
        }

    async def get(self, order_id: int) -> ChannelOrder:
        row = await self.session.get(ChannelOrder, order_id)
        if row is None or row.channel != CHANNEL:
            raise NotFoundError("Order not found")
        return row

    async def detail(self, order_id: int) -> dict[str, Any]:
        o = await self.get(order_id)
        now = datetime.now(timezone.utc)
        items = (await self._items([o.id])).get(o.id, [])
        images = await self._images(items)
        names = await self._supplier_names([o])
        events = (await self.session.execute(select(ChannelOrderEvent).where(ChannelOrderEvent.order_id == o.id)
                                             .order_by(ChannelOrderEvent.id.desc()))).scalars().all()
        return {
            **self.summary(o, items, now, images, names),
            "external_state": o.external_state, "external_buyer_id": o.external_buyer_id, "buyer_email": o.buyer_email,
            "buyer_phone": o.buyer_phone, "ship_address": o.ship_address, "gift_message": o.gift_message,
            "buyer_note": o.buyer_note, "items_total": o.items_total, "shipping_charged": o.shipping_charged,
            "discounts": o.discounts, "tax": o.tax, "grand_total": o.grand_total, "marketplace_fees": o.marketplace_fees,
            "purchase_cost": o.purchase_cost, "costs_prefilled": o.costs_prefilled,
            "supplier_order_number": o.supplier_order_number, "shipping_cost": o.shipping_cost, "carrier": o.carrier,
            "tracking_sent_at": o.tracking_sent_at, "tracking_error": o.tracking_error, "purchased_at": o.purchased_at,
            "shipped_at": o.shipped_at, "delivered_at": o.delivered_at, "notes": o.notes, "synced_at": o.synced_at,
            "external_url": f"https://www.etsy.com/your/orders/sold?order_id={o.external_id}",
            "supplier_owed": etsy_payments.owed(o.purchase_cost, o.shipping_cost),
            "supplier_payment": etsy_payments.status(order_status=o.status, purchase_cost=o.purchase_cost,
                                                     paid=o.supplier_paid_at is not None),
            "supplier_paid_at": o.supplier_paid_at, "supplier_paid_amount": o.supplier_paid_amount,
            "supplier_payment_ref": o.supplier_payment_ref,
            "line_items": [{"id": i.id, "listing_external_id": i.listing_external_id, "title": i.title, "sku": i.sku,
                            "image": images.get(i.listing_external_id or 0), "variations": i.variations,
                            "quantity": i.quantity, "unit_price": i.unit_price} for i in items],
            "history": [{"id": e.id, "kind": e.kind, "from_status": e.from_status, "to_status": e.to_status,
                         "message": e.message, "source": e.source, "actor_name": e.actor_name,
                         "created_at": e.created_at} for e in events],
        }

    def _event(self, o: ChannelOrder, actor, kind: str, message: str, frm: str | None = None,
               to: str | None = None) -> None:
        self.session.add(ChannelOrderEvent(order_id=o.id, kind=kind, from_status=frm, to_status=to,
                                           message=message[:500], source="team", actor_id=actor.id,
                                           actor_name=getattr(actor, "full_name", None) or actor.email))

    async def update(self, order_id: int, actor, patch: dict[str, Any]) -> dict[str, Any]:
        o = await self.get(order_id)
        unknown = set(patch) - set(EDITABLE)
        if unknown:
            raise ValidationFailedError(f"Not editable here: {', '.join(sorted(unknown))}")
        if patch.get("supplier_account_id") is not None and patch["supplier_account_id"] != o.supplier_account_id:
            await self.accounts.require(patch["supplier_account_id"])
        names = await self.accounts.names([x for x in (o.supplier_account_id, patch.get("supplier_account_id")) if x])
        changed: dict[str, list[str]] = {"costs": [], "tracking": [], "note": []}
        for k, v in patch.items():
            if isinstance(v, str):
                v = v.strip() or None
            old = getattr(o, k)
            if old == v:
                continue
            setattr(o, k, v)
            kind = "costs" if k in COST_FIELDS else "tracking" if k in TRACKING_FIELDS else "note"
            if k == "supplier_account_id":
                changed[kind].append(f"supplier: {names.get(old, 'none') if old else 'none'} → "
                                     f"{names.get(v, 'none') if v else 'none'}")
            elif k == "notes":
                changed[kind].append("notes changed")
            else:
                changed[kind].append(f"{LABEL[k]}: {_show(old)} → {_show(v)}")
        if not any(changed.values()):
            return await self.detail(o.id)
        if changed["costs"] and "purchase_cost" in patch:
            o.costs_prefilled = False
        if changed["tracking"]:
            o.tracking_sent_at, o.tracking_error = None, None  # sending tracking to Etsy comes in a later phase
        for kind, lines in changed.items():
            if lines:
                self._event(o, actor, kind, "; ".join(lines))
        await self.audit.record("channel.order_update", actor=actor, entity_type="channel_order", entity_id=o.id,
                                changes={"order": o.external_id, "fields": sorted(k for k in patch if k in EDITABLE)})
        await self.session.commit()
        return await self.detail(o.id)

    async def set_status(self, order_id: int, actor, status: str, note: str | None) -> dict[str, Any]:
        o = await self.get(order_id)
        if not etsy_status.is_valid(status):
            raise ValidationFailedError("Unknown status")
        if not etsy_status.can_set_by_team(o.status, status):
            raise ValidationFailedError("The order already has that status")
        now = datetime.now(timezone.utc)
        old = o.status
        o.status = status
        if status == etsy_status.PURCHASED and not o.purchased_at:
            o.purchased_at = now
        if status in (etsy_status.SHIPPED, etsy_status.DELIVERED) and not o.shipped_at:
            o.shipped_at = now
        if status == etsy_status.DELIVERED and not o.delivered_at:
            o.delivered_at = now
        msg = f"{etsy_status.LABELS[old]} → {etsy_status.LABELS[status]}" + (f": {note.strip()}" if note and note.strip() else "")
        self._event(o, actor, "status", msg, old, status)
        await self.audit.record("channel.order_status", actor=actor, entity_type="channel_order", entity_id=o.id,
                                changes={"order": o.external_id, "status": [old, status]})
        await self.session.commit()
        return await self.detail(o.id)
