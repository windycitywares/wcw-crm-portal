"""Customers: the people Windy City Wares sells to (SPEC §3.2).

Rules:
- one active customer per email (case-insensitive); creating a duplicate returns 409 with the existing id;
- Sales can change customers they own; Support/Manager/Admin can change any (permissions map);
- types and sources must be active lookup values; custom fields are validated by the customfields module;
- every change is audited and lands on the customer's timeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, RecordsMerged, register_entity
from app.core.events import bus
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customfields.service import CustomFieldService
from app.modules.lookups.service import LookupService
from app.modules.tags.service import TagService

from .models import Customer
from .repository import CustomerRepository
from .schemas import CustomerCreate, CustomerOut, CustomerPage, CustomerUpdate, EmailCheck, TagRef

ENTITY = "customer"
TRACKED = ("first_name", "last_name", "company", "email", "phone", "customer_type", "source", "status",
           "owner_id", "marketing_consent")
LABELS = {"first_name": "first name", "last_name": "last name", "customer_type": "type", "owner_id": "owner",
          "marketing_consent": "marketing consent"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _exists(session, entity_id: int) -> bool:
    return await CustomerRepository(session).get(entity_id) is not None


async def _can_edit(session, user, entity_id: int) -> bool:
    if has_permission(user.role, Permission.CUSTOMERS_EDIT_ANY):
        return True
    customer = await CustomerRepository(session).get(entity_id)
    return customer is not None and customer.owner_id == user.id


async def _labels(session, ids: list[int]) -> dict[int, str]:
    rows = await CustomerRepository(session).list(CustomerRepository(session).query(include_deleted=True)
                                                  .where(Customer.id.in_(ids)))
    return {c.id: c.display_name for c in rows}


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Customer",
        view=(Permission.CUSTOMERS_VIEW,), edit=(Permission.CUSTOMERS_EDIT_OWN, Permission.CUSTOMERS_EDIT_ANY),
        exists=_exists, can_edit=_can_edit, labels=_labels,
    ))


def _snapshot(c: Customer) -> dict[str, Any]:
    return {k: getattr(c, k) for k in TRACKED}


class CustomerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CustomerRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.tags = TagService(session)
        self.lookups = LookupService(session)
        self.fields = CustomFieldService(session)

    # ---- reads ----------------------------------------------------------
    async def _out(self, customers: list[Customer]) -> list[CustomerOut]:
        tags = await self.tags.tags_for(ENTITY, [c.id for c in customers])
        return [CustomerOut.model_validate(c).model_copy(update={
            "tags": [TagRef(id=t.id, name=t.name, color=t.color) for t in tags.get(c.id, [])]
        }) for c in customers]

    async def _get(self, customer_id: int, *, include_deleted: bool = False) -> Customer:
        customer = await self.repo.get(customer_id, include_deleted=include_deleted)
        if customer is None:
            raise NotFoundError("Customer not found")
        return customer

    async def list(self, params: PageParams, *, tag_id: int | None = None, **filters: Any) -> CustomerPage:
        ids = await self.tags.entity_ids_with_tag(ENTITY, tag_id) if tag_id else None
        rows, total = await self.repo.paginate(self.repo.search(ids=ids, **filters), params)
        return CustomerPage(items=await self._out(list(rows)), total=total, page=params.page, page_size=params.page_size)

    async def get(self, customer_id: int, *, include_deleted: bool = False) -> CustomerOut:
        return (await self._out([await self._get(customer_id, include_deleted=include_deleted)]))[0]

    async def check_email(self, email: str, exclude_id: int | None = None) -> EmailCheck:
        existing = await self.repo.by_email(email)
        if existing is None or existing.id == exclude_id:
            return EmailCheck(exists=False)
        return EmailCheck(exists=True, customer_id=existing.id, display_name=existing.display_name)

    # ---- writes ---------------------------------------------------------
    async def _validate(self, data: dict[str, Any], current: Customer | None) -> dict[str, Any]:
        if "email" in data and data["email"]:
            data["email"] = str(data["email"]).strip().lower()
            dup = await self.repo.by_email(data["email"])
            if dup and (current is None or dup.id != current.id):
                raise ConflictError(f"A customer with this email already exists (#{dup.id} {dup.display_name})")
        if "alt_emails" in data and data["alt_emails"] is not None:
            data["alt_emails"] = sorted({str(e).lower() for e in data["alt_emails"]})
        if "customer_type" in data:
            data["customer_type"] = await self.lookups.require(
                "customer_type", data["customer_type"], allow_inactive_key=current.customer_type if current else None)
        if "source" in data:
            data["source"] = await self.lookups.require(
                "lead_source", data["source"], allow_inactive_key=current.source if current else None)
        if "address" in data and data["address"] is not None:
            data["address"] = {k: v for k, v in data["address"].items() if v} or None
        if "custom_fields" in data:
            data["custom_fields"] = await self.fields.validate(ENTITY, data["custom_fields"] or {},
                                                               existing=current.custom_fields if current else None)
        return data

    def _consent(self, customer: Customer, consent: bool | None, how: str) -> None:
        if consent is None or consent == customer.marketing_consent:
            return
        customer.marketing_consent = consent
        if consent:
            customer.consent_at, customer.consent_source, customer.unsubscribed_at = _now(), how, None
        else:
            customer.unsubscribed_at = _now()

    async def create(self, data: CustomerCreate, actor) -> CustomerOut:
        values = data.model_dump(exclude_unset=True)
        if not any(values.get(k) for k in ("first_name", "last_name", "company", "email", "phone")):
            raise ValidationFailedError("Give at least a name, company, email or phone")
        consent = values.pop("marketing_consent", None)
        values = await self._validate(values, None)
        if "owner_id" not in values:
            values["owner_id"] = actor.id
        elif values["owner_id"] != actor.id and not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("You can only create customers you own")
        customer = Customer(**{k: v for k, v in values.items() if v is not None},
                            created_by=actor.id, updated_by=actor.id)
        self._consent(customer, consent, "staff")
        await self.repo.add(customer)
        await self.audit.record("customer.create", actor=actor, entity_type=ENTITY, entity_id=customer.id,
                                changes=diff({}, _snapshot(customer)))
        await self.timeline.record(ENTITY, customer.id, "customer.created", "Customer added", actor=actor)
        await self.session.commit()
        return await self.get(customer.id)

    async def update(self, customer_id: int, data: CustomerUpdate, actor) -> CustomerOut:
        customer = await self._get(customer_id)
        if not await _can_edit(self.session, actor, customer_id):
            raise PermissionDeniedError("You can only change customers you own")
        values = data.model_dump(exclude_unset=True)
        if "owner_id" in values and values["owner_id"] != customer.owner_id \
                and not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("Only managers can hand a customer to someone else")
        if values.get("status") is None:
            values.pop("status", None)
        before = _snapshot(customer)
        consent = values.pop("marketing_consent", None)
        values = await self._validate(values, customer)
        self.repo.apply(customer, values)
        self._consent(customer, consent, "staff")
        customer.updated_by = actor.id
        changes = diff(before, _snapshot(customer))
        if changes:
            await self.audit.record("customer.update", actor=actor, entity_type=ENTITY, entity_id=customer.id, changes=changes)
            what = ", ".join(LABELS.get(k, k.replace("_", " ")) for k in changes)
            await self.timeline.record(ENTITY, customer.id, "customer.updated", f"Changed {what}", actor=actor,
                                       data={"fields": list(changes)})
        await self.session.commit()
        return await self.get(customer.id)

    async def delete(self, customer_id: int, actor) -> None:
        customer = await self._get(customer_id)
        if not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("Only managers and support can delete customers")
        await self.repo.soft_delete(customer)
        await self.audit.record("customer.delete", actor=actor, entity_type=ENTITY, entity_id=customer.id,
                                changes={"name": customer.display_name})
        await self.timeline.record(ENTITY, customer.id, "customer.deleted", "Customer deleted", actor=actor)
        await self.session.commit()

    async def restore(self, customer_id: int, actor) -> CustomerOut:
        customer = await self._get(customer_id, include_deleted=True)
        if customer.deleted_at is None:
            return await self.get(customer_id)
        if not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("Only managers and support can restore customers")
        if customer.email and await self.repo.by_email(customer.email):
            raise ConflictError("Another active customer now uses this email — merge them instead")
        await self.repo.restore(customer)
        await self.audit.record("customer.restore", actor=actor, entity_type=ENTITY, entity_id=customer.id)
        await self.timeline.record(ENTITY, customer.id, "customer.restored", "Customer restored", actor=actor)
        await self.session.commit()
        return await self.get(customer.id)

    # ---- shop sync ------------------------------------------------------
    # Called by app.integrations.shop with no actor (shown as "System"). These methods flush but don't
    # commit: the caller commits once the whole shop event has been applied.

    async def _shop_source(self) -> str | None:
        try:
            return await self.lookups.require("lead_source", "shop")
        except (NotFoundError, ValidationFailedError):
            return None  # someone removed the "Shop" source; leave it blank

    async def find_by_email(self, email: str) -> int | None:
        customer = await self.repo.by_email(email)
        return customer.id if customer else None

    async def sync_from_shop(self, *, email: str | None, shop_user_id: int | None = None, full_name: str | None = None,
                             phone: str | None = None, address: dict[str, Any] | None = None) -> int:
        """Find the customer for a shop account / order email, or create one. Staff edits win: existing
        names, phone and address are only filled in when blank. Returns the customer id."""
        email = (email or "").strip().lower() or None
        if not email and shop_user_id is None:
            raise ValidationFailedError("A shop event needs an email or a shop account id")
        customer = await self.repo.by_shop_user(shop_user_id) if shop_user_id is not None else None
        if customer is not None and customer.deleted_at is not None:
            customer = None  # a deleted record keeps its link; match the live one by email instead
            shop_user_id = None
        if customer is None and email:
            customer = await self.repo.by_email(email)
        first, _, last = " ".join((full_name or "").split()).partition(" ")
        address = {k: v for k, v in (address or {}).items() if v} or None

        if customer is None:
            customer = Customer(first_name=first[:80], last_name=last[:80], email=email, phone=(phone or None),
                                address=address, source=await self._shop_source(), shop_user_id=shop_user_id)
            await self.repo.add(customer)
            await self.audit.record("customer.create", entity_type=ENTITY, entity_id=customer.id,
                                    changes=diff({}, _snapshot(customer)))
            await self.timeline.record(ENTITY, customer.id, "customer.created", "Customer added from the shop")
            return customer.id

        before = _snapshot(customer)
        alt = set(customer.alt_emails or [])
        if not customer.first_name and not customer.last_name and first:
            customer.first_name, customer.last_name = first[:80], last[:80]
        if not customer.phone and phone:
            customer.phone = phone[:40]
        if not customer.address and address:
            customer.address = address
        if shop_user_id is not None and customer.shop_user_id is None:
            customer.shop_user_id = shop_user_id
        if email and email != customer.email:
            other = await self.repo.by_email(email)
            if customer.email is None and other is None:
                customer.email = email
            elif other is None and customer.shop_user_id == shop_user_id and shop_user_id is not None:
                alt.add(customer.email or "")  # the shop account changed its email: follow it, keep the old one
                customer.email = email
            else:
                alt.add(email)
        alt.discard("")
        alt.discard(customer.email or "")
        if alt != set(customer.alt_emails or []):
            customer.alt_emails = sorted(alt)
        changes = diff(before, _snapshot(customer))
        await self.session.flush()
        if changes:
            await self.audit.record("customer.update", entity_type=ENTITY, entity_id=customer.id, changes=changes)
            what = ", ".join(LABELS.get(k, k.replace("_", " ")) for k in changes)
            await self.timeline.record(ENTITY, customer.id, "customer.updated", f"Shop updated {what}",
                                       data={"fields": list(changes)})
        return customer.id

    async def set_consent_from_shop(self, customer_id: int, consent: bool, how: str) -> None:
        customer = await self._get(customer_id)
        was = customer.marketing_consent
        if consent and not customer.marketing_consent:
            self._consent(customer, True, how)
            await self.timeline.record(ENTITY, customer.id, "customer.consent", f"Agreed to marketing email ({how})")
        elif not consent and customer.unsubscribed_at is None:
            customer.marketing_consent, customer.unsubscribed_at = False, _now()
            await self.timeline.record(ENTITY, customer.id, "customer.consent", f"Unsubscribed from marketing email ({how})")
        else:
            return
        await self.audit.record("customer.consent", entity_type=ENTITY, entity_id=customer.id,
                                changes={"marketing_consent": [was, consent], "via": how})
        await self.session.flush()

    async def set_order_stats(self, customer_id: int, *, count: int, total: Any, first: datetime | None,
                              last: datetime | None) -> None:
        """Order totals worked out by the shop integration (derived data: not audited)."""
        customer = await self._get(customer_id, include_deleted=True)
        customer.orders_count, customer.total_spent = count, total
        customer.first_order_at, customer.last_order_at = first, last
        await self.session.flush()

    # ---- merge ----------------------------------------------------------------------------
    async def merge(self, keep_id: int, other_id: int, actor) -> CustomerOut:
        """Merge duplicate `other_id` into `keep_id`. The kept record's values win; its blanks are filled from the
        duplicate. Emails, tags, notes, timeline and shop orders all move over; an unsubscribe on either record
        wins over consent. The duplicate is soft-deleted (it keeps its own copy of what it had)."""
        if keep_id == other_id:
            raise ValidationFailedError("Choose two different customers")
        if not has_permission(actor.role, Permission.CUSTOMERS_MERGE):
            raise PermissionDeniedError("Only managers can merge customers")
        keep, other = await self._get(keep_id), await self._get(other_id)
        before = _snapshot(keep)
        other_email, other_shop, other_name = other.email, other.shop_user_id, other.display_name

        other.shop_user_id = None  # unique across all rows: free it before the kept record takes it
        other.updated_by = actor.id
        await self.repo.soft_delete(other)
        await self.session.flush()

        if not keep.first_name and not keep.last_name:
            keep.first_name, keep.last_name = other.first_name, other.last_name
        for field in ("company", "phone", "address", "customer_type", "source", "owner_id"):
            if not getattr(keep, field) and getattr(other, field):
                setattr(keep, field, getattr(other, field))
        emails = {*(keep.alt_emails or []), *(other.alt_emails or [])}
        if other_email:
            if keep.email is None:
                keep.email = other_email
            else:
                emails.add(other_email)
        emails.discard(keep.email or "")
        keep.alt_emails = sorted(emails)
        if keep.shop_user_id is None and other_shop is not None:
            keep.shop_user_id = other_shop
        if other.unsubscribed_at or keep.unsubscribed_at:
            keep.marketing_consent = False
            keep.unsubscribed_at = max(d for d in (keep.unsubscribed_at, other.unsubscribed_at) if d)
        elif other.marketing_consent and not keep.marketing_consent:
            keep.marketing_consent, keep.consent_at, keep.consent_source = True, other.consent_at, other.consent_source
        keep.custom_fields = {**(other.custom_fields or {}), **(keep.custom_fields or {})}
        keep.updated_by = actor.id
        await self.session.flush()

        await bus.publish(RecordsMerged(entity_type=ENTITY, from_id=other.id, into_id=keep.id, actor_id=actor.id), self.session)
        changes = diff(before, _snapshot(keep))
        await self.audit.record("customer.merge", actor=actor, entity_type=ENTITY, entity_id=keep.id,
                                changes={"merged_customer": [other.id, other_name], **changes})
        await self.audit.record("customer.delete", actor=actor, entity_type=ENTITY, entity_id=other.id,
                                changes={"merged_into": keep.id})
        await self.timeline.record(ENTITY, keep.id, "customer.merged", f"Merged with duplicate #{other.id} {other_name}",
                                   actor=actor, data={"merged_id": other.id})
        await self.session.commit()
        return await self.get(keep.id)

    # ---- import (app.modules.customers.transfer) ------------------------------------------
    async def import_row(self, values: dict[str, Any], actor, *, update_existing: bool) -> tuple[str, int]:
        """Create a customer from an import row, or (when asked) fill in an existing one with the same email.
        Returns ("created" | "updated" | "skipped", customer id). Flushes, doesn't commit."""
        existing = await self.repo.by_email(values["email"]) if values.get("email") else None
        if existing is None:
            data = await self._validate(dict(values), None)
            data.setdefault("owner_id", actor.id)
            customer = Customer(**{k: v for k, v in data.items() if v is not None}, created_by=actor.id, updated_by=actor.id)
            await self.repo.add(customer)
            await self.audit.record("customer.create", actor=actor, entity_type=ENTITY, entity_id=customer.id,
                                    changes=diff({}, _snapshot(customer)))
            await self.timeline.record(ENTITY, customer.id, "customer.created", "Customer imported", actor=actor)
            return "created", customer.id
        if not update_existing:
            return "skipped", existing.id
        data = {k: v for k, v in values.items() if k != "email"}
        if "alt_emails" in data:
            data["alt_emails"] = [e for e in {*(existing.alt_emails or []), *data["alt_emails"]} if e != existing.email]
        if "address" in data:
            data["address"] = {**(existing.address or {}), **data["address"]}
        before = _snapshot(existing)
        data = await self._validate(data, existing)
        self.repo.apply(existing, data)
        existing.updated_by = actor.id
        await self.session.flush()
        changes = diff(before, _snapshot(existing))
        if changes:
            await self.audit.record("customer.update", actor=actor, entity_type=ENTITY, entity_id=existing.id, changes=changes)
            what = ", ".join(LABELS.get(k, k.replace("_", " ")) for k in changes)
            await self.timeline.record(ENTITY, existing.id, "customer.updated", f"Import changed {what}", actor=actor,
                                       data={"fields": list(changes)})
        return "updated", existing.id
