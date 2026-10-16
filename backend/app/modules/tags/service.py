"""Tags shared by every record type. Other modules call `TagService(session).tags_for(...)` to show them
and `entity_ids_with_tag(...)` to filter lists."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import check_entity_access
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit.service import AuditService

from .models import Tag
from .repository import TagRepository
from .schemas import TagCreate, TagOut, TagUpdate, TagWithCount

MAX_TAGS_PER_RECORD = 50


def clean(name: str) -> str:
    return " ".join(name.split())[:60]


class TagService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TagRepository(session)
        self.audit = AuditService(session)

    async def search(self, q: str | None, limit: int = 50) -> list[TagWithCount]:
        return [TagWithCount(id=t.id, name=t.name, color=t.color, uses=n)
                for t, n in await self.repo.search_with_counts(q, limit)]

    async def create(self, data: TagCreate, actor) -> TagOut:
        name = clean(data.name)
        if await self.repo.by_keys([name.lower()]):
            raise ConflictError(f"Tag '{name}' already exists")
        tag = await self.repo.add(Tag(name=name, name_key=name.lower(), color=data.color,
                                      created_by=actor.id, updated_by=actor.id))
        await self.audit.record("tag.create", actor=actor, entity_type="tag", entity_id=tag.id, changes={"name": name})
        await self.session.commit()
        return TagOut.model_validate(tag)

    async def update(self, tag_id: int, data: TagUpdate, actor) -> TagOut:
        tag = await self.repo.get(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        changes = data.model_dump(exclude_unset=True)
        if changes.get("name"):
            name = clean(changes["name"])
            other = await self.repo.by_keys([name.lower()])
            if other and other[0].id != tag.id:
                raise ConflictError(f"Tag '{name}' already exists")
            tag.name, tag.name_key = name, name.lower()
        if "color" in changes:
            tag.color = changes["color"]
        tag.updated_by = actor.id
        await self.audit.record("tag.update", actor=actor, entity_type="tag", entity_id=tag.id, changes=changes)
        await self.session.commit()
        await self.session.refresh(tag)
        return TagOut.model_validate(tag)

    async def delete(self, tag_id: int, actor) -> None:
        tag = await self.repo.get(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        await self.audit.record("tag.delete", actor=actor, entity_type="tag", entity_id=tag.id, changes={"name": tag.name})
        await self.repo.hard_delete(tag)  # taggings go with it (ON DELETE CASCADE)
        await self.session.commit()

    # ---- per record -----------------------------------------------------
    async def tags_for(self, entity_type: str, ids: list[int]) -> dict[int, list[TagOut]]:
        out: dict[int, list[TagOut]] = defaultdict(list)
        for eid, tag in await self.repo.for_entities(entity_type, ids):
            out[eid].append(TagOut.model_validate(tag))
        return out

    async def entity_ids_with_tag(self, entity_type: str, tag_id: int) -> list[int]:
        return await self.repo.entity_ids_with_tag(entity_type, tag_id)

    async def list_for(self, user, entity_type: str, entity_id: int) -> list[TagOut]:
        await check_entity_access(self.session, user, entity_type, entity_id, write=False)
        return (await self.tags_for(entity_type, [entity_id])).get(entity_id, [])

    async def set_for(self, user, entity_type: str, entity_id: int, names: list[str], *, commit: bool = True) -> list[TagOut]:
        await check_entity_access(self.session, user, entity_type, entity_id, write=True)
        wanted: dict[str, str] = {}
        for name in map(clean, names):
            if name:
                wanted.setdefault(name.lower(), name)  # first spelling wins
        if len(wanted) > MAX_TAGS_PER_RECORD:
            raise ValidationFailedError(f"At most {MAX_TAGS_PER_RECORD} tags per record")
        existing = {t.name_key: t for t in await self.repo.by_keys(list(wanted))}
        for key, name in wanted.items():
            if key not in existing:  # anyone who may edit the record may add a new tag name
                existing[key] = await self.repo.add(Tag(name=name, name_key=key, created_by=user.id, updated_by=user.id))
        before = [t.name for t in (await self.tags_for(entity_type, [entity_id])).get(entity_id, [])]
        await self.repo.set_for_entity(entity_type, entity_id, {t.id for t in existing.values()}, user.id)
        after = sorted(existing[k].name for k in wanted)
        if sorted(before) != after:
            await self.audit.record("tags.set", actor=user, entity_type=entity_type, entity_id=entity_id,
                                    changes={"tags": [sorted(before), after]})
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return (await self.tags_for(entity_type, [entity_id])).get(entity_id, [])
