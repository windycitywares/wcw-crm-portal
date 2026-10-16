from collections.abc import Sequence

from sqlalchemy import delete, func, select

from app.shared.repository import BaseRepository

from .models import Tag, Tagging


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TagRepository(BaseRepository[Tag]):
    model = Tag

    async def by_keys(self, keys: list[str]) -> Sequence[Tag]:
        if not keys:
            return []
        return await self.list(select(Tag).where(Tag.name_key.in_(keys)))

    async def search_with_counts(self, q: str | None, limit: int) -> list[tuple[Tag, int]]:
        uses = select(Tagging.tag_id, func.count().label("n")).group_by(Tagging.tag_id).subquery()
        stmt = select(Tag, func.coalesce(uses.c.n, 0)).outerjoin(uses, uses.c.tag_id == Tag.id)
        if q:
            stmt = stmt.where(Tag.name_key.like(f"%{escape_like(q.strip().lower())}%"))
        stmt = stmt.order_by(func.coalesce(uses.c.n, 0).desc(), Tag.name_key).limit(limit)
        return [(t, n) for t, n in (await self.session.execute(stmt)).all()]

    async def for_entities(self, entity_type: str, ids: list[int]) -> list[tuple[int, Tag]]:
        if not ids:
            return []
        stmt = (select(Tagging.entity_id, Tag).join(Tag, Tag.id == Tagging.tag_id)
                .where(Tagging.entity_type == entity_type, Tagging.entity_id.in_(ids)).order_by(Tag.name_key))
        return [(eid, t) for eid, t in (await self.session.execute(stmt)).all()]

    async def set_for_entity(self, entity_type: str, entity_id: int, tag_ids: set[int], actor_id: int | None) -> None:
        current = set((await self.session.execute(
            select(Tagging.tag_id).where(Tagging.entity_type == entity_type, Tagging.entity_id == entity_id)
        )).scalars())
        if current - tag_ids:
            await self.session.execute(delete(Tagging).where(
                Tagging.entity_type == entity_type, Tagging.entity_id == entity_id, Tagging.tag_id.in_(current - tag_ids)))
        for tag_id in tag_ids - current:
            self.session.add(Tagging(tag_id=tag_id, entity_type=entity_type, entity_id=entity_id, created_by=actor_id))
        await self.session.flush()

    async def entity_ids_with_tag(self, entity_type: str, tag_id: int) -> list[int]:
        stmt = select(Tagging.entity_id).where(Tagging.entity_type == entity_type, Tagging.tag_id == tag_id)
        return list((await self.session.execute(stmt)).scalars())
