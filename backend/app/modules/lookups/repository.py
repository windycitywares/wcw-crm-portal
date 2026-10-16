from collections.abc import Sequence

from sqlalchemy import func, select

from app.shared.repository import BaseRepository

from .models import LookupValue


class LookupRepository(BaseRepository[LookupValue]):
    model = LookupValue

    async def for_kind(self, kind: str, *, include_inactive: bool = True) -> Sequence[LookupValue]:
        stmt = select(LookupValue).where(LookupValue.kind == kind)
        if not include_inactive:
            stmt = stmt.where(LookupValue.is_active.is_(True))
        return await self.list(stmt.order_by(LookupValue.sort_order, LookupValue.id))

    async def all(self) -> Sequence[LookupValue]:
        return await self.list(select(LookupValue).order_by(LookupValue.kind, LookupValue.sort_order, LookupValue.id))

    async def by_key(self, kind: str, key: str) -> LookupValue | None:
        stmt = select(LookupValue).where(LookupValue.kind == kind, LookupValue.key == key)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def next_sort(self, kind: str) -> int:
        stmt = select(func.coalesce(func.max(LookupValue.sort_order), -1)).where(LookupValue.kind == kind)
        return (await self.session.execute(stmt)).scalar_one() + 1
