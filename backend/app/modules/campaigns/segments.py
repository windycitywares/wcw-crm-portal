"""Dynamic audiences (SPEC §3.6): the rules behind a segment.

A segment is a `target_lists` row with `kind="segment"` and `rules` in JSON — a small, closed query builder:

    {"match": "all", "rules": [{"field": "orders_count", "op": "gte", "value": 3},
                               {"field": "tags", "op": "has_any", "value": [2, 5]}]}

The vocabulary is fixed (FIELDS): a field maps to a column, an op to a comparison, and no part of a rule ever
reaches SQL as text — so a rule can only be as expressive as this module allows, and a saved rule that stops
making sense (a field removed in a later release) is refused with a 422 rather than becoming a wild query.

A segment has no member rows: it is evaluated as a query whenever its count is asked for, its members are
listed, or (next batch) a campaign goes out, so it is always current and there is no sync job to go stale.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import ValidationFailedError
from app.modules.customers.models import STATUSES, Customer
from app.modules.tags.models import Tagging

from . import consent

CUSTOMER = "customer"  # `app.core.entities`'s key for a customer (what taggings use)
MAX_RULES = 20


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# What a rule may say, and what the editor should offer for its value. `value_kind` tells the web how to ask
# for a value: a lookup picker (customer_type / lead_source), a tag or staff picker, a status, a number, an
# amount, a number of days, or a yes/no.
FIELDS: tuple[dict[str, Any], ...] = (
    {"field": "customer_type", "label": "Customer type", "value_kind": "customer_type", "ops": ("in", "not_in")},
    {"field": "source", "label": "Came from", "value_kind": "lead_source", "ops": ("in", "not_in")},
    {"field": "status", "label": "Status", "value_kind": "status", "ops": ("is",)},
    {"field": "tags", "label": "Tags", "value_kind": "tags", "ops": ("has_any", "has_all", "has_none")},
    {"field": "owner_id", "label": "Owner", "value_kind": "users", "ops": ("in", "none")},
    {"field": "orders_count", "label": "Orders placed", "value_kind": "number", "ops": ("gte", "lte", "eq")},
    {"field": "total_spent", "label": "Total spent", "value_kind": "money", "ops": ("gte", "lte")},
    {"field": "last_order_at", "label": "Last order", "value_kind": "days",
     "ops": ("within_days", "not_within_days", "never")},
    {"field": "created_at", "label": "Customer since", "value_kind": "days",
     "ops": ("within_days", "not_within_days")},
    {"field": "marketing_consent", "label": "Agreed to marketing email", "value_kind": "yesno", "ops": ("is",)},
)

OPS: dict[str, str] = {
    "in": "is any of",
    "not_in": "is none of",
    "is": "is",
    "none": "is nobody",
    "has_any": "has any of",
    "has_all": "has all of",
    "has_none": "has none of",
    "gte": "is at least",
    "lte": "is at most",
    "eq": "is exactly",
    "within_days": "in the last … days",
    "not_within_days": "not in the last … days",
    "never": "never",
}

_SPEC = {item["field"]: item for item in FIELDS}
FieldName = Literal["customer_type", "source", "status", "tags", "owner_id", "orders_count", "total_spent",
                    "last_order_at", "created_at", "marketing_consent"]


# ---- value checks (each one refuses what it cannot compare) ------------------------------------------


def _picked(value: Any, what: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"“{what}” takes a list of values")
    if not value:
        raise ValueError(f"Pick at least one value for “{what}”")
    if len(value) > 50:
        raise ValueError(f"Pick 50 values at most for “{what}”")
    return list(value)


def _words(value: Any, what: str) -> list[str]:
    out = [str(item).strip() for item in _picked(value, what)]
    out = [item for item in out if item]
    if not out:
        raise ValueError(f"Pick at least one value for “{what}”")
    return out


def _ids(value: Any, what: str) -> list[int]:
    out: list[int] = []
    for item in _picked(value, what):
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise ValueError(f"“{what}” takes ids, not {item!r}")
        out.append(item)
    return out


def _one_of(value: Any, allowed: tuple[str, ...], what: str) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        raise ValueError(f"“{what}” has to be one of: {', '.join(allowed)}")
    return text


def _whole(value: Any, low: int, high: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"“{what}” takes a whole number")
    if not low <= value <= high:
        raise ValueError(f"“{what}” has to be between {low} and {high}")
    return value


def _amount(value: Any, what: str) -> float:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"“{what}” takes a number") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"“{what}” cannot be negative")
    return float(amount)


# ---- rules --------------------------------------------------------------------------------------------


class SegmentRule(BaseModel):
    """One condition, e.g. `orders_count` `gte` `3`, or `tags` `has_any` `[2, 5]`."""

    field: FieldName
    op: str
    value: Any = None

    @model_validator(mode="after")
    def _value_fits(self) -> "SegmentRule":
        spec = _SPEC[self.field]
        what = spec["label"]
        if self.op not in spec["ops"]:
            raise ValueError(f"“{OPS.get(self.op, self.op)}” cannot be used with {what.lower()}")
        kind = spec["value_kind"]
        if self.op in ("none", "never"):
            self.value = None
        elif kind == "status":
            self.value = _one_of(self.value, STATUSES, what)
        elif kind in ("customer_type", "lead_source"):
            self.value = _words(self.value, what)
        elif kind in ("tags", "users"):
            self.value = _ids(self.value, what)
        elif kind == "yesno":
            if not isinstance(self.value, bool):
                raise ValueError(f"“{what}” is a yes or a no")
        elif kind == "money":
            self.value = _amount(self.value, what)
        elif kind == "days":
            self.value = _whole(self.value, 1, 3650, what)
        else:  # a count
            self.value = _whole(self.value, 0, 1_000_000, what)
        return self


class SegmentRules(BaseModel):
    """A segment's whole rule set: every rule (`all`) or any of them (`any`) has to hold.

    At least one rule: a segment with none would be every customer in the CRM, which is never what anyone
    means when they save one.
    """

    match: Literal["all", "any"] = "all"
    rules: list[SegmentRule] = Field(min_length=1, max_length=MAX_RULES)


def fields() -> list[dict[str, Any]]:
    """The vocabulary a rule builder offers: the fields, how to ask for a value, and each field's ops."""
    return [
        {"field": item["field"], "label": item["label"], "value_kind": item["value_kind"],
         "ops": [{"op": op, "label": OPS[op]} for op in item["ops"]]}
        for item in FIELDS
    ]


