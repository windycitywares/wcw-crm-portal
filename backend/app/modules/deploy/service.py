"""Admin → Deployments: settings + "Deploy now", and the gate the server's cron job asks every minute."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.service import AuditService
from app.modules.settings.service import SettingsService

from .models import DeployControl
from .policy import Decision, decide
from .schemas import DeployConfig, DeployStatus, Version

LOG_MAX_LINES = 400
STUCK_AFTER = timedelta(minutes=30)  # a run that never reported back is treated as finished


def _now() -> datetime:
    return datetime.now(timezone.utc)


def git_version(repo: str) -> Version:
    try:
        out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h%x1f%s%x1f%cI"], capture_output=True,
                             text=True, timeout=5, check=True).stdout.strip()
        commit, subject, date = out.split("\x1f")
        return Version(commit=commit, subject=subject[:200], date=date)
    except (OSError, subprocess.SubprocessError, ValueError):
        return Version(commit=None, subject=None, date=None)


def read_text(path: str, max_chars: int = 200) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:max_chars].strip() or None
    except OSError:
        return None


def log_tail(path: str, lines: int = 200) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 200_000))
            data = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(data.splitlines()[-min(lines, LOG_MAX_LINES):])


class DeployService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def control(self) -> DeployControl:
        row = await self.session.get(DeployControl, 1)
        if row is None:
            row = DeployControl(id=1, mode="auto", interval_minutes=10, schedule_times=[])
            self.session.add(row)
            await self.session.flush()
        return row

    async def _timezone(self) -> str:
        try:
            return (await SettingsService(self.session).get_model("business_hours")).timezone  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - settings unreadable: fall back
            return "America/Chicago"

    async def status(self, user_names: dict[int, str] | None = None) -> DeployStatus:
        row = await self.control()
        settings = get_settings()
        now = _now()
        running = bool(row.started_at and (not row.finished_at or row.finished_at < row.started_at)
                       and now - row.started_at < STUCK_AFTER)
        api = await asyncio.to_thread(git_version, settings.deploy_repo_dir)
        return DeployStatus(
            mode=row.mode, interval_minutes=row.interval_minutes, schedule_times=list(row.schedule_times or []),
            timezone=await self._timezone(), requested_at=row.requested_at,
            requested_by=(user_names or {}).get(row.requested_by or 0), last_check_at=row.last_check_at,
            started_at=row.started_at, finished_at=row.finished_at, running=running, last_reason=row.last_reason,
            last_result=row.last_result, api=api,
            web_build=(read_text(f"{settings.web_app_dir}/BUILD_SHA") or "")[:12] or None,
            cron_seen=bool(row.last_seen_at and now - row.last_seen_at < timedelta(minutes=3)),
        )

    async def configure(self, data: DeployConfig, actor) -> None:
        row = await self.control()
        before = {"mode": row.mode, "interval_minutes": row.interval_minutes, "schedule_times": row.schedule_times}
        if data.mode == "schedule" and not data.schedule_times:
            from app.core.exceptions import ValidationFailedError

            raise ValidationFailedError("Add at least one time for scheduled updates")
        row.mode, row.interval_minutes, row.schedule_times = data.mode, data.interval_minutes, data.schedule_times
        row.updated_by = actor.id
        await self.audit.record("deploy.configure", actor=actor, entity_type="deploy",
                                changes={"before": before, "after": data.model_dump()})
        await self.session.commit()

    async def request_now(self, actor) -> None:
        row = await self.control()
        row.requested_at, row.requested_by = _now(), actor.id
        await self.audit.record("deploy.requested", actor=actor, entity_type="deploy")
        await self.session.commit()

    async def cancel_request(self, actor) -> None:
        row = await self.control()
        row.requested_at = row.requested_by = None
        await self.audit.record("deploy.request_cancelled", actor=actor, entity_type="deploy")
        await self.session.commit()

    # ---- the server's cron job ------------------------------------------
    async def gate_begin(self) -> Decision:
        row = await self.control()
        now = _now()
        row.last_seen_at = now
        decision = decide(now=now, mode=row.mode, interval_minutes=row.interval_minutes,
                          schedule_times=list(row.schedule_times or []), tz=await self._timezone(),
                          requested=row.requested_at is not None, last_check=row.last_check_at)
        if decision.go:
            row.last_check_at, row.started_at, row.last_reason = now, now, decision.reason
            row.requested_at = row.requested_by = None
        await self.session.commit()
        return decision

    async def gate_end(self, ok: bool, summary: str) -> None:
        row = await self.control()
        row.finished_at = _now()
        row.last_result = ("✓ " if ok else "✗ ") + (summary.strip() or ("no changes" if ok else "failed"))[:2000]
        await self.session.commit()
