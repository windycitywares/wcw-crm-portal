"""One-off import of what the shop already has (customers, then orders, then newsletter consent), run in chunks
by the `shop-backfill` job so a large shop never blocks a web request or the other jobs. Safe to run again:
every item goes through the same find-or-create rules as live events."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailedError
from app.modules.audit.service import AuditService
from app.modules.settings.service import SettingsService
from app.shared.time import utcnow

from .client import ShopApiError, shop_client
from .models import ShopBackfill
from .service import ShopEventService

PHASES = ("customers", "orders", "newsletter")
TIME_BUDGET = 40.0
PAGE = 200
EVENT_FOR = {"customers": "customer.upserted", "orders": "order.updated"}


class BackfillOut(BaseModel):
    status: str
    phase: str
    counts: dict[str, int]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ShopBackfillService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _row(self) -> ShopBackfill:
        row = await self.session.get(ShopBackfill, 1)
        if row is None:
            row = ShopBackfill(id=1, status="idle", phase=PHASES[0], after_id=0, counts={})
            self.session.add(row)
            await self.session.flush()
        return row

    @staticmethod
    def _out(row: ShopBackfill) -> BackfillOut:
        return BackfillOut(status=row.status, phase=row.phase, counts=dict(row.counts or {}), error=row.error,
                           started_at=row.started_at, finished_at=row.finished_at)

    async def _client(self):
        return shop_client(await SettingsService(self.session).get_model("shop"))

    async def state(self) -> BackfillOut:
        out = self._out(await self._row())
        await self.session.commit()
        return out

    async def test_connection(self) -> dict[str, Any]:
        try:
            page = await (await self._client()).page("customers", 0, 1)
        except ShopApiError as exc:
            return {"ok": False, "detail": str(exc)}
        return {"ok": True, "detail": "Connected: the shop answered." + ("" if page.get("items") else " It has no customer accounts yet.")}

    async def start(self, actor) -> BackfillOut:
        result = await self.test_connection()
        if not result["ok"]:
            raise ValidationFailedError(f"Can't reach the shop: {result['detail']}")
        row = await self._row()
        row.status, row.phase, row.after_id, row.counts, row.error = "running", PHASES[0], 0, {}, None
        row.started_by, row.started_at, row.finished_at = actor.id, utcnow(), None
        await self.audit.record("shop.backfill.start", actor=actor, entity_type="settings")
        await self.session.commit()
        return self._out(row)

    async def cancel(self, actor) -> BackfillOut:
        row = await self._row()
        if row.status == "running":
            row.status, row.finished_at, row.error = "idle", utcnow(), "Stopped by an admin"
            await self.audit.record("shop.backfill.cancel", actor=actor, entity_type="settings")
        await self.session.commit()
        return self._out(row)

    async def run_chunk(self, budget: float = TIME_BUDGET) -> str | None:
        """Called every minute by the job: import pages until the time budget is used. Returns a log line."""
        row = await self._row()
        if row.status != "running":
            await self.session.commit()
            return None
        events = ShopEventService(self.session)
        events.quiet = True
        started, done = time.monotonic(), 0
        try:
            client = await self._client()
            while row.status == "running" and time.monotonic() - started < budget:
                page = await client.page(row.phase, row.after_id, PAGE)
                counts = dict(row.counts or {})
                for item in page.get("items", []):
                    event_type = EVENT_FOR.get(row.phase) or str(item.get("type", ""))
                    try:
                        async with self.session.begin_nested():
                            await events.apply_data(event_type, item)
                        counts[row.phase] = counts.get(row.phase, 0) + 1
                    except Exception:  # noqa: BLE001 - one bad record must not stop the import
                        counts["errors"] = counts.get("errors", 0) + 1
                    done += 1
                row.counts = counts
                nxt = page.get("next_after_id")
                if nxt:
                    row.after_id = int(nxt)
                else:
                    i = PHASES.index(row.phase)
                    if i + 1 < len(PHASES):
                        row.phase, row.after_id = PHASES[i + 1], 0
                    else:
                        row.status, row.finished_at = "done", utcnow()
                await self.session.commit()
        except ShopApiError as exc:
            row.status, row.error, row.finished_at = "failed", str(exc)[:1000], utcnow()
            await self.session.commit()
            return f"shop backfill failed: {exc}"
        return f"shop backfill: {done} records ({row.status}, {row.phase})" if done or row.status == "done" else None
