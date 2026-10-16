"""When should the server look for updates? Pure logic, unit-tested (no DB, no clock).

The cron job on the server runs every minute and asks `decide(...)`:
  - a pending "Deploy now" request always wins (within a minute of the click);
  - paused  → never automatically;
  - auto    → every `interval_minutes`;
  - schedule→ once each time a listed time of day (in the business time zone) has passed.
"Deploy" means "check GitHub and install what's new" — nothing happens if nothing changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

MODES = ("auto", "schedule", "paused")


@dataclass(frozen=True)
class Decision:
    go: bool
    reason: str


def _times(values: list[str]) -> list[time]:
    out = []
    for v in values:
        hh, mm = v.split(":")
        out.append(time(int(hh), int(mm)))
    return sorted(out)


def decide(*, now: datetime, mode: str, interval_minutes: int, schedule_times: list[str], tz: str,
           requested: bool, last_check: datetime | None) -> Decision:
    if requested:
        return Decision(True, "manual")
    if mode == "paused":
        return Decision(False, "paused")
    if mode == "auto":
        if last_check is None or now - last_check >= timedelta(minutes=interval_minutes) - timedelta(seconds=20):
            return Decision(True, "interval")
        return Decision(False, "waiting")
    if mode == "schedule":
        zone = ZoneInfo(tz)
        local_now = now.astimezone(zone)
        since = (last_check or now - timedelta(days=1)).astimezone(zone)
        for day in (local_now.date() - timedelta(days=1), local_now.date()):
            for t in _times(schedule_times):
                slot = datetime.combine(day, t, tzinfo=zone)
                if since < slot <= local_now:
                    return Decision(True, f"scheduled {t:%H:%M}")
        return Decision(False, "waiting for schedule")
    return Decision(False, f"unknown mode {mode}")
