"""Leads (SPEC §3.3): the funnel before a customer, and converting one into a customer + deal.

Rules:
- `sales:view` reads every lead; `sales:edit_own` adds leads and works the ones you own or created;
  `sales:edit_any` changes anyone's lead and hands one to someone else;
- a lead needs at least a name, company, email or phone; the email must be a real address;
- `source` must be an active `lead_source` lookup and `custom_fields` follow the admin's definition;
- `converted` is never set by hand — POST /leads/{id}/convert creates the customer (or reuses the one with
  the same email, or the `customer_id` given) and, unless asked otherwise, the first deal. It is one
  transaction: a failure leaves neither a half-made customer nor a converted lead;
- the lead is a registered record type, so notes, tags, tasks and its timeline work on it like on a
  customer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, check_entity_access, entity_labels, register_entity
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService
from app.modules.customfields.service import CustomFieldService
from app.modules.lookups.service import LookupService
from app.modules.sales.schemas import DealCreate
from app.modules.sales.service import SalesService
from app.modules.users.service import UserService
from app.shared.time import utcnow

from .models import Lead
from .repository import LeadRepository
from .schemas import LeadConvert, LeadCreate, LeadOut, LeadPage, LeadSummary, LeadUpdate

ENTITY = "lead"
TRACKED = ("first_name", "last_name", "company", "email", "phone", "source", "status", "notes", "owner_id")
LABELS = {"first_name": "first name", "last_name": "last name", "owner_id": "owner"}


def _snapshot(lead: Lead) -> dict[str, Any]:
    return {k: getattr(lead, k) for k in TRACKED}


async def _exists(session, entity_id: int) -> bool:
    return await LeadRepository(session).get(entity_id) is not None


def _may_change(user, lead: Lead) -> bool:
    return has_permission(user.role, Permission.SALES_EDIT_ANY) or (
        has_permission(user.role, Permission.SALES_EDIT_OWN) and user.id in (lead.owner_id, lead.created_by))


async def _can_edit(session, user, entity_id: int) -> bool:
    lead = await LeadRepository(session).get(entity_id)
    return lead is not None and _may_change(user, lead)


async def _labels(session, ids: list[int]) -> dict[int, str]:
    repo = LeadRepository(session)
    return {lead.id: lead.display_name for lead in await repo.list(repo.query(include_deleted=True)
                                                                   .where(Lead.id.in_(ids)))}


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Lead", view=(Permission.SALES_VIEW,),
        edit=(Permission.SALES_EDIT_OWN, Permission.SALES_EDIT_ANY), exists=_exists, can_edit=_can_edit,
        labels=_labels,
    ))


class LeadService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LeadRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)
        self.fields = CustomFieldService(session)
        self.customers = CustomerService(session)
        self.deals = SalesService(session)

    # ---- helpers ------------------------------------------------------------------------------
    async def _out(self, leads: list[Lead]) -> list[LeadOut]:
        if not leads:
            return []
        customer_ids = [x.converted_customer_id for x in leads if x.converted_customer_id]
        deal_ids = [x.converted_deal_id for x in leads if x.converted_deal_id]
        customers = await entity_labels(self.session, "customer", customer_ids) if customer_ids else {}
        deal_titles = await entity_labels(self.session, "deal", deal_ids) if deal_ids else {}
        people = {u.id: u.full_name for u in await UserService(self.session).directory()}
        out = []
        for lead in leads:
            item = LeadOut.model_validate(lead)
            item.owner_name = people.get(lead.owner_id) if lead.owner_id else None
            item.converted_customer_name = customers.get(lead.converted_customer_id) if lead.converted_customer_id else None
            item.converted_deal_title = deal_titles.get(lead.converted_deal_id) if lead.converted_deal_id else None
            out.append(item)
        return out

    async def _get(self, lead_id: int) -> Lead:
        lead = await self.repo.get(lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        return lead

    def _check_owner(self, user, owner_id: int | None, current: int | None = None) -> None:
        if owner_id is not None and owner_id != user.id and owner_id != current \
                and not has_permission(user.role, Permission.SALES_EDIT_ANY):
            raise PermissionDeniedError("Only managers can give leads to someone else")

    async def _validate(self, values: dict[str, Any], current: Lead | None) -> dict[str, Any]:
        if "email" in values and values["email"]:
            values["email"] = str(values["email"]).strip().lower()
        if "source" in values:
            values["source"] = await self.lookups.require(
                "lead_source", values["source"], allow_inactive_key=current.source if current else None)
        if "custom_fields" in values:
            values["custom_fields"] = await self.fields.validate(
                ENTITY, values["custom_fields"] or {}, existing=current.custom_fields if current else None)
        return values

    async def _active_source(self, key: str | None) -> str | None:
        """A lead's source, but only while it is still on the list: a deactivated option must not block a
        conversion, and the customer/deal validators only accept active keys."""
        if not key:
            return None
        active = {v.key for v in await self.lookups.values("lead_source", include_inactive=False)}
        return key if key in active else None

    # ---- reads --------------------------------------------------------------------------------
    async def list(self, user, params: PageParams, *, view: str = "all", status: str | None = None,
                   source: str | None = None, owner_id: int | None = None, q: str | None = None) -> LeadPage:
        filters: dict[str, Any] = {"status": status, "source": source, "q": q}
        if view == "mine":
            filters["owner_id"] = user.id
        elif view == "unassigned":
            filters["unassigned"] = True
        elif owner_id is not None:
            filters["owner_id"] = owner_id
        rows, total = await self.repo.paginate(self.repo.search(**filters), params)
        return LeadPage(items=await self._out(list(rows)), total=total, page=params.page,
                        page_size=params.page_size)

    async def get(self, lead_id: int) -> LeadOut:
        return (await self._out([await self._get(lead_id)]))[0]

    async def summary(self) -> LeadSummary:
        async def count(status: str) -> int:
            return await self.repo.count_where(Lead.status == status)

        return LeadSummary(
            new=await count("new"), contacted=await count("contacted"), qualified=await count("qualified"),
            unqualified=await count("unqualified"), converted=await count("converted"),
            total=await self.repo.count_where(), unassigned=await self.repo.count_where(Lead.owner_id.is_(None)),
        )

    # ---- writes -------------------------------------------------------------------------------
    async def create(self, data: LeadCreate, actor) -> LeadOut:
        values = data.model_dump(exclude_unset=True)
        if not any(values.get(k) for k in ("first_name", "last_name", "company", "email", "phone")):
            raise ValidationFailedError("Give at least a name, company, email or phone")
        owner_id = values.pop("owner_id", None) or actor.id
        self._check_owner(actor, owner_id)
        values = await self._validate(values, None)
        lead = Lead(**{k: v for k, v in values.items() if v is not None}, owner_id=owner_id,
                    created_by=actor.id, updated_by=actor.id)
        await self.repo.add(lead)
        await self.audit.record("lead.create", actor=actor, entity_type=ENTITY, entity_id=lead.id,
                                changes=diff({}, _snapshot(lead)))
        await self.timeline.record(ENTITY, lead.id, "lead.created", f"Lead added: {lead.display_name}", actor=actor)
        await self.session.commit()
        return await self.get(lead.id)

    async def update(self, lead_id: int, data: LeadUpdate, actor) -> LeadOut:
        lead = await self._get(lead_id)
        if not _may_change(actor, lead):
            raise PermissionDeniedError("You can only change leads you own")
        values = data.model_dump(exclude_unset=True)
        # a form sends null for a field it isn't changing, and `status` is never empty — so leave it alone
        if values.get("status") is None:
            values.pop("status", None)
        if lead.is_converted:
            # once it is a customer, the customer is the live record; the lead keeps its own details
            if "status" in values:
                raise ValidationFailedError("This lead has been converted — change the customer and deal instead")
        if "owner_id" in values:
            if values["owner_id"] is None:
                values["owner_id"] = lead.owner_id
            self._check_owner(actor, values["owner_id"], lead.owner_id)
        values = await self._validate(values, lead)
        before = _snapshot(lead)
        self.repo.apply(lead, values)
        lead.updated_by = actor.id
        changes = diff(before, _snapshot(lead))
        if changes:
            await self.audit.record("lead.update", actor=actor, entity_type=ENTITY, entity_id=lead.id, changes=changes)
            what = ", ".join(LABELS.get(k, k.replace("_", " ")) for k in changes)
            await self.timeline.record(ENTITY, lead.id, "lead.updated", f"Changed {what}", actor=actor,
                                       data={"fields": list(changes)})
        await self.session.commit()
        return await self.get(lead.id)

    async def delete(self, lead_id: int, actor) -> None:
        lead = await self._get(lead_id)
        if not _may_change(actor, lead):
            raise PermissionDeniedError("You can only delete leads you own")
        await self.repo.soft_delete(lead)
        await self.audit.record("lead.delete", actor=actor, entity_type=ENTITY, entity_id=lead.id,
                                changes={"name": lead.display_name})
        await self.timeline.record(ENTITY, lead.id, "lead.deleted", f"Lead deleted: {lead.display_name}", actor=actor)
        await self.session.commit()

    async def convert(self, lead_id: int, data: LeadConvert, actor) -> LeadOut:
        """Turn a lead into a customer and (unless asked otherwise) its first deal.

        The customer is the one whose email matches the lead, so converting a lead twice over — or a lead
        from someone already in the CRM — never makes a duplicate. One transaction covers the customer,
        the deal and the lead's own update.
        """
        lead = await self._get(lead_id)
        if not _may_change(actor, lead):
            raise PermissionDeniedError("You can only convert leads you own")
        if lead.is_converted:
            raise ValidationFailedError("This lead has already been converted")

        owner_id = lead.owner_id or actor.id
        source = await self._active_source(lead.source)
        customer_id = data.customer_id
        if customer_id is not None:
            await check_entity_access(self.session, actor, "customer", customer_id, write=False)
        elif lead.email:
            customer_id = await self.customers.find_by_email(lead.email)
        if customer_id is None:
            created = await self.customers.create(CustomerCreate(
                first_name=lead.first_name, last_name=lead.last_name, company=lead.company, email=lead.email,
                phone=lead.phone, source=source, owner_id=owner_id), actor, commit=False)
            customer_id = created.id

        deal_id = None
        if data.create_deal:
            deal = await self.deals.create(DealCreate(
                title=data.deal_title or lead.company or lead.display_name, customer_id=customer_id,
                stage_id=data.stage_id, owner_id=owner_id, value=data.value, currency=data.currency,
                expected_close_on=data.expected_close_on, source=source), actor, commit=False)
            deal_id = deal.id

        lead.status = "converted"
        lead.converted_at, lead.converted_customer_id, lead.converted_deal_id = utcnow(), customer_id, deal_id
        lead.updated_by = actor.id
        await self.session.flush()
        what = f"Lead converted to customer #{customer_id}" + (f" and deal #{deal_id}" if deal_id else "")
        await self.audit.record("lead.convert", actor=actor, entity_type=ENTITY, entity_id=lead.id,
                                changes={"customer_id": customer_id, "deal_id": deal_id})
        await self.timeline.record(ENTITY, lead.id, "lead.converted", what, actor=actor,
                                   data={"customer_id": customer_id, "deal_id": deal_id})
        await self.session.commit()
        return await self.get(lead.id)