def parse(rules: dict[str, Any] | None) -> SegmentRules:
    """Read stored rules, turning anything this release no longer understands into a 422."""
    try:
        return SegmentRules.model_validate(rules or {})
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first.get("loc", ())) or "rules"
        raise ValidationFailedError(
            f"The segment's rules are not understood: {where} — {first.get('msg', 'invalid')}") from exc


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=int(days))


def _compare(column: Any, op: str, value: Any) -> ColumnElement[bool]:
    if op == "gte":
        return column >= value
    if op == "lte":
        return column <= value
    return column == value


def _condition(rule: SegmentRule) -> ColumnElement[bool]:
    field, op, value = rule.field, rule.op, rule.value
    if field in ("customer_type", "source"):
        column = Customer.customer_type if field == "customer_type" else Customer.source
        if op == "in":
            return column.in_(value)
        # "is none of" includes the customers whose type is not set at all
        return or_(column.is_(None), column.not_in(value))
    if field == "status":
        return Customer.status == value
    if field == "tags":
        tagged = (select(Tagging.tag_id)
                  .where(Tagging.entity_type == CUSTOMER, Tagging.entity_id == Customer.id,
                         Tagging.tag_id.in_(value)))
        if op == "has_any":
            return tagged.exists()
        if op == "has_none":
            return ~tagged.exists()
        counted = (select(func.count(func.distinct(Tagging.tag_id)))
                   .where(Tagging.entity_type == CUSTOMER, Tagging.entity_id == Customer.id,
                          Tagging.tag_id.in_(value)).scalar_subquery())
        return counted >= len(value)
    if field == "owner_id":
        return Customer.owner_id.is_(None) if op == "none" else Customer.owner_id.in_(value)
    if field == "orders_count":
        return _compare(Customer.orders_count, op, value)
    if field == "total_spent":
        return _compare(Customer.total_spent, op, Decimal(str(value)))
    if field == "last_order_at":
        if op == "never":
            return Customer.last_order_at.is_(None)
        cutoff = _cutoff(value)
        if op == "within_days":
            return Customer.last_order_at >= cutoff
        # "not in the last N days" includes the customers who never ordered
        return or_(Customer.last_order_at.is_(None), Customer.last_order_at < cutoff)
    if field == "created_at":
        cutoff = _cutoff(value)
        return Customer.created_at >= cutoff if op == "within_days" else Customer.created_at < cutoff
    # marketing_consent — the model has already checked the field name
    return Customer.marketing_consent.is_(bool(value))


def condition(rules: dict[str, Any] | None) -> ColumnElement[bool]:
    """The whole rule set as one SQL condition over `Customer`."""
    parsed = parse(rules)
    parts = [_condition(rule) for rule in parsed.rules]
    return and_(*parts) if parsed.match == "all" else or_(*parts)


def members_stmt(rules: dict[str, Any] | None, *, q: str | None = None) -> Select[tuple[Customer]]:
    """The customers a segment matches, in name order and searchable like any customer list."""
    stmt = select(Customer).where(Customer.deleted_at.is_(None), condition(rules))
    if q:
        pattern = f"%{escape_like(q.strip().lower())}%"
        stmt = stmt.where(or_(
            func.lower(Customer.first_name).like(pattern), func.lower(Customer.last_name).like(pattern),
            func.lower(Customer.company).like(pattern), func.lower(Customer.email).like(pattern),
        ))
    return stmt.order_by(func.lower(Customer.first_name), func.lower(Customer.last_name), Customer.id)


def count_stmt(rules: dict[str, Any] | None, *, reachable: bool = False) -> Select[tuple[int]]:
    """How many customers match — and, with `reachable`, how many of those a campaign could email."""
    stmt = select(func.count()).select_from(Customer).where(Customer.deleted_at.is_(None), condition(rules))
    if reachable:
        stmt = stmt.where(*consent.conditions())
    return stmt
