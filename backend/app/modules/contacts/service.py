"""Contacts: the people directory (SPEC A3.2 widened).

Rules:
- one active contact per email (case-insensitive); a duplicate is a 409 that names the existing row;
- a contact needs at least one type, and every type must be an active value in the `contact_type` list;
- staff users and customers are mirrored here: creating or changing either upserts the linked contact
  (`sync_user` / `sync_customer`), so the directory stays complete without anyone maintaining it twice;
- a person who is both staff and a customer is one row with both types and both links;
- every change is audited.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.modules.audit.service import AuditService, diff
from app.modules.lookups.service import LookupService
from app.shared.snapshot import snapshot

from .models import Contact
from .repository import ContactRepository
from .schemas import ContactCreate, ContactOut, ContactPage, ContactUpdate

ENTITY = "contact"
TRACKED = ("first_name", "last_name", "company", "title", "email", "phone", "types", "status", "owner_id")
LABELS = {"first_name": "first name", "last_name": "last name", "types": "types", "owner_id": "owner"}
TYPE_USER = "user"
TYPE_CUSTOMER = "customer"
DEFAULT_TYPE = "other"


def _with_type(types: list[str] | None, *wanted: str) -> list[str]:
    return sorted({*(types or []), *wanted})


def _without_type(types: list[str] | None, gone: str) -> list[str]:
    return [t for t in (types or []) if t != gone]


class ContactService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactRepository(session)
        self.audit = AuditService(session)
        self.lookups = LookupService(session)

    # ---- reads ----------------------------------------------------------
    async def list(self, params: PageParams, *, q: str | None = None, type: str | None = None,
                   status: str | None = None, owner_id: int | None = None, sort: str = "-updated") -> ContactPage:
        rows, total = await self.repo.paginate(
            self.repo.search(q=q, type=type, status=status, owner_id=owner_id, sort=sort), params)
        return ContactPage(items=[ContactOut.model_validate(c) for c in rows], total=total, page=params.page,
                           page_size=params.page_size)

    async def _get(self, contact_id: int, *, include_deleted: bool = False) -> Contact:
        contact = await self.repo.get(contact_id, include_deleted=include_deleted)
        if contact is None:
            raise NotFoundError("Contact not found")
        return contact

    async def get(self, contact_id: int, *, include_deleted: bool = False) -> ContactOut:
        return ContactOut.model_validate(await self._get(contact_id, include_deleted=include_deleted))

    # ---- validation -----------------------------------------------------
    # System types that drive the links to users/customers. They don't have to exist as lookup rows;
    # the services keep them present, but validating against a lookup would break if an admin removed them.
    # System types that drive the links to users/customers. They don't have to exist as lookup rows.
    SYSTEM_TYPES = {TYPE_USER, TYPE_CUSTOMER}

    async def _types(self, raw: list[str] | None, current: list[str] | None = None) -> list[str]:
        """Clean, validate and keep the structural types a link requires."""
        cleaned = sorted({t.strip() for t in (raw or []) if t and t.strip()})
        if not cleaned:
            cleaned = [DEFAULT_TYPE]
        for key in cleaned:
            if key in self.SYSTEM_TYPES:
                continue
            await self.lookups.require("contact_type", key, allow_inactive_key=None)
        linked = list(current or [])
        if TYPE_USER in linked:
            cleaned = _with_type(cleaned, TYPE_USER)
        if TYPE_CUSTOMER in linked:
            cleaned = _with_type(cleaned, TYPE_CUSTOMER)
        return cleaned

    async def _validate(self, data: dict[str, Any], current: Contact | None) -> dict[str, Any]:
        if "email" in data and data["email"]:
            data["email"] = str(data["email"]).strip().lower()
            dup = await self.repo.by_email(data["email"])
            if dup and (current is None or dup.id != current.id):
                raise ConflictError(f"A contact with this email already exists (#{dup.id} {dup.display_name})")
        if "alt_emails" in data and data["alt_emails"] is not None:
            data["alt_emails"] = sorted({str(e).lower() for e in data["alt_emails"]})
        if "address" in data and data["address"] is not None:
            data["address"] = {k: v for k, v in data["address"].items() if v} or None
        if "types" in data:
            data["types"] = await self._types(data["types"], current.types if current else None)
        return data

    # ---- writes ---------------------------------------------------------
    async def create(self, data: ContactCreate, actor) -> ContactOut:
        values = data.model_dump(exclude_unset=True)
        if not any(values.get(k) for k in ("first_name", "last_name", "company", "email", "phone")):
            raise ValidationFailedError("Give at least a name, company, email or phone")
        values.setdefault("types", [DEFAULT_TYPE])
        values = await self._validate(values, None)
        if "owner_id" not in values or values["owner_id"] is None:
            values["owner_id"] = actor.id
        elif values["owner_id"] != actor.id and not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("You can only create contacts you own")
        contact = Contact(**{k: v for k, v in values.items() if v is not None}, source="manual",
                          created_by=actor.id, updated_by=actor.id)
        await self.repo.add(contact)
        await self.audit.record("contact.create", actor=actor, entity_type=ENTITY, entity_id=contact.id,
                                changes=diff({}, snapshot(contact, TRACKED)))
        await self.session.commit()
        await self.session.refresh(contact)
        return ContactOut.model_validate(contact)

    async def update(self, contact_id: int, data: ContactUpdate, actor) -> ContactOut:
        contact = await self._get(contact_id)
        if contact.owner_id != actor.id and not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("You can only change contacts you own")
        values = data.model_dump(exclude_unset=True)
        if values.get("status") is None:
            values.pop("status", None)
        before = snapshot(contact, TRACKED)
        values = await self._validate(values, contact)
        self.repo.apply(contact, values)
        contact.updated_by = actor.id
        changes = diff(before, snapshot(contact, TRACKED))
        if changes:
            await self.audit.record("contact.update", actor=actor, entity_type=ENTITY, entity_id=contact.id,
                                    changes=changes)
        await self.session.commit()
        await self.session.refresh(contact)
        return ContactOut.model_validate(contact)

    async def delete(self, contact_id: int, actor) -> None:
        contact = await self._get(contact_id)
        if not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("Only managers and support can delete contacts")
        await self.repo.soft_delete(contact)
        await self.audit.record("contact.delete", actor=actor, entity_type=ENTITY, entity_id=contact.id,
                                changes={"name": contact.display_name})
        await self.session.commit()

    # ---- mirrors --------------------------------------------------------
    # Called by the users and customers services (and the shop sync). They flush but do not commit: the
    # caller commits once the whole change is applied, so a contact never outlives a failed write.

    async def _contact_for(self, *, user_id: int | None = None, customer_id: int | None = None,
                           email: str | None) -> Contact | None:
        if user_id is not None:
            found = await self.repo.by_user(user_id)
            if found:
                return found
        if customer_id is not None:
            found = await self.repo.by_customer(customer_id)
            if found:
                return found
        if email:
            return await self.repo.by_email(email)
        return None

    async def _set_email(self, contact: Contact, email: str | None) -> None:
        """Move the address only when no other live contact owns it (never steal one)."""
        if not email:
            return
        email = email.strip().lower()
        if contact.email == email:
            return
        other = await self.repo.by_email(email)
        if other is None or other.id == contact.id:
            contact.email = email

    async def sync_user(self, user, *, actor=None) -> Contact:
        email = (user.email or "").strip().lower()
        contact = await self._contact_for(user_id=user.id, email=email)
        first, _, last = (user.full_name or "").strip().partition(" ")
        if contact is None:
            contact = Contact(first_name=first, last_name=last, email=email or None, phone=user.phone,
                              title=user.title, types=_with_type([], TYPE_USER), source="user",
                              owner_id=user.id, user_id=user.id, created_by=getattr(actor, "id", None),
                              updated_by=getattr(actor, "id", None))
            await self.repo.add(contact)
            return contact
        contact.user_id = user.id
        contact.types = _with_type(contact.types, TYPE_USER)
        if not contact.first_name and not contact.last_name:
            contact.first_name, contact.last_name = first, last
        if not contact.phone and user.phone:
            contact.phone = user.phone
        if not contact.title and user.title:
            contact.title = user.title
        await self._set_email(contact, email)
        await self.session.flush()
        return contact

    async def sync_customer(self, customer, *, actor=None) -> Contact:
        email = (customer.email or "").strip().lower()
        contact = await self._contact_for(customer_id=customer.id, email=email)
        if contact is None:
            contact = Contact(first_name=customer.first_name, last_name=customer.last_name,
                              company=customer.company, email=email or None, phone=customer.phone,
                              address=customer.address, types=_with_type([], TYPE_CUSTOMER), source="customer",
                              owner_id=customer.owner_id, customer_id=customer.id, created_by=getattr(actor, "id", None),
                              updated_by=getattr(actor, "id", None))
            await self.repo.add(contact)
            return contact
        contact.customer_id = customer.id
        contact.types = _with_type(contact.types, TYPE_CUSTOMER)
        if not contact.first_name and not contact.last_name:
            contact.first_name, contact.last_name = customer.first_name, customer.last_name
        if not contact.company and customer.company:
            contact.company = customer.company
        if not contact.phone and customer.phone:
            contact.phone = customer.phone
        if not contact.address and customer.address:
            contact.address = customer.address
        contact.owner_id = contact.owner_id or customer.owner_id
        await self._set_email(contact, email)
        await self.session.flush()
        return contact

    async def forget_customer(self, customer_id: int) -> None:
        """A deleted customer is no longer a customer, but the person (and the link) stays."""
        contact = await self.repo.by_customer(customer_id)
        if contact is not None:
            contact.types = _without_type(contact.types, TYPE_CUSTOMER)
            await self.session.flush()
