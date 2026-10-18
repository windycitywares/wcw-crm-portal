"""Shared time helpers."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """The current time in UTC, timezone-aware.

    Used everywhere a timestamp is written to the database or compared against one. All datetimes in this
    app are stored in UTC; conversion to local time is a display concern.
    """
    return datetime.now(timezone.utc)