"""Admin-defined extra fields, and the validator every module runs before saving `custom_fields`:

    record.custom_fields = await CustomFieldService(session).validate("customer", data.custom_fields,
                                                                      existing=record.custom_fields)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import get_entity_type
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit.service import AuditService, diff
from app.shared.snapshot import snapshot
from app.shared.text import slugify

from .models import CustomFieldDef
from .repository import FieldDefRepository
from .schemas import FieldDefCreate, FieldDefOut, FieldDefUpdate, FieldTypeOut
from .types import CHOICE_TYPES, FIELD_TYPES
from .validation import check_values



class CustomFieldService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FieldDefRepository(session)
        self.audit = AuditService(session)

    @staticmethod
    def field_types() -> list[FieldTypeOut]:
        return [FieldTypeOut(key=k, label=label) for k, (label, _) in FIELD_TYPES.items()]

    async def list(self, entity_type: str, *, active_only: bool = False) -> list[FieldDefOut]:
        get_entity_type(entity_type)
        return [FieldDefOut.model_validate(f) for f in await self.repo.for_entity(entity_type, active_only=active_only)]

    async def validate(self, entity_type: str, incoming: dict[str, Any] | None,
                       existing: dict[str, Any] | None = None) -> dict[str, Any]:
        return check_values(list(await self.repo.for_entity(entity_type)), incoming, existing)

    async def create(self, entity_type: str, data: FieldDefCreate, actor) -> FieldDefOut:
        get_entity_type(entity_type)
        if data.field_type in CHOICE_TYPES and not data.options:
            raise ValidationFailedError("Add at least one option")
        key = data.key or slugify(data.label)
        if not key[0].isalpha():
            key = f"f_{key}"
        if await self.repo.by_key(entity_type, key):
            raise ConflictError(f"A field with key '{key}' already exists")
        field = await self.repo.add(CustomFieldDef(
            entity_type=entity_type, key=key, label=data.label.strip(), field_type=data.field_type,
            options=data.options if data.field_type in CHOICE_TYPES else None, required=data.required,
            help_text=data.help_text, sort_order=await self.repo.next_sort(entity_type),
            created_by=actor.id, updated_by=actor.id,
        ))
        await self.audit.record("custom_field.create", actor=actor, entity_type="custom_field", entity_id=field.id,
                                changes={"record_type": entity_type, "key": key, "type": data.field_type})
        await self.session.commit()
        await self.session.refresh(field)
        return FieldDefOut.model_validate(field)

    async def _get(self, entity_type: str, field_id: int) -> CustomFieldDef:
        field = await self.repo.get(field_id)
        if field is None or field.entity_type != entity_type:
            raise NotFoundError("Field not found")
        return field

    async def update(self, entity_type: str, field_id: int, data: FieldDefUpdate, actor) -> FieldDefOut:
        field = await self._get(entity_type, field_id)
        before = snapshot(field, ("label", "options", "required", "help_text", "is_active", "sort_order"))
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None or k == "help_text"}
        if "options" in changes:
            if field.field_type not in CHOICE_TYPES:
                changes.pop("options")
            elif not changes["options"]:
                raise ValidationFailedError("Add at least one option")
        self.repo.apply(field, changes)
        field.updated_by = actor.id
        await self.audit.record("custom_field.update", actor=actor, entity_type="custom_field", entity_id=field.id,
                                changes=diff(before, snapshot(field, ("label", "options", "required", "help_text", "is_active", "sort_order"))))
        await self.session.commit()
        await self.session.refresh(field)
        return FieldDefOut.model_validate(field)

    async def reorder(self, entity_type: str, ids: list[int], actor) -> list[FieldDefOut]:
        fields = {f.id: f for f in await self.repo.for_entity(entity_type)}
        if set(ids) != set(fields) or len(ids) != len(fields):
            raise ValidationFailedError("Send every field of this record type exactly once")
        for position, field_id in enumerate(ids):
            fields[field_id].sort_order = position
        await self.audit.record("custom_field.reorder", actor=actor, entity_type="custom_field",
                                changes={"record_type": entity_type, "order": ids})
        await self.session.commit()
        return await self.list(entity_type)
