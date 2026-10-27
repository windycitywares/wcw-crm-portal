"""Subscribers: the newsletter list, a view of the contacts typed "subscriber".

Not a second list: a subscriber is a contact, so someone who is also a customer or a vendor is still one row. This
file is what the Subscribers page needs on top of the directory — status tabs with counts, the pause / unsubscribe /
remove actions, adding by hand, and the CSV. Every change is audited.

Status: *unsubscribed* wins over *paused*; a person who has never signed up has none. Pausing keeps someone on the
list but out of campaigns until resumed; unsubscribing keeps the row (so nobody is re-added by mistake); removing
takes off the "subscriber" type and clears the dates, and leaves the contact itself alone.
"""

from __future__ import annotations

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.pagination import PageDep, PageParams
from app.core.permissions import Permission
from app.modules.audit.service import AuditService
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.shared.time import utcnow

from .models import Contact
from .repository import ContactRepository
from .schemas import ContactOut
from .service import ENTITY, TYPE_SUBSCRIBER, ContactService, _without_type

Status = Literal["subscribed", "paused", "unsubscribed"]
EXPORT_LIMIT = 50_000


class SubscriberAdd(BaseModel):
    email: EmailStr
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=10)


class SubscriberOut(ContactOut):
    model_config = ConfigDict(from_attributes=True)


class SubscriberPage(BaseModel):
    items: list[SubscriberOut]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]  # subscribed, paused, unsubscribed, all (for the search and source, any status)
    sources: list[str]


