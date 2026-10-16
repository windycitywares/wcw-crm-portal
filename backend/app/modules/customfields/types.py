"""Field types for admin-defined custom fields — one validator per type (add a type = add an entry).

Each validator takes the raw JSON value and the field definition, and returns the value to store
(normalised) or raises ValueError with a message for the person filling in the form.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL = re.compile(r"^https?://[^\s]+$", re.I)


def _text(max_len: int) -> Callable[[Any, Any], str]:
    def check(value: Any, _field: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("must be text")
        value = value.strip()
        if len(value) > max_len:
            raise ValueError(f"must be at most {max_len} characters")
        return value

    return check


def _number(value: Any, _field: Any) -> float | int:
    if isinstance(value, bool):
        raise ValueError("must be a number")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("must be a number") from None
    if not number.is_finite():
        raise ValueError("must be a number")
    return int(number) if number == number.to_integral_value() else float(number)


def _date(value: Any, _field: Any) -> str:
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise ValueError("must be a date (YYYY-MM-DD)") from None


def _checkbox(value: Any, _field: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in ("true", "1", 1):
        return True
    if value in ("false", "0", 0):
        return False
    raise ValueError("must be yes or no")


def _select(value: Any, field: Any) -> str:
    if value not in (field.options or []):
        raise ValueError("must be one of the listed options")
    return value


def _multiselect(value: Any, field: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("must be a list of options")
    allowed = field.options or []
    bad = [v for v in value if v not in allowed]
    if bad:
        raise ValueError(f"has values that aren't options: {', '.join(map(str, bad))}")
    return [v for v in allowed if v in value]  # option order, no duplicates


def _email(value: Any, field: Any) -> str:
    value = _text(320)(value, field).lower()
    if not EMAIL.match(value):
        raise ValueError("must be an email address")
    return value


def _url(value: Any, field: Any) -> str:
    value = _text(2000)(value, field)
    if not URL.match(value):
        raise ValueError("must be a web address starting with http:// or https://")
    return value


FIELD_TYPES: dict[str, tuple[str, Callable[[Any, Any], Any]]] = {
    "text": ("Short text", _text(255)),
    "textarea": ("Long text", _text(5000)),
    "number": ("Number", _number),
    "date": ("Date", _date),
    "checkbox": ("Yes / no", _checkbox),
    "select": ("Pick one", _select),
    "multiselect": ("Pick several", _multiselect),
    "email": ("Email", _email),
    "url": ("Web address", _url),
}
CHOICE_TYPES = {"select", "multiselect"}


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []
