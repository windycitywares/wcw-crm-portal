from collections.abc import Sequence

from sqlalchemy import func, select

from app.shared.repository import BaseRepository

from .models import CustomFieldDef


class FieldDefRepository(BaseRepository[CustomFieldDef]):
    model = CustomFieldDef

    async def for_entity(self, entity_type: str, *, active_only: bool = False) -> Sequence[CustomFieldDef]:
        stmt = select(CustomFieldDef).where(CustomFieldDef.entity_type == entity_type)
        if active_only:
            stmt = stmt.where(CustomFieldDef.is_active.is_(True))
        return await self.list(stmt.order_by(CustomFieldDef.sort_order, CustomFieldDef.id))

    async def by_key(self, entity_type: str, key: str) -> CustomFieldDef | None:
        stmt = select(CustomFieldDef).where(CustomFieldDef.entity_type == entity_type, CustomFieldDef.key == key)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def next_sort(self, entity_type: str) -> int:
        stmt = select(func.coalesce(func.max(CustomFieldDef.sort_order), -1)).where(CustomFieldDef.entity_type == entity_type)
        return (await self.session.execute(stmt)).scalar_one() + 1