def _cell(value: object) -> str:
    """One CSV cell; a leading = + - @ would be run as a formula by a spreadsheet, so it is made plain text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


class SubscriberService:
    def __init__(self, session):
        self.session = session
        self.repo = ContactRepository(session)
        self.contacts = ContactService(session)
        self.audit = AuditService(session)

    async def list(self, params: PageParams, *, q=None, source=None, status=None, sort="-joined") -> SubscriberPage:
        rows, total = await self.repo.paginate(self.repo.subscribers(q=q, source=source, status=status, sort=sort), params)
        return SubscriberPage(
            items=[SubscriberOut.model_validate(c) for c in rows], total=total, page=params.page,
            page_size=params.page_size, counts=await self.repo.subscriber_counts(q=q, source=source),
            sources=await self.repo.subscriber_sources())

    async def _get(self, contact_id: int) -> Contact:
        contact = await self.repo.get(contact_id)
        if contact is None or TYPE_SUBSCRIBER not in (contact.types or []):
            raise NotFoundError("Subscriber not found")
        return contact

    async def _done(self, contact: Contact, actor, action: str, before: str | None) -> SubscriberOut:
        contact.updated_by = actor.id
        await self.audit.record("contact.update", actor=actor, entity_type=ENTITY, entity_id=contact.id,
                                changes={"newsletter": [before, contact.subscription_status], "via": action})
        await self.session.commit()
        await self.session.refresh(contact)
        return SubscriberOut.model_validate(contact)

    async def add(self, data: SubscriberAdd, actor) -> SubscriberOut:
        email = str(data.email).strip().lower()
        existing = await self.repo.by_email(email)
        before = existing.subscription_status if existing else None
        contact = await self.contacts.sync_subscriber(email, subscribed=True, source="manual", language=data.language,
                                                      origin="manual", actor=actor)
        assert contact is not None
        if existing is None:
            contact.owner_id = actor.id
            contact.first_name = (data.first_name or "").strip()
            contact.last_name = (data.last_name or "").strip()
        elif before == "paused":
            contact.paused_at = None
        await self.session.commit()
        await self.session.refresh(contact)
        return SubscriberOut.model_validate(contact)

    async def pause(self, contact_id: int, actor) -> SubscriberOut:
        contact = await self._get(contact_id)
        if contact.subscription_status != "subscribed":
            raise ValidationFailedError("Only someone who is subscribed can be paused")
        contact.paused_at = utcnow()
        return await self._done(contact, actor, "pause", "subscribed")

    async def resume(self, contact_id: int, actor) -> SubscriberOut:
        contact = await self._get(contact_id)
        if contact.subscription_status != "paused":
            raise ValidationFailedError("This subscriber is not paused")
        contact.paused_at = None
        return await self._done(contact, actor, "resume", "paused")

    async def unsubscribe(self, contact_id: int, actor) -> SubscriberOut:
        contact = await self._get(contact_id)
        before = contact.subscription_status
        if before != "unsubscribed":
            contact.unsubscribed_at = utcnow()
            contact.paused_at = None
        return await self._done(contact, actor, "unsubscribe", before)

    async def resubscribe(self, contact_id: int, actor) -> SubscriberOut:
        contact = await self._get(contact_id)
        if contact.subscription_status != "unsubscribed":
            raise ValidationFailedError("This subscriber has not unsubscribed")
        contact.unsubscribed_at = None
        contact.paused_at = None
        contact.subscribed_at = utcnow()
        return await self._done(contact, actor, "resubscribe", "unsubscribed")

    async def remove(self, contact_id: int, actor) -> None:
        """Off the list: the contact stays, without the type or the newsletter dates."""
        contact = await self._get(contact_id)
        before = contact.subscription_status
        contact.types = _without_type(contact.types, TYPE_SUBSCRIBER) or ["other"]
        contact.subscribed_at = contact.unsubscribed_at = contact.paused_at = None
        contact.subscribe_source = None
        await self._done(contact, actor, "remove", before)

    async def export_csv(self, *, q=None, source=None, status=None) -> str:
        rows = await self.repo.list(self.repo.subscribers(q=q, source=source, status=status).limit(EXPORT_LIMIT))
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["email", "first_name", "last_name", "status", "source", "language", "joined", "unsubscribed"])
        for c in rows:
            writer.writerow([_cell(v) for v in (
                c.email, c.first_name, c.last_name, c.subscription_status, c.subscribe_source, c.language,
                c.subscribed_at.date().isoformat() if c.subscribed_at else "",
                c.unsubscribed_at.date().isoformat() if c.unsubscribed_at else "")])
        return out.getvalue()


router = APIRouter(prefix="/subscribers", tags=["subscribers"])  # mounted under /contacts
Editor = Annotated[object, Depends(require(Permission.CUSTOMERS_EDIT_OWN))]
SortKey = Literal["-joined", "joined", "email"]


@router.get("", response_model=SubscriberPage)
async def list_subscribers(
    session: SessionDep, page: PageDep, q: str | None = None, source: str | None = None,
    status_: Annotated[Status | None, Query(alias="status")] = None, sort: SortKey = "-joined",
) -> SubscriberPage:
    return await SubscriberService(session).list(page, q=q, source=source, status=status_, sort=sort)


@router.get("/export.csv")
async def export_subscribers(
    session: SessionDep, q: str | None = None, source: str | None = None,
    status_: Annotated[Status | None, Query(alias="status")] = None,
) -> Response:
    body = await SubscriberService(session).export_csv(q=q, source=source, status=status_)
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="subscribers.csv"', "X-Content-Type-Options": "nosniff"})


@router.post("", response_model=SubscriberOut, status_code=201)
async def add_subscriber(session: SessionDep, actor: CurrentUser, _: Editor, data: SubscriberAdd) -> SubscriberOut:
    return await SubscriberService(session).add(data, actor)


@router.post("/{contact_id}/pause", response_model=SubscriberOut)
async def pause(session: SessionDep, actor: CurrentUser, _: Editor, contact_id: int) -> SubscriberOut:
    return await SubscriberService(session).pause(contact_id, actor)


@router.post("/{contact_id}/resume", response_model=SubscriberOut)
async def resume(session: SessionDep, actor: CurrentUser, _: Editor, contact_id: int) -> SubscriberOut:
    return await SubscriberService(session).resume(contact_id, actor)


@router.post("/{contact_id}/unsubscribe", response_model=SubscriberOut)
async def unsubscribe(session: SessionDep, actor: CurrentUser, _: Editor, contact_id: int) -> SubscriberOut:
    return await SubscriberService(session).unsubscribe(contact_id, actor)


@router.post("/{contact_id}/resubscribe", response_model=SubscriberOut)
async def resubscribe(session: SessionDep, actor: CurrentUser, _: Editor, contact_id: int) -> SubscriberOut:
    return await SubscriberService(session).resubscribe(contact_id, actor)


@router.delete("/{contact_id}", status_code=204)
async def remove(session: SessionDep, actor: CurrentUser, _: Editor, contact_id: int) -> None:
    await SubscriberService(session).remove(contact_id, actor)
