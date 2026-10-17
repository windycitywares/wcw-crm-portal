"""Registry of record types that shared features (notes, tags, timeline, custom fields) can attach to.

Each feature module registers its record types once, e.g. in the customers module:

    register_entity(EntityType(
        key="customer", label="Customer",
        view=(Permission.CUSTOMERS_VIEW,), edit=(Permission.CUSTOMERS_EDIT_OWN, Permission.CUSTOMERS_EDIT_ANY),
        exists=customer_exists,
    ))

Notes/tags/timeline then work for `/entities/customer/{id}/…` with no change to those modules
(open/closed). `view`/`edit` are "any of" permission sets; record-level ownership rules stay in the
owning module and are applied through `can_edit` when given.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.events import DomainEvent
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.permissions import Permission, has_permission

ExistsFn = Callable[[Any, int], Awaitable[bool]]  # (session, entity_id) -> bool
CanEditFn = Callable[[Any, Any, int], Awaitable[bool]]  # (session, user, entity_id) -> bool
LabelsFn = Callable[[Any, list[int]], Awaitable[dict[int, str]]]  # (session, ids) -> {id: display name}


@dataclass(frozen=True)
class EntityType:
    key: str
    label: str
    view: tuple[Permission, ...]
    edit: tuple[Permission, ...]
    exists: ExistsFn
    can_edit: CanEditFn | None = None  # optional record-level rule (e.g. "own records only")
    labels: LabelsFn | None = None  # display names, so other records can show what they point at


_REGISTRY: dict[str, EntityType] = {}


def register_entity(entity: EntityType) -> None:
    _REGISTRY[entity.key] = entity


def unregister_entity(key: str) -> None:  # tests
    _REGISTRY.pop(key, None)


def entity_types() -> list[EntityType]:
    return list(_REGISTRY.values())


def get_entity_type(key: str) -> EntityType:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise NotFoundError(f"Unknown record type: {key}") from None


async def entity_labels(session: Any, entity_type: str, ids: list[int]) -> dict[int, str]:
    """Display names for records of one type (empty when the type has no `labels` function)."""
    et = _REGISTRY.get(entity_type)
    if et is None or et.labels is None or not ids:
        return {}
    return await et.labels(session, sorted(set(ids)))


async def check_entity_access(session: Any, user: Any, entity_type: str, entity_id: int, *, write: bool) -> EntityType:
    """Raise unless `user` may read (or change) record `entity_type/entity_id`, and the record exists."""
    et = get_entity_type(entity_type)
    perms = et.edit if write else et.view
    if not any(has_permission(user.role, p) for p in perms):
        raise PermissionDeniedError("You don't have permission to do that")
    if not await et.exists(session, entity_id):
        raise NotFoundError(f"{et.label} not found")
    if write and et.can_edit is not None and not await et.can_edit(session, user, entity_id):
        raise PermissionDeniedError(f"You can only change your own {et.label.lower()} records")
    return et


@dataclass(frozen=True, kw_only=True)
class RecordsMerged(DomainEvent):
    """`from_id` was merged into `into_id` (e.g. a duplicate customer). Every module that keeps rows pointing at
    records (notes, timeline, tags, shop orders …) subscribes and moves its own rows, in the same transaction."""

    entity_type: str
    from_id: int
    into_id: int
