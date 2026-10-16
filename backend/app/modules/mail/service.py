"""The email outbox: queue, send within the limits set in Admin → Settings → Email, retry with back-off.

    await MailService(session).queue(Mail(...), category="system")   # caller commits
    OutboxEmailSender(session)                                        # EmailSender: queue + try now

The SMTP transport is built from the saved settings; tests pass `transport=` instead.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email import EmailSender, Mail, SmtpEmailSender
from app.modules.settings.groups import EmailSettings
from app.modules.settings.service import SettingsService, smtp_config

from .models import FAILED, QUEUED, SENT, EmailOutbox

MAX_ATTEMPTS = 5
GIVE_UP_AFTER = timedelta(days=3)  # unsent mail (e.g. email switched off) older than this is marked failed
OFF = "Outgoing email is off — set it up in Admin → Settings → Email"
TransportFactory = Callable[[EmailSettings], EmailSender]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _smtp(settings: EmailSettings) -> EmailSender:
    return SmtpEmailSender(smtp_config(settings))


class MailService:
    def __init__(self, session: AsyncSession, transport: TransportFactory | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self.session = session
        self.transport_factory = transport or _smtp
        self.sleep = sleep

    async def queue(self, mail: Mail, category: str = "system", send_after: datetime | None = None) -> EmailOutbox:
        row = EmailOutbox(to_email=mail.to, subject=mail.subject[:300], text=mail.text, html=mail.html,
                          reply_to=mail.reply_to, headers=mail.headers or None, category=category,
                          send_after=send_after or _now())
        self.session.add(row)
        await self.session.flush()
        return row

    async def settings(self) -> EmailSettings:
        return await SettingsService(self.session).get_model("email")  # type: ignore[return-value]

    async def _sent_since(self, since: datetime) -> int:
        stmt = select(func.count()).select_from(EmailOutbox).where(EmailOutbox.status == SENT, EmailOutbox.sent_at >= since)
        return (await self.session.execute(stmt)).scalar_one()

    async def room(self, settings: EmailSettings) -> int:
        """How many messages may go out right now (daily and per-minute limits)."""
        now = _now()
        day = settings.daily_limit - await self._sent_since(now - timedelta(hours=24))
        minute = settings.per_minute - await self._sent_since(now - timedelta(minutes=1))
        return max(0, min(day, minute))

    async def _attempt(self, row: EmailOutbox, transport: EmailSender, settings: EmailSettings) -> bool:
        row.attempts += 1
        try:
            await transport.send(Mail(to=row.to_email, subject=row.subject, text=row.text, html=row.html,
                                      reply_to=row.reply_to or (str(settings.reply_to) or None),
                                      headers=row.headers or {}))
        except Exception as exc:  # noqa: BLE001 - keep the reason, retry later
            row.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = FAILED
            else:
                row.send_after = _now() + timedelta(minutes=5 * 2 ** (row.attempts - 1))  # 5, 10, 20, 40 min
            return False
        row.status, row.sent_at, row.last_error = SENT, _now(), None
        return True

    async def try_send_now(self, row: EmailOutbox) -> bool:
        """Send one queued message immediately if email is on and limits allow; otherwise the job will."""
        settings = await self.settings()
        if not settings.enabled:
            row.last_error = OFF
            return False
        if await self.room(settings) <= 0:
            return False
        return await self._attempt(row, self.transport_factory(settings), settings)

    async def deliver_due(self, max_seconds: float = 480) -> str | None:
        """Background job: send what's due, pacing to the per-minute limit, stopping at the daily limit."""
        now = _now()
        stale = (await self.session.execute(select(EmailOutbox).where(
            EmailOutbox.status == QUEUED, EmailOutbox.created_at < now - GIVE_UP_AFTER))).scalars().all()
        for row in stale:
            row.status, row.last_error = FAILED, (row.last_error or "Not sent within 3 days")
        settings = await self.settings()
        if not settings.enabled:
            await self.session.commit()
            return f"{len(stale)} expired; email is off" if stale else None
        due = (await self.session.execute(
            select(EmailOutbox).where(EmailOutbox.status == QUEUED, EmailOutbox.send_after <= now)
            .order_by(EmailOutbox.category != "system", EmailOutbox.send_after, EmailOutbox.id)  # system mail first
            .limit(1000)
        )).scalars().all()
        transport = self.transport_factory(settings)
        started, sent, failed = time.monotonic(), 0, 0
        gap = 60.0 / settings.per_minute
        for row in due:
            if time.monotonic() - started > max_seconds:
                break
            if await self.room(settings) <= 0:
                if settings.daily_limit - await self._sent_since(_now() - timedelta(hours=24)) <= 0:
                    break  # daily limit reached — the rest waits for the next runs
                await self.sleep(gap)
            if await self._attempt(row, transport, settings):
                sent += 1
            else:
                failed += 1
            await self.session.commit()
            await self.sleep(gap)
        await self.session.commit()
        if not (sent or failed or stale):
            return None
        return f"sent {sent}, failed {failed}, expired {len(stale)}, waiting {max(0, len(due) - sent - failed)}"


class OutboxEmailSender:
    """EmailSender used by the app: queue the message, then try to send it straight away."""

    def __init__(self, session: AsyncSession, transport: TransportFactory | None = None):
        self.service = MailService(session, transport)
        self.session = session

    async def send(self, mail: Mail) -> None:
        row = await self.service.queue(mail)
        await self.session.commit()
        await self.service.try_send_now(row)
        await self.session.commit()
