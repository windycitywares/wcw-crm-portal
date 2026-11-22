"""Loads the Etsy orders for a period and hands them to etsy/dashboard.py: sales, costs, profit and fulfilment, with
the previous period of the same length to compare. Days are the business's days (Settings → Business hours)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailedError
from app.modules.accounts.service import AccountService
from app.modules.settings.service import SettingsService

from .connection import CHANNEL
from .etsy import dashboard as dash
from .models import ChannelListing, ChannelOrder, ChannelOrderItem

MAX_DAYS = 731


@dataclass(frozen=True)
class Range:
    start: date
    end: date  # inclusive
    zone: ZoneInfo

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def start_utc(self) -> datetime:
        return datetime.combine(self.start, time.min, self.zone).astimezone(timezone.utc)

    @property
    def end_utc(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time.min, self.zone).astimezone(timezone.utc)

    def previous(self) -> Range:
        return Range(self.start - timedelta(days=self.days), self.start - timedelta(days=1), self.zone)

    def granularity(self) -> str:
        return "day" if self.days <= 45 else "week" if self.days <= 200 else "month"

    def buckets(self) -> list[date]:
        gran, out = self.granularity(), []
        cur = self.start if gran == "day" else (self.start - timedelta(days=self.start.weekday()) if gran == "week"
                                                 else self.start.replace(day=1))
        while cur <= self.end:
            out.append(cur)
            cur = cur + timedelta(days=1) if gran == "day" else cur + timedelta(days=7) if gran == "week" \
                else (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        return out


def label(bucket: date, gran: str) -> str:
    return bucket.strftime("%b %Y") if gran == "month" else f"{bucket.strftime('%b')} {bucket.day}"


def kpi(key: str, name: str, value: float | None, previous: float | None = None, fmt: str = "number",
        help: str = "", better: str = "up") -> dict[str, Any]:
    change = delta = None
    if value is not None and previous is not None:
        delta = round(value - previous, 6)
        if previous:
            change = round((value - previous) / abs(previous), 6)
    return {"key": key, "label": name, "value": value, "previous": previous, "delta": delta, "change": change,
            "format": fmt, "help": help, "better": better}


class EtsyDashboard:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def range(self, start: date | None, end: date | None, default_days: int = 30) -> Range:
        hours = await SettingsService(self.session).get_model("business_hours")
        zone = ZoneInfo(getattr(hours, "timezone", "America/Chicago"))
        today = datetime.now(zone).date()
        end = end or today
        start = start or end - timedelta(days=default_days - 1)
        if start > end:
            raise ValidationFailedError("The start date is after the end date")
        if (end - start).days + 1 > MAX_DAYS:
            raise ValidationFailedError("Choose at most two years")
        return Range(start, end, zone)

    async def _orders(self, rng: Range, listing_id: int | None, supplier: str | None) -> list[dash.Order]:
        cond = [ChannelOrder.channel == CHANNEL, ChannelOrder.ordered_at >= rng.start_utc,
                ChannelOrder.ordered_at < rng.end_utc]
        if listing_id:
            cond.append(exists().where(ChannelOrderItem.order_id == ChannelOrder.id,
                                       ChannelOrderItem.listing_external_id == listing_id))
        if supplier == "none":
            cond.append(ChannelOrder.supplier_account_id.is_(None))
        elif supplier and supplier.isdigit():
            cond.append(ChannelOrder.supplier_account_id == int(supplier))
        rows = (await self.session.execute(select(ChannelOrder).where(*cond))).scalars().all()
        items: dict[int, list[dash.Item]] = {}
        if rows:
            for it in (await self.session.execute(select(ChannelOrderItem).where(
                    ChannelOrderItem.order_id.in_([r.id for r in rows])))).scalars():
                items.setdefault(it.order_id, []).append(
                    dash.Item(it.listing_external_id, it.title, it.quantity, it.unit_price * it.quantity))
        return [dash.Order(
            status=o.status, ordered_at=o.ordered_at, paid_at=o.paid_at, shipped_at=o.shipped_at, ship_by=o.ship_by,
            items_total=o.items_total, shipping_charged=o.shipping_charged, discounts=o.discounts,
            purchase_cost=o.purchase_cost, shipping_cost=o.shipping_cost, etsy_fees=o.marketplace_fees,
            supplier=o.supplier_account_id, state=(o.ship_address or {}).get("state"),
            country=(o.ship_address or {}).get("country_iso"), items=tuple(items.get(o.id, ())),
        ) for o in rows]

    async def build(self, rng: Range, listing_id: int | None = None, supplier: str | None = None) -> dict[str, Any]:
        gran = rng.granularity()

        def bucket_of(moment: datetime) -> date:
            day = moment.astimezone(rng.zone).date()
            if gran == "week":
                return day - timedelta(days=day.weekday())
            if gran == "month":
                return day.replace(day=1)
            return day

        prev = rng.previous()
        out = dash.build(await self._orders(rng, listing_id, supplier), await self._orders(prev, listing_id, supplier),
                         rng.buckets(), bucket_of)
        for s in out["series"]:
            s["label"] = label(date.fromisoformat(s["bucket"]), gran)
        names = await AccountService(self.session).names([s["supplier_account_id"] for s in out["suppliers"]
                                                          if s["supplier_account_id"]])
        for s in out["suppliers"]:
            s["supplier"] = names.get(s["supplier_account_id"]) if s["supplier_account_id"] else None
        t, p = out["totals"], out["previous"]
        out["kpis"] = [
            kpi("orders", "Orders", t["orders"], p["orders"], help="Paid, not cancelled."),
            kpi("items", "Items sold", t["units"], p["units"], help="What Etsy calls “sales”."),
            kpi("revenue", "Revenue", t["revenue"], p["revenue"], "money", "After discounts, before tax."),
            kpi("profit", "Net profit", t["profit"], p["profit"], "money", "Costed orders, before Etsy fees."),
            kpi("margin", "Margin", t["margin"], p["margin"], "percent", "Of costed orders."),
            kpi("days_to_ship", "Days to ship", t["avg_days_to_ship"], p["avg_days_to_ship"], "decimal",
                "Payment to shipping.", better="down"),
        ]
        out["range"] = {"start": rng.start.isoformat(), "end": rng.end.isoformat(), "days": rng.days,
                        "granularity": gran, "previous_start": prev.start.isoformat(), "previous_end": prev.end.isoformat()}
        out["options"] = await self._options()
        ids = [x["listing_id"] for x in out["top_products"] if x["listing_id"]]
        if ids:
            imgs = dict((await self.session.execute(select(ChannelListing.external_id, ChannelListing.images).where(
                ChannelListing.channel == CHANNEL, ChannelListing.external_id.in_(ids)))).all())
            for x in out["top_products"]:
                x["image"] = (imgs.get(x["listing_id"]) or [None])[0]
        return out

    async def _options(self) -> dict[str, Any]:
        """Products that have sold (for the product filter)."""
        products = (await self.session.execute(
            select(ChannelOrderItem.listing_external_id, func.max(ChannelOrderItem.title))
            .join(ChannelOrder, ChannelOrder.id == ChannelOrderItem.order_id)
            .where(ChannelOrder.channel == CHANNEL, ChannelOrderItem.listing_external_id.is_not(None))
            .group_by(ChannelOrderItem.listing_external_id).order_by(func.max(ChannelOrderItem.title)))).all()
        return {"products": [{"listing_id": lid, "title": title} for lid, title in products]}
