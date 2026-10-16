"""Audit trail. Other modules call `AuditService(session).record(...)` inside their own transaction."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams

from .models import AuditLog
from .repository import AuditRepository
from .schemas import AuditOut, AuditPage

REDACTED = "••••"
SENSITIVE = {"password", "password_hash", "token", "smtp_password", "secret"}


class Actor(Protocol):
    id: int
    email: str


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """{"field": [old, new]} for the fields that changed; secrets are masked."""
    out: dict[str, list[Any]] = {}
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old != new:
            out[key] = [REDACTED, REDACTED] if key in SENSITIVE else [old, new]
    return out


class AuditService:
    def __init__(self, session: AsyncSession):
        self.repo = AuditRepository(session)

    async def record(
        self, action: str, *, actor: Actor | None = None, entity_type: str | None = None,
        entity_id: int | None = None, changes: dict[str, Any] | None = None, ip: str | None = None,
        actor_email: str | None = None,
    ) -> AuditLog:
        return await self.repo.add(AuditLog(
            action=action,
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else actor_email,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes or None,
            ip=ip,
        ))

    async def search(self, params: PageParams, **filters: Any) -> AuditPage:
        rows, total = await self.repo.paginate(self.repo.search(**filters), params)
        return AuditPage(
            items=[AuditOut.model_validate(r) for r in rows], total=total, page=params.page, page_size=params.page_size
        )
