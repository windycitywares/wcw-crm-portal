"""Delete in two steps, the way business software does it: a delete moves a record to the Trash (soft delete, it can
be restored), and the Trash empties itself after a set number of days (Admin → Settings → Trash, 30 by default).

Each module registers the record types that go to the Trash with `register_trash(TrashType(...))`. A type may name
`children`: checks that list the live records still hanging off one row ("2 deals", "3 people"). A parent with live
children can't be deleted until they are removed or moved; a child can always be deleted on its own. Modules call
`await ensure_no_children(session, key, obj)` at the top of their delete.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import ConflictError

ChildCheck = Callable[[Any, Any], Awaitable[int]]  # (session, row) -> how many live children of this kind


@dataclass(frozen=True)
class TrashType:
    key: str                     # same key as the entity registry ("account", "deal")
    label: str                   # "Account"
    model: type                  # ORM model with SoftDeleteMixin
    title: Callable[[Any], str]  # how a row is named in the Trash
    # (one, many, check): live children that block deleting this row, e.g. ("deal", "deals", count_deals).
    children: tuple[tuple[str, str, ChildCheck], ...] = field(default_factory=tuple)
    # Permanently delete: an extra clean-up before the row itself goes (files on disk, …). Optional.
    before_purge: Callable[[Any, Any], Awaitable[None]] | None = None
    # Purge order: lower first. Children purge before their parents so foreign keys never block.
    order: int = 100
    # Restore through the module's own service when it has rules of its own (e.g. a clashing email). It commits.
    restore: Callable[[Any, int, Any], Awaitable[None]] | None = None


TRASH_TYPES: dict[str, TrashType] = {}


def register_trash(t: TrashType) -> None:
    TRASH_TYPES[t.key] = t


def trash_type(key: str) -> TrashType | None:
    return TRASH_TYPES.get(key)


async def children_of(session: Any, key: str, obj: Any) -> list[str]:
    """'2 deals', '1 supplier' — the live records that keep `obj` from being deleted."""
    t = TRASH_TYPES.get(key)
    found: list[str] = []
    for one, many, check in (t.children if t else ()):
        n = await check(session, obj)
        if n:
            found.append(f"{n} {one if n == 1 else many}")
    return found


async def ensure_no_children(session: Any, key: str, obj: Any) -> None:
    found = await children_of(session, key, obj)
    if found:
        label = TRASH_TYPES[key].label.lower()
        raise ConflictError(f"This {label} still has {', '.join(found)}. Delete or move them first.")


def count_in(table: str, column: str, *, live: bool = True, where: str = "") -> ChildCheck:
    """A child check that counts rows of another module's table pointing at this row, without importing that
    module: `count_in("deals", "customer_id")`. `live` skips rows already in the Trash; `where` adds SQL
    (constants only, e.g. "status NOT IN ('resolved','closed')")."""
    from sqlalchemy import text

    sql = f"SELECT count(*) FROM {table} WHERE {column} = :id"  # noqa: S608 - names are code constants, never input
    if live:
        sql += " AND deleted_at IS NULL"
    if where:
        sql += f" AND ({where})"
    stmt = text(sql)

    async def check(session: Any, obj: Any) -> int:
        return int((await session.execute(stmt, {"id": obj.id})).scalar_one())

    return check


def open_tasks(entity: str) -> ChildCheck:
    """Open tasks about a record (tasks hang off any record by related_type/related_id)."""
    return count_in("tasks", "related_id", where=f"related_type = '{entity}' AND status = 'open'")
