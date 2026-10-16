"""Generic repository: the only place that builds queries for a model.

Module repositories subclass it and add their own finders:

    class CustomerRepository(BaseRepository[Customer]):
        model = Customer

        async def by_email(self, email: str) -> Customer | None: ...

Soft-deleted rows are hidden by default for models with `SoftDeleteMixin`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.shared.models import Base, SoftDeleteMixin

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    model: type[M]

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- query building -------------------------------------------------
    @property
    def _soft_deletes(self) -> bool:
        return issubclass(self.model, SoftDeleteMixin)

    def query(self, *, include_deleted: bool = False) -> Select[tuple[M]]:
        stmt = select(self.model)
        if self._soft_deletes and not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    # ---- reads ----------------------------------------------------------
    async def get(self, id_: int, *, include_deleted: bool = False) -> M | None:
        stmt = self.query(include_deleted=include_deleted).where(self.model.id == id_)  # type: ignore[attr-defined]
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, stmt: Select[tuple[M]] | None = None) -> Sequence[M]:
        return (await self.session.execute(stmt if stmt is not None else self.query())).scalars().all()

    async def count(self, stmt: Select[tuple[M]] | None = None) -> int:
        base = stmt if stmt is not None else self.query()
        return (await self.session.execute(select(func.count()).select_from(base.order_by(None).subquery()))).scalar_one()

    async def paginate(self, stmt: Select[tuple[M]], params: PageParams) -> tuple[Sequence[M], int]:
        total = await self.count(stmt)
        rows = await self.list(stmt.limit(params.page_size).offset(params.offset))
        return rows, total

    # ---- writes ---------------------------------------------------------
    async def add(self, obj: M) -> M:
        self.session.add(obj)
        await self.session.flush()
        return obj

    def apply(self, obj: M, data: dict[str, Any]) -> M:
        for key, value in data.items():
            setattr(obj, key, value)
        return obj

    async def soft_delete(self, obj: M) -> None:
        if not self._soft_deletes:
            raise TypeError(f"{self.model.__name__} doesn't support soft delete")
        obj.deleted_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        await self.session.flush()

    async def restore(self, obj: M) -> None:
        obj.deleted_at = None  # type: ignore[attr-defined]
        await self.session.flush()

    async def hard_delete(self, obj: M) -> None:
        await self.session.delete(obj)
        await self.session.flush()
