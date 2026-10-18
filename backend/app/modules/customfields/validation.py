"""Pure validation of custom-field values (no database), so it's easy to test and reuse."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.exceptions import ValidationFailedError

from .types import FIELD_TYPES, is_empty


class FieldDef(Protocol):
    key: str
    label: str
    field_type: str
    options: list[Any] | None
    required: bool
    is_active: bool


def check_values(defs: list[FieldDef], incoming: dict[str, Any] | None, existing: dict[str, Any] | None) -> dict[str, Any]:
    """Merge `incoming` into `existing` and return the dict to store, or raise with every problem listed.

    - unknown keys are rejected; empty values remove the key;
    - a deactivated field keeps its stored value but can't be given a new one;
    - active required fields must end up with a value.
    """
    by_key = {d.key: d for d in defs}
    merged = dict(existing or {})
    errors: list[str] = []
    failed: set[str] = set()
    for key, value in (incoming or {}).items():
        field = by_key.get(key)
        if field is None:
            errors.append(f"{key}: unknown field")
            continue
        if not field.is_active:
            if value != merged.get(key):
                errors.append(f"{field.label}: this field is no longer in use")
            continue
        if is_empty(value):
            merged.pop(key, None)
            continue
        try:
            merged[key] = FIELD_TYPES[field.field_type]["check"](value, field)
        except ValueError as exc:
            errors.append(f"{field.label} {exc}")
            failed.add(key)
    for field in defs:
        if field.is_active and field.required and field.key not in failed and is_empty(merged.get(field.key)):
            errors.append(f"{field.label} is required")
    if errors:
        raise ValidationFailedError("; ".join(errors))
    return merged
