"""Add *business* time to a moment, using the Business hours settings (SPEC §3.5 / §9).

SLA targets read like "respond within 4 business hours" or "resolve in 3 business days". That means the
clock only runs while the team is open: days that have hours in Admin → Settings → Business hours, minus
the configured holidays, in the configured time zone.

    add_business_minutes(now, 3 * 8 * 60, hours)   # 3 business days from now
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.modules.settings.groups import DAYS, BusinessHours

_HORIZON_DAYS = 400  # safety stop (~13 months) so a misconfigured calendar can't loop forever


def _hm(value: str) -> tuple[int, int]:
    return int(value[:2]), int(value[3:])


def _next_opening(moment: datetime, hours: BusinessHours, tz: ZoneInfo, *, strictly_after: bool) -> datetime:
    """The next moment the team is open, at or after `moment` (or strictly after it)."""
    holidays = set(hours.holidays)
    cursor = moment
    for _ in range(_HORIZON_DAYS):
        day = hours.days.get(DAYS[cursor.weekday()])
        if day is not None and cursor.date() not in holidays:
            open_h, open_m = _hm(day.open)
            close_h, close_m = _hm(day.close)
            opens = cursor.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
            closes = cursor.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
            if not strictly_after and opens <= cursor < closes:
                return cursor  # already inside opening hours
            if opens > cursor:
                return opens
        cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return moment  # no open day found: leave the moment unchanged


def add_business_minutes(start: datetime, minutes: int, hours: BusinessHours) -> datetime:
    """`start` plus `minutes` of open time, returned in UTC. A non-positive `minutes` returns `start`."""
    tz = ZoneInfo(hours.timezone)
    remaining = max(0, int(minutes))
    moment = start.astimezone(tz)
    if remaining == 0:
        return moment.astimezone(timezone.utc)

    moment = _next_opening(moment, hours, tz, strictly_after=False)
    holidays = set(hours.holidays)
    for _ in range(_HORIZON_DAYS):
        day = hours.days.get(DAYS[moment.weekday()])
        if day is None or moment.date() in holidays:
            moment = _next_opening(moment, hours, tz, strictly_after=False)
            continue
        open_h, open_m = _hm(day.open)
        close_h, close_m = _hm(day.close)
        opens = moment.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        closes = moment.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        if moment < opens:
            moment = opens
        if moment >= closes:
            moment = _next_opening(closes, hours, tz, strictly_after=True)
            continue
        available = (closes - moment).total_seconds() / 60
        if remaining <= available:
            return (moment + timedelta(minutes=remaining)).astimezone(timezone.utc)
        remaining -= available
        moment = _next_opening(closes, hours, tz, strictly_after=True)
    return moment.astimezone(timezone.utc)
