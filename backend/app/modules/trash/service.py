from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.trash import TRASH_TYPES, TrashType, children_of, trash_type
from app.modules.audit.service import AuditService

log = logging.getLogger(__name__)


class TrashSettings(BaseModel):
    """How long a deleted record waits in the Trash before it is removed for good."""

    retention_days: int = Field(default=30, ge=1, le=3650)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TrashService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def retention_days(self) -> int:
        from app.modules.settings.service import SettingsService

        try:
            return (await SettingsService(self.session).get_model("trash", factory=TrashSettings)).retention_days
        except Exception:  # noqa: BLE001 - an unreadable setting must never stop the Trash; use the default
            return TrashSettings().retention_days

    @staticmethod
    def _type(key: str) -> TrashType:
        t = trash_type(key)
        if t is None:
            raise NotFoundError("Unknown record type")
        return t

    async def _row(self, t: TrashType, item_id: int) -> Any:
        row = await self.session.get(t.model, item_id)
        if row is None or row.deleted_at is None:
            raise NotFoundError(f"{t.label} #{item_id} isn't in the Trash")
        return row

    async def summary(self) -> list[dict[str, Any]]:
        out = []
        for t in TRASH_TYPES.values():
            n = (await self.session.execute(select(func.count()).select_from(t.model)
                                            .where(t.model.deleted_at.is_not(None)))).scalar_one()
            out.append({"type": t.key, "label": t.label, "count": n})
        return sorted(out, key=lambda r: r["label"])

    async def list(self, *, type: str | None, page: int, page_size: int) -> dict[str, Any]:
        days = await self.retention_days()
        types = [self._type(type)] if type else list(TRASH_TYPES.values())
        rows: list[dict[str, Any]] = []
        for t in types:  # small tables in a CRM; merged in Python and paged
            for obj in (await self.session.execute(select(t.model).where(t.model.deleted_at.is_not(None)))).scalars():
                rows.append({"type": t.key, "label": t.label, "id": obj.id, "title": t.title(obj) or f"#{obj.id}",
                             "deleted_at": obj.deleted_at, "deleted_by": getattr(obj, "updated_by", None),
                             "purge_after": obj.deleted_at + timedelta(days=days)})
        rows.sort(key=lambda r: r["deleted_at"], reverse=True)
        start = (page - 1) * page_size
        return {"items": rows[start:start + page_size], "total": len(rows), "page": page, "page_size": page_size,
                "retention_days": days}

    async def restore(self, key: str, item_id: int, actor) -> dict[str, Any]:
        t = self._type(key)
        row = await self._row(t, item_id)
        if t.restore is not None:
            await t.restore(self.session, item_id, actor)
            return {"type": t.key, "id": item_id, "title": t.title(row)}
        row.deleted_at = None
        if hasattr(row, "updated_by"):
            row.updated_by = actor.id
        await self.audit.record(f"{t.key}.restore", actor=actor, entity_type=t.key, entity_id=item_id,
                                changes={"title": t.title(row)})
        await self.session.commit()
        return {"type": t.key, "id": item_id, "title": t.title(row)}

    async def _purge(self, t: TrashType, row: Any) -> None:
        if t.before_purge:
            await t.before_purge(self.session, row)
        await self.session.delete(row)
        await self.session.flush()

    async def purge(self, key: str, item_id: int, actor) -> None:
        t = self._type(key)
        row = await self._row(t, item_id)
        title = t.title(row)
        await self._purge(t, row)
        await self.audit.record(f"{t.key}.purge", actor=actor, entity_type=t.key, entity_id=item_id,
                                changes={"title": title})
        await self.session.commit()

    async def empty_expired(self) -> str | None:
        """The job: remove for good whatever has waited longer than the retention period. One row that can't go
        (still referenced by something) stays for the next run and never stops the others."""
        cutoff = _now() - timedelta(days=await self.retention_days())
        purged, kept = 0, 0
        for t in sorted(TRASH_TYPES.values(), key=lambda t: t.order):
            ids = list((await self.session.execute(select(t.model.id).where(
                t.model.deleted_at.is_not(None), t.model.deleted_at < cutoff).limit(200))).scalars())
            for item_id in ids:
                try:
                    async with self.session.begin_nested():
                        row = await self.session.get(t.model, item_id)
                        if row is not None:
                            await self._purge(t, row)
                    purged += 1
                except Exception as exc:  # noqa: BLE001 - e.g. a foreign key from a record outside the Trash
                    kept += 1
                    log.info("trash: kept %s #%s (%s)", t.key, item_id, exc.__class__.__name__)
        await self.session.commit()
        if not purged and not kept:
            return None
        return f"trash: removed {purged} for good" + (f", {kept} still referenced" if kept else "")

    async def blockers(self, key: str, item_id: int) -> list[str]:
        t = self._type(key)
        row = await self.session.get(t.model, item_id)
        if row is None:
            raise NotFoundError(f"{t.label} not found")
        return await children_of(self.session, key, row)
