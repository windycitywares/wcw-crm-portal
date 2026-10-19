"""Shared helpers for working with ORM entities."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _json_safe(value: Any) -> Any:
    """A value the audit log's JSON column can store.

    The `changes` column is JSONB, and SQLAlchemy serialises it with plain `json.dumps`, which
    cannot handle a `Decimal` (a money column) or a `date`/`datetime` (a due date, a close date).
    Those become text, exactly as the audit trail already shows them.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """A dict of the given fields from an ORM entity, for audit diffs.

    Used by every module's `_snapshot()` to build the "before" picture when recording what changed.
    """
    return {field: _json_safe(getattr(obj, field)) for field in fields}
