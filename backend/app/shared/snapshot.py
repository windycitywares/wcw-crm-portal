"""Shared helpers for working with ORM entities."""

from typing import Any


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """A dict of the given fields from an ORM entity, for audit diffs.

    Used by every module's `_snapshot()` to build the "before" picture when recording what changed.
    """
    return {field: getattr(obj, field) for field in fields}