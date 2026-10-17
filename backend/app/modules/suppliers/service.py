from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, register_entity
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customfields.service import CustomFieldService
from app.modules.lookups.service import LookupService

from .models import Supplier, SupplierContact
from .repository import SupplierContactRepository, SupplierRepository
from .schemas import (
    SupplierContactIn, SupplierContactOut, SupplierContactUpdate, SupplierIn, SupplierOut, SupplierPage,
    SupplierUpdate,
)

ENTITY = "supplier"
SUPPLIER_FIELDS = (
    "name", "supplier_type", "status", "address", "website", "payment_terms", "lead_time_days", "currency",
    "rating", "custom_fields",
)


async def _exists(session, supplier_id: int) -> bool:
    return await SupplierRepository(session).get(supplier_id) is not None


async def _labels(session, ids: list[int]) -> dict[int, str]:
    repo = SupplierRepository(session)
    rows = await repo.list(repo.query(include_deleted=True).where(Supplier.id.in_(ids)))
    return {supplier.id: supplier.name for supplier in rows}


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Supplier", view=(Permission.SUPPLIERS_VIEW,), edit=(Permission.SUPPLIERS_EDIT,),
        exists=_exists, labels=_labels,
    ))


def _snapshot(supplier: Supplier) -> dict[str, Any]:
    return {field: getattr(supplier, field) for field in SUPPLIER_FIELDS}


def _contact_snapshot(contact: SupplierContact) -> dict[str, Any]:
    return {field: getattr(contact, field) for field in ("name", "title", "email", "phone", "is_primary")}


class SupplierService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SupplierRepository(session)
        self.contact_repo = SupplierContactRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)
        self.fields = CustomFieldService(session)

    async def _get(self, supplier_id: int) -> Supplier:
        supplier = await self.repo.get(supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found")
        return supplier

    async def _out(self, suppliers: list[Supplier]) -> list[SupplierOut]:
        contacts = await self.repo.contacts_for([supplier.id for supplier in suppliers])
        return [SupplierOut.model_validate(supplier).model_copy(update={
            "contacts": [SupplierContactOut.model_validate(contact) for contact in contacts.get(supplier.id, [])],
        }) for supplier in suppliers]

    async def list(self, params: PageParams, *, q: str | None = None, supplier_type: str | None = None,
                   status: str | None = None) -> SupplierPage:
        rows, total = await self.repo.paginate(
            self.repo.search(q=q, supplier_type=supplier_type, status=status), params,
        )
        return SupplierPage(items=await self._out(list(rows)), total=total, page=params.page,
                            page_size=params.page_size)

    async def get(self, supplier_id: int) -> SupplierOut:
        return (await self._out([await self._get(supplier_id)]))[0]

    async def _validate(self, values: dict[str, Any], current: Supplier | None) -> dict[str, Any]:
        if "supplier_type" in values and values["supplier_type"] is not None:
            values["supplier_type"] = await self.lookups.require(
                "supplier_type", values["supplier_type"],
                allow_inactive_key=current.supplier_type if current else None,
            )
        if "address" in values and values["address"] is not None:
            values["address"] = {key: value for key, value in values["address"].items() if value} or None
        if "website" in values and values["website"] is not None:
            values["website"] = str(values["website"])
        if "currency" in values and values["currency"] is not None:
            values["currency"] = values["currency"].upper()
        if "custom_fields" in values:
            values["custom_fields"] = await self.fields.validate(
                ENTITY, values["custom_fields"] or {}, existing=current.custom_fields if current else None,
            )
        return values

    async def _clear_primary(self, supplier_id: int, actor, *, keep_id: int | None = None) -> None:
        for contact in (await self.repo.contacts_for([supplier_id])).get(supplier_id, []):
            if contact.is_primary and contact.id != keep_id:
                before = _contact_snapshot(contact)
                contact.is_primary = False
                contact.updated_by = actor.id
                changes = diff(before, _contact_snapshot(contact))
                await self.audit.record("supplier.contact_update", actor=actor, entity_type=ENTITY,
                                        entity_id=supplier_id, changes={"contact_id": contact.id, **changes})
                await self.timeline.record(ENTITY, supplier_id, "supplier.contact_updated",
                                           f"Primary contact changed: {contact.name}", actor=actor,
                                           data={"contact_id": contact.id, "fields": list(changes)})

    async def _add_contact(self, supplier: Supplier, data: SupplierContactIn, actor) -> SupplierContact:
        values = data.model_dump(exclude_unset=True, mode="json")
        if values.get("is_primary"):
            await self._clear_primary(supplier.id, actor)
        contact = SupplierContact(**values, supplier_id=supplier.id, created_by=actor.id, updated_by=actor.id)
        await self.contact_repo.add(contact)
        return contact

    async def create(self, data: SupplierIn, actor) -> SupplierOut:
        if sum(contact.is_primary for contact in data.contacts) > 1:
            raise ValidationFailedError("A supplier can have only one primary contact")
        values = data.model_dump(exclude={"contacts"}, exclude_unset=True)
        values = await self._validate(values, None)
        supplier = Supplier(**values, created_by=actor.id, updated_by=actor.id)
        await self.repo.add(supplier)
        for contact in data.contacts:
            await self._add_contact(supplier, contact, actor)
        await self.audit.record("supplier.create", actor=actor, entity_type=ENTITY, entity_id=supplier.id,
                                changes=diff({}, _snapshot(supplier)))
        await self.timeline.record(ENTITY, supplier.id, "supplier.created", "Supplier added", actor=actor)
        await self.session.commit()
        return await self.get(supplier.id)

    async def update(self, supplier_id: int, data: SupplierUpdate, actor) -> SupplierOut:
        supplier = await self._get(supplier_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("name") is None:
            values.pop("name", None)
        if values.get("supplier_type") is None:
            values.pop("supplier_type", None)
        if values.get("status") is None:
            values.pop("status", None)
        if values.get("currency") is None:
            values.pop("currency", None)
        before = _snapshot(supplier)
        values = await self._validate(values, supplier)
        self.repo.apply(supplier, values)
        supplier.updated_by = actor.id
        changes = diff(before, _snapshot(supplier))
        if changes:
            await self.audit.record("supplier.update", actor=actor, entity_type=ENTITY, entity_id=supplier.id,
                                    changes=changes)
            await self.timeline.record(ENTITY, supplier.id, "supplier.updated", "Supplier details changed",
                                       actor=actor, data={"fields": list(changes)})
        await self.session.commit()
        return await self.get(supplier.id)

    async def delete(self, supplier_id: int, actor) -> None:
        supplier = await self._get(supplier_id)
        await self.repo.soft_delete(supplier)
        await self.audit.record("supplier.delete", actor=actor, entity_type=ENTITY, entity_id=supplier.id,
                                changes={"name": supplier.name})
        await self.timeline.record(ENTITY, supplier.id, "supplier.deleted", "Supplier archived", actor=actor)
        await self.session.commit()

    async def add_contact(self, supplier_id: int, data: SupplierContactIn, actor) -> SupplierContactOut:
        supplier = await self._get(supplier_id)
        contact = await self._add_contact(supplier, data, actor)
        supplier.updated_by = actor.id
        await self.audit.record("supplier.contact_add", actor=actor, entity_type=ENTITY, entity_id=supplier.id,
                                changes={"contact": contact.name})
        await self.timeline.record(ENTITY, supplier.id, "supplier.contact_added", f"Contact added: {contact.name}",
                                   actor=actor)
        await self.session.commit()
        return SupplierContactOut.model_validate(contact)

    async def update_contact(self, supplier_id: int, contact_id: int, data: SupplierContactUpdate,
                             actor) -> SupplierContactOut:
        supplier = await self._get(supplier_id)
        contact = await self.repo.contact(supplier_id, contact_id)
        if contact is None:
            raise NotFoundError("Supplier contact not found")
        values = data.model_dump(exclude_unset=True, mode="json")
        for field in ("name", "is_primary"):
            if values.get(field) is None:
                values.pop(field, None)
        before = _contact_snapshot(contact)
        if values.get("is_primary"):
            await self._clear_primary(supplier_id, actor, keep_id=contact.id)
        self.contact_repo.apply(contact, values)
        contact.updated_by = actor.id
        changes = diff(before, _contact_snapshot(contact))
        if changes:
            supplier.updated_by = actor.id
            await self.audit.record("supplier.contact_update", actor=actor, entity_type=ENTITY,
                                    entity_id=supplier.id, changes={"contact_id": contact.id, **changes})
            await self.timeline.record(ENTITY, supplier.id, "supplier.contact_updated",
                                       f"Contact updated: {contact.name}", actor=actor,
                                       data={"contact_id": contact.id, "fields": list(changes)})
        await self.session.commit()
        return SupplierContactOut.model_validate(contact)

    async def delete_contact(self, supplier_id: int, contact_id: int, actor) -> None:
        supplier = await self._get(supplier_id)
        contact = await self.repo.contact(supplier_id, contact_id)
        if contact is None:
            raise NotFoundError("Supplier contact not found")
        await self.contact_repo.soft_delete(contact)
        supplier.updated_by = actor.id
        await self.audit.record("supplier.contact_delete", actor=actor, entity_type=ENTITY, entity_id=supplier.id,
                                changes={"contact_id": contact.id, "name": contact.name})
        await self.timeline.record(ENTITY, supplier.id, "supplier.contact_deleted", f"Contact removed: {contact.name}",
                                   actor=actor)
        await self.session.commit()