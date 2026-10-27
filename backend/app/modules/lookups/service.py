"""Admin-editable type lists. Other modules validate stored keys with `LookupService(session).require(kind, key)`."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit.service import AuditService, diff
from app.shared.snapshot import snapshot
from app.shared.text import slugify

from .kinds import KINDS, Kind
from .models import LookupValue
from .repository import LookupRepository
from .schemas import KindOut, LookupCreate, LookupOut, LookupUpdate



class LookupService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LookupRepository(session)
        self.audit = AuditService(session)

    @staticmethod
    def kind(kind: str) -> Kind:
        try:
            return KINDS[kind]
        except KeyError:
            raise NotFoundError(f"Unknown type list: {kind}") from None

    # ---- reads ----------------------------------------------------------
    async def kinds(self) -> list[KindOut]:
        by_kind: dict[str, list[LookupOut]] = {k: [] for k in KINDS}
        for v in await self.repo.all():
            if v.kind in by_kind:
                by_kind[v.kind].append(LookupOut.model_validate(v))
        return [KindOut(key=k.key, label=k.label, description=k.description, values=by_kind[k.key]) for k in KINDS.values()]

    async def values(self, kind: str, *, include_inactive: bool = True) -> list[LookupOut]:
        self.kind(kind)
        return [LookupOut.model_validate(v) for v in await self.repo.for_kind(kind, include_inactive=include_inactive)]

    async def require(self, kind: str, key: str | None, *, allow_inactive_key: str | None = None) -> str | None:
        """Validate a key another module wants to store. None stays None.

        `allow_inactive_key` lets a record keep the (now deactivated) value it already has.
        """
        if key is None:
            return None
        value = await self.repo.by_key(kind, key)
        if value is None or (not value.is_active and key != allow_inactive_key):
            raise ValidationFailedError(f"'{key}' isn't an active {self.kind(kind).label.lower()} value")
        return key

    # ---- writes ---------------------------------------------------------
    async def _get(self, kind: str, value_id: int) -> LookupValue:
        value = await self.repo.get(value_id)
        if value is None or value.kind != kind:
            raise NotFoundError("Value not found")
        return value

    async def create(self, kind: str, data: LookupCreate, actor) -> LookupOut:
        self.kind(kind)
        key = data.key or slugify(data.label)
        if await self.repo.by_key(kind, key):
            raise ConflictError(f"'{key}' already exists in this list")
        value = await self.repo.add(LookupValue(
            kind=kind, key=key, label=data.label.strip(), color=data.color,
            sort_order=await self.repo.next_sort(kind), created_by=actor.id, updated_by=actor.id,
        ))
        await self.audit.record("lookup.create", actor=actor, entity_type="lookup", entity_id=value.id,
                                changes={"kind": kind, "key": key, **diff({}, snapshot(value, ("label", "color", "is_active", "sort_order")))})
        await self.session.commit()
        await self.session.refresh(value)
        return LookupOut.model_validate(value)

    async def update(self, kind: str, value_id: int, data: LookupUpdate, actor) -> LookupOut:
        value = await self._get(kind, value_id)
        before = snapshot(value, ("label", "color", "is_active", "sort_order"))
        changes = data.model_dump(exclude_unset=True)
        if "label" in changes and changes["label"] is None:
            changes.pop("label")
        if "is_active" in changes and changes["is_active"] is None:
            changes.pop("is_active")
        self.repo.apply(value, changes)
        value.updated_by = actor.id
        await self.audit.record("lookup.update", actor=actor, entity_type="lookup", entity_id=value.id,
                                changes=diff(before, snapshot(value, ("label", "color", "is_active", "sort_order"))))
        await self.session.commit()
        await self.session.refresh(value)
        return LookupOut.model_validate(value)

    async def reorder(self, kind: str, ids: list[int], actor) -> list[LookupOut]:
        values = {v.id: v for v in await self.repo.for_kind(kind)}
        if set(ids) != set(values) or len(ids) != len(values):
            raise ValidationFailedError("Send every value of this list exactly once")
        for position, value_id in enumerate(ids):
            values[value_id].sort_order = position
        await self.audit.record("lookup.reorder", actor=actor, entity_type="lookup", changes={"kind": kind, "order": ids})
        await self.session.commit()
        return await self.values(kind)

    # ---- seed -----------------------------------------------------------
    async def seed(self) -> str:
        """Insert starter values that don't exist yet (by key). Never changes or re-adds edited values."""
        added = 0
        for kind in KINDS.values():
            existing = {v.key for v in await self.repo.for_kind(kind.key)}
            if existing:
                # System types on contacts must stay present and active even after edits.
                if kind.key == "contact_type":
                    for key in ("user", "customer", "subscriber"):
                        row = next((v for v in await self.repo.for_kind(kind.key) if v.key == key), None)
                        if row is None:
                            self.session.add(LookupValue(kind=kind.key, key=key, label=key.title(),
                                                       sort_order=0, created_by=None, updated_by=None))
                            added += 1
                        elif not row.is_active:
                            row.is_active = True
                continue  # the admin owns this list now
            for position, label in enumerate(kind.seed):
                self.session.add(LookupValue(kind=kind.key, key=slugify(label), label=label, sort_order=position))
                added += 1
        await self.session.flush()
        return f"{added} starter values added" if added else "type lists already set up"
