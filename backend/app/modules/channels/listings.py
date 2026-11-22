"""Etsy listings → the CRM, one way. Etsy is the source of truth: every pass overwrites Etsy's columns and never
touches the team's (supplier, purchase cost, notes). A listing Etsy no longer returns is marked `removed`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode
from app.core.exceptions import NotFoundError
from app.modules.accounts.service import AccountService
from app.modules.audit.service import AuditService, diff

from .connection import CHANNEL, EtsyConnectionService
from .etsy import client as etsy_client
from .etsy import listing as etsy_listing
from .etsy.client import EtsyError
from .models import ChannelListing

PAGE = 100
EVERY = timedelta(minutes=15)  # the job runs every minute; a full pass is this often
TEAM_FIELDS = ("supplier_account_id", "purchase_cost", "notes")


def _columns(parsed: dict[str, Any]) -> dict[str, Any]:
    out = dict(parsed)
    out["external_id"] = out.pop("etsy_listing_id")
    out["external_updated_at"] = out.pop("etsy_updated_at")
    return out


class EtsyListingSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, force: bool = False) -> dict[str, Any]:
        service = EtsyConnectionService(self.session)
        conn = await service.row()
        if not (conn.access_token_enc and conn.external_shop_id):
            return {"skipped": "not connected"}
        now = datetime.now(timezone.utc)
        if not force and conn.listings_synced_at and now - conn.listings_synced_at < EVERY:
            return {"skipped": "not due"}
        try:
            key, token = await service.access_token()
            seen: set[int] = set()
            created = updated = 0
            for state in etsy_listing.STATES:
                offset = 0
                while True:
                    data = await etsy_client.get(
                        f"/shops/{conn.external_shop_id}/listings", api_key=key, access_token=token,
                        params={"state": state, "limit": PAGE, "offset": offset, "includes": "Images,Inventory"})
                    results = data.get("results") or []
                    for raw in results:
                        c, u = await self._upsert(_columns(etsy_listing.parse({**raw, "state": raw.get("state") or state})), now)
                        seen.add(int(raw["listing_id"]))
                        created, updated = created + c, updated + u
                    offset += PAGE
                    if len(results) < PAGE:
                        break
            removed = await self._mark_removed(seen)
        except EtsyError as exc:
            await self.session.rollback()
            await service.fail(f"Listing sync: {exc}")
            return {"error": str(exc)[:200]}
        conn = await service.row()
        conn.listings_synced_at, conn.last_error, conn.last_error_at = now, None, None
        await self.session.commit()
        return {"created": created, "updated": updated, "removed": removed, "total": len(seen)}

    async def _upsert(self, fields: dict[str, Any], now: datetime) -> tuple[int, int]:
        row = (await self.session.execute(select(ChannelListing).where(
            ChannelListing.channel == CHANNEL, ChannelListing.external_id == fields["external_id"]))).scalar_one_or_none()
        if row is None:
            self.session.add(ChannelListing(channel=CHANNEL, **fields, synced_at=now))
            await self.session.flush()
            return 1, 0
        for k, v in fields.items():
            setattr(row, k, v)
        row.synced_at = now
        return 0, 1

    async def _mark_removed(self, seen: set[int]) -> int:
        if not seen:  # an empty answer is more likely a problem than a shop with nothing in it
            return 0
        rows = (await self.session.execute(select(ChannelListing).where(
            ChannelListing.channel == CHANNEL, ChannelListing.external_id.not_in(seen),
            ChannelListing.state != "removed"))).scalars().all()
        for r in rows:
            r.state = "removed"
        return len(rows)


async def job(session: AsyncSession) -> str | None:
    """The `etsy-listings` job: a full pass every 15 minutes while Etsy is connected (never in test mode)."""
    if appmode.is_test():
        return None
    result = await EtsyListingSync(session).run()
    if "skipped" in result:
        return None
    if "error" in result:
        return f"etsy listings: {result['error']}"
    return f"etsy listings: {result['total']} ({result['created']} new, {result['removed']} removed)"


class ListingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)
        self.accounts = AccountService(session)

    async def out(self, rows: list[ChannelListing]) -> list[dict[str, Any]]:
        names = await self.accounts.names(sorted({r.supplier_account_id for r in rows if r.supplier_account_id}))
        return [{
            "id": r.id, "channel": r.channel, "external_id": r.external_id, "title": r.title, "state": r.state,
            "price": r.price, "currency": r.currency, "quantity": r.quantity, "skus": r.skus, "url": r.url,
            "image": (r.images or [None])[0], "variations": r.variations, "tags": r.tags,
            "description": r.description, "synced_at": r.synced_at,
            "supplier_account_id": r.supplier_account_id,
            "supplier_name": names.get(r.supplier_account_id) if r.supplier_account_id else None,
            "purchase_cost": r.purchase_cost, "notes": r.notes,
        } for r in rows]

    async def search(self, *, q: str | None, state: str | None, supplier: str | None, page: int,
                     page_size: int) -> dict[str, Any]:
        cond = [ChannelListing.channel == CHANNEL]
        if supplier == "none":
            cond.append(ChannelListing.supplier_account_id.is_(None))
        elif supplier and supplier.isdigit():
            cond.append(ChannelListing.supplier_account_id == int(supplier))
        if q:
            like = f"%{q.strip().lower()}%"
            cond.append(or_(func.lower(ChannelListing.title).like(like),
                            func.lower(cast(ChannelListing.skus, Text)).like(like)))
        if state:
            cond.append(ChannelListing.state == state)
        total = (await self.session.execute(select(func.count()).select_from(ChannelListing).where(*cond))).scalar_one()
        rows = (await self.session.execute(select(ChannelListing).where(*cond).order_by(ChannelListing.title)
                                           .limit(page_size).offset((page - 1) * page_size))).scalars().all()
        return {"items": await self.out(list(rows)), "total": total, "page": page, "page_size": page_size}

    async def update(self, listing_id: int, values: dict[str, Any], actor) -> dict[str, Any]:
        row = await self.session.get(ChannelListing, listing_id)
        if row is None:
            raise NotFoundError("Listing not found")
        if values.get("supplier_account_id") is not None:
            await self.accounts.require(values["supplier_account_id"])
        before = {f: getattr(row, f) for f in TEAM_FIELDS}
        for k, v in values.items():
            if k in TEAM_FIELDS:
                setattr(row, k, v)
        after = {f: getattr(row, f) for f in TEAM_FIELDS}
        changes = diff({k: str(v) if isinstance(v, Decimal) else v for k, v in before.items()},
                       {k: str(v) if isinstance(v, Decimal) else v for k, v in after.items()})
        if changes:
            await self.audit.record("channel.listing_update", actor=actor, entity_type="channel_listing",
                                    entity_id=row.id, changes=changes)
        await self.session.commit()
        await self.session.refresh(row)
        return (await self.out([row]))[0]
