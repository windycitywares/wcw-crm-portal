"""Campaigns (SPEC §3.6): email templates and the suppression list — what a campaign is made of.

Rules:
- `campaigns:view` reads; `campaigns:edit` writes templates and the suppression list; `campaigns:send` is
  what it takes to send a test — sending email is the careful action, not editing words;
- a template is **checked when it is saved**: it is rendered with sample data, so a misspelled merge field
  or a broken `{% if %}` comes back as an error at the desk, not in a customer's inbox;
- a template with no text body gets one derived from its HTML (`render.plain_text`), so every email has a
  text part; editing the HTML re-derives it unless the author sends one along;
- `version` goes up on every save, and the audit log records who changed what (names, subject, preheader and
  how big the bodies are — not the whole HTML). What a customer actually received is kept by the send
  itself, in the outbox, rather than by a second copy of the template;
- every rendered message gets the compliance footer: the postal address from Admin → Settings → Email and
  the customer's signed unsubscribe link, whether the template included one or not;
- a test send goes through the outbox like every other email (see the `mail` module), so it is limited and
  retried the same way;
- the suppression list is soft-deleted: re-adding an address restores its row, keeping the history of why
  it was there. The campaign sender (next batch) asks `suppressed()` before every send; a customer's own
  `unsubscribed_at` is the other half of the same rule and is read at send time.
- an **audience** is a target list of customers: either a **static** list, whose members are put on by hand,
  or a **segment** — the same row with `kind="segment"` and `rules`, which is a query, not a stored list, so
  it is always current and nothing has to be synced (see `segments.py`). Either way a list row carries two
  numbers: `members` — the live customers in it (for a segment: the ones matching now) — and `reachable` —
  the ones a campaign could actually email: an address, consent, no unsubscribe, and not on the suppression
  list (see `consent.py`). Membership changes are audited one row per customer, so "who put them on this
  list?" always has an answer. Merging two customers moves their memberships to the one that stayed
  (see `merge.py`).
- a **campaign** is a template plus an audience plus a time (SPEC §3.6: draft → scheduled → sending → paused
  → sent), and it never sends anything itself: when it
  starts, its audience is copied into `campaign_recipients` (a segment is evaluated then, once) and the
  dispatcher job queues one personalized message per recipient into the email outbox, only as many at a time
  as the SMTP limits allow. The outbox does the sending, the pacing and the retrying, and the dispatcher
  copies back what happened: sent, or failed with the reason. Anyone without consent, unsubscribed or
  suppressed is skipped, with the reason kept on their row — compliance is checked at send time, not when
  the audience was written.
- the **unsubscribe link** in a campaign email works without a login: the token is the proof (see
  `tokens.py`). It answers a GET without changing anything (so a mail scanner cannot unsubscribe anyone),
  and a POST turns consent off, suppresses the address and writes down which campaign it came from.
- **tracking** (SPEC §3.6) works the same way, from the other end: every link in a queued message is wrapped
  so following it comes back to us (and then sends the customer on to where the link pointed — the destination
  is inside the signed token, so a link can only ever redirect where that email pointed), and a one-pixel
  image at the end of the message says it was opened. Both are written to `campaign_events` **once per
  recipient**, so the report counts people rather than requests; an open or a click lands on the customer's
  timeline the first time only. A preview and a test send are not tracked: they are the words, not a send.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.entities import check_entity_access
from app.core.exceptions import ConflictError, NotFoundError, TooManyRequestsError, ValidationFailedError
from app.core.pagination import PageParams
from app.integrations.email import EmailSender, Mail, get_email_sender
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.service import CustomerService
from app.modules.lookups.service import LookupService
from app.modules.mail.service import MailService
from app.modules.settings.groups import EmailSettings
from app.modules.settings.service import SettingsService
from app.modules.users.service import UserService

from . import render, segments
from .models import (
    CLICK, DRAFT, OPEN, PAUSED, QUEUED, RECIPIENT_FAILED, RECIPIENT_SENT, RECIPIENT_STATUSES, SCHEDULED,
    SENDING, SENT, SKIPPED, UNSUBSCRIBED, Campaign, EmailTemplate, Suppression, TargetList, TargetListMember,
)
from .repository import (
    CampaignEventRepository, CampaignRecipientRepository, CampaignRepository, EmailTemplateRepository,
    SuppressionRepository, TargetListMemberRepository, TargetListRepository,
)
from .schemas import (
    CampaignIn, CampaignOut, CampaignPage, CampaignReport, CampaignSchedule, CampaignStats, CampaignSummary,
    LinkClicks, MemberOut, MemberPage, MembersAdded, MembersIn, RecipientCounts, RecipientOut, RecipientPage,
    RenderedEmail, SegmentField, SuppressionIn, SuppressionOut, SuppressionPage, TargetListIn, TargetListOut,
    TargetListPage, TargetListUpdate, TemplateIn, TemplateOut, TemplatePage, TemplateSummary, TemplateUpdate,
    TestIn, TestSent, UnsubscribeIn, UnsubscribeOut,
)
from .tokens import (
    click_url, open_url, read_click_token, read_open_token, read_unsubscribe_token, unsubscribe_url,
)

ENTITY = "email_template"
SUPPRESSION = "suppression"
LIST = "target_list"
CAMPAIGN = "campaign"
TRACKED = ("name", "subject", "preheader", "version")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot(template: EmailTemplate) -> dict[str, Any]:
    """What the audit log keeps: the words that matter and the size of the two bodies."""
    snap: dict[str, Any] = {key: getattr(template, key) for key in TRACKED}
    snap["html"] = f"{len(template.html)} chars"
    snap["text"] = f"{len(template.text)} chars"
    return snap


def _list_snapshot(target: TargetList) -> dict[str, Any]:
    return {"name": target.name, "description": target.description, "rules": target.rules}


def _campaign_snapshot(campaign: Campaign) -> dict[str, Any]:
    return {"name": campaign.name, "status": campaign.status, "template_id": campaign.template_id,
            "target_list_id": campaign.target_list_id, "scheduled_at": campaign.scheduled_at}


def _recipient_counts(counts: dict[str, int] | None) -> RecipientCounts:
    """The five statuses always add up to `total`, so a row nobody has touched reads all zeroes."""
    known = {status: int((counts or {}).get(status, 0)) for status in RECIPIENT_STATUSES}
    return RecipientCounts(total=sum(known.values()), **known)


class CampaignService:
    def __init__(self, session: AsyncSession, email_sender: EmailSender | None = None):
        self.session = session
        self.templates = EmailTemplateRepository(session)
        self.suppressions = SuppressionRepository(session)
        self.lists = TargetListRepository(session)
        self.members = TargetListMemberRepository(session)
        self.customers = CustomerRepository(session)  # the customer table, for segments and member lookups
        self.campaigns = CampaignRepository(session)
        self.recipients = CampaignRecipientRepository(session)
        self.events = CampaignEventRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.settings = SettingsService(session)
        self.lookups = LookupService(session)
        self.outbox = MailService(session)  # campaigns queue into the outbox; the mail job sends them
        self.mail = email_sender
        self._directory: dict[int, str] | None = None

    # ---- merge fields and rendering ------------------------------------------------------------
    async def _people(self) -> dict[int, str]:
        """Staff names by id, fetched once per service (a page of templates asks repeatedly)."""
        if self._directory is None:
            self._directory = {u.id: u.full_name for u in await UserService(self.session).directory()}
        return self._directory

    async def _type_label(self, key: str | None) -> str:
        if not key:
            return ""
        for value in await self.lookups.values("customer_type"):
            if value.key == key:
                return value.label
        return key

    async def _context(self, customer: Customer | None, campaign_id: int | None = None) -> dict[str, Any]:
        """The merge fields for one customer — or the sample ones for nobody in particular."""
        base = get_settings().site_url.rstrip("/")
        if customer is None:
            fields = dict(render.SAMPLE_CUSTOMER)
            unsubscribe = f"{base}/unsubscribe?token=sample"
        else:
            people = await self._people()
            fields = {
                "first_name": customer.first_name or "",
                "last_name": customer.last_name or "",
                "full_name": customer.full_name,
                "company": customer.company or "",
                "email": customer.email or "",
                "customer_type": await self._type_label(customer.customer_type),
                "owner_name": people.get(customer.owner_id) if customer.owner_id else "",
            }
            unsubscribe = unsubscribe_url(customer.id, base_url=base, campaign_id=campaign_id)
        prefs: EmailSettings = await self.settings.get_model("email")  # type: ignore[assignment]
        return {"customer": fields, "sender_name": prefs.from_name, "unsubscribe_url": unsubscribe}

    async def _render(self, *, subject: str, preheader: str | None, html: str, text: str,
                      customer: Customer | None, campaign_id: int | None = None,
                      recipient_id: int | None = None) -> RenderedEmail:
        """What one customer would get in their inbox: subject, preheader, HTML and text, footer included.

        `campaign_id` is only noted on the unsubscribe link, so the report can say which campaign someone
        left from. The footer, and with it the link, is added here — no template can leave it out.

        `recipient_id` is what makes a message a **tracked** one (SPEC §3.6): every web link in it is wrapped
        so a click comes back to us, and the one-pixel image an open is recorded by is added at the end. It is
        passed only when a real message is queued — a preview and a test send show the words as written.
        """
        prefs: EmailSettings = await self.settings.get_model("email")  # type: ignore[assignment]
        api = get_settings().api_url.rstrip("/")  # tracking links are fetched by a mail client, not the web app
        context = await self._context(customer, campaign_id)
        rendered_subject = render.render(subject, context).strip()
        if not rendered_subject:
            raise ValidationFailedError(
                "The subject comes out empty for this customer — add a fallback, e.g. "
                "“{{ customer.full_name }}”")
        body = render.render(html, context, html=True)
        rendered_text = render.render(text, context)
        if recipient_id is not None:
            who = recipient_id
            body = render.track_links(body, lambda url: click_url(who, url, base_url=api))
        body, rendered_text = render.with_footer(body, rendered_text, sender_name=prefs.from_name,
                                                footer_address=prefs.footer_address,
                                                unsubscribe_url=context["unsubscribe_url"])
        if recipient_id is not None:  # after the footer, so the unsubscribe link stays a plain link
            body = f"{body}\n{render.tracking_pixel(open_url(recipient_id, base_url=api))}\n"
        rendered_preheader = render.render(preheader, context).strip() if preheader else None
        return RenderedEmail(subject=rendered_subject, preheader=rendered_preheader, html=body,
                             text=rendered_text)

    async def _check(self, *, subject: str, preheader: str | None, html: str, text: str) -> None:
        """Render a template with sample data before it is stored, so typos are caught here."""
        await self._render(subject=subject, preheader=preheader, html=html, text=text, customer=None)

    # ---- templates -----------------------------------------------------------------------------
    async def list_templates(self, params: PageParams, *, q: str | None = None) -> TemplatePage:
        rows, total = await self.templates.paginate(self.templates.search(q=q), params)
        people = await self._people() if any(row.updated_by for row in rows) else {}
        items = []
        for row in rows:
            item = TemplateSummary.model_validate(row)
            item.updated_by_name = people.get(row.updated_by) if row.updated_by else None
            items.append(item)
        return TemplatePage(items=items, total=total, page=params.page, page_size=params.page_size)

    async def _get(self, template_id: int) -> EmailTemplate:
        template = await self.templates.get(template_id)
        if template is None:
            raise NotFoundError("Template not found")
        return template

    async def get_template(self, template_id: int) -> TemplateOut:
        template = await self._get(template_id)
        people = await self._people() if template.updated_by else {}
        out = TemplateOut.model_validate(template)
        out.updated_by_name = people.get(template.updated_by) if template.updated_by else None
        return out

    async def _check_name(self, name: str, *, keep: int | None = None) -> None:
        other = await self.templates.by_name(name)
        if other is not None and other.id != keep:
            raise ConflictError(f"There is already a template called “{other.name}”")

    async def create_template(self, data: TemplateIn, actor) -> TemplateOut:
        values = data.model_dump(exclude_unset=True)
        await self._check_name(values["name"])
        html = values["html"]
        text = values.get("text") or render.plain_text(html)
        await self._check(subject=values["subject"], preheader=values.get("preheader"), html=html, text=text)
        template = EmailTemplate(name=values["name"], subject=values["subject"], preheader=values.get("preheader"),
                                 html=html, text=text, version=1, created_by=actor.id, updated_by=actor.id)
        await self.templates.add(template)
        await self.audit.record("email_template.create", actor=actor, entity_type=ENTITY, entity_id=template.id,
                                changes=diff({}, _snapshot(template)))
        await self.session.commit()
        return await self.get_template(template.id)

    async def update_template(self, template_id: int, data: TemplateUpdate, actor) -> TemplateOut:
        """PATCH. A field left out is not changed; an emptied `preheader` clears it and an emptied `text`
        body is derived from the HTML again (so is any HTML edit that comes without a text body)."""
        template = await self._get(template_id)
        values = data.model_dump(exclude_unset=True)
        text_emptied = "text" in values and values["text"] is None
        values = {k: v for k, v in values.items() if v is not None or k == "preheader"}
        if values.get("name"):
            await self._check_name(values["name"], keep=template.id)
        html = values.get("html") or template.html
        if text_emptied or ("text" not in values and "html" in values):
            values["text"] = render.plain_text(html)
        merged = {"subject": values.get("subject") or template.subject,
                  "preheader": values["preheader"] if "preheader" in values else template.preheader,
                  "html": html, "text": values.get("text") or template.text}
        await self._check(**merged)
        before = _snapshot(template)
        self.templates.apply(template, values)
        changes = diff(before, _snapshot(template))
        if changes:
            template.version += 1
            template.updated_by = actor.id
            await self.session.flush()
            await self.audit.record("email_template.update", actor=actor, entity_type=ENTITY,
                                    entity_id=template.id, changes=changes)
        await self.session.commit()
        return await self.get_template(template.id)

    async def delete_template(self, template_id: int, actor) -> None:
        template = await self._get(template_id)
        await self.templates.soft_delete(template)
        await self.audit.record("email_template.delete", actor=actor, entity_type=ENTITY, entity_id=template.id,
                                changes={"name": template.name})
        await self.session.commit()

    # ---- preview and test send ------------------------------------------------------------------
    async def _customer(self, customer_id: int | None, actor) -> Customer | None:
        if customer_id is None:
            return None
        await check_entity_access(self.session, actor, "customer", customer_id, write=False)
        customer = await self.customers.get(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        return customer

    async def preview(self, template_id: int, customer_id: int | None, actor) -> RenderedEmail:
        template = await self._get(template_id)
        return await self._render(subject=template.subject, preheader=template.preheader, html=template.html,
                                  text=template.text, customer=await self._customer(customer_id, actor))

    async def test_send(self, template_id: int, data: TestIn, actor) -> TestSent:
        """Send the rendered template to an address of your choosing (SPEC §3.6)."""
        rendered = await self.preview(template_id, data.customer_id, actor)
        sender = self.mail or get_email_sender(self.session)
        await sender.send(Mail(to=str(data.to), subject=rendered.subject, text=rendered.text,
                               html=rendered.html))
        await self.audit.record("email_template.test", actor=actor, entity_type=ENTITY, entity_id=template_id,
                                changes={"to": str(data.to), "subject": rendered.subject})
        await self.session.commit()
        return TestSent(to=str(data.to), subject=rendered.subject)

    # ---- suppression list ------------------------------------------------------------------------
    async def list_suppressions(self, params: PageParams, *, reason: str | None = None,
                                q: str | None = None) -> SuppressionPage:
        rows, total = await self.suppressions.paginate(self.suppressions.search(reason=reason, q=q), params)
        return SuppressionPage(items=[SuppressionOut.model_validate(row) for row in rows], total=total,
                               page=params.page, page_size=params.page_size)

    async def suppress(self, data: SuppressionIn, actor) -> SuppressionOut:
        """Put an address on the list. Adding one that was released before restores its row."""
        email = str(data.email).strip().lower()
        existing = await self.suppressions.by_email(email, include_deleted=True)
        if existing is not None and existing.deleted_at is None:
            raise ConflictError(f"{email} is already on the suppression list")
        suppression = await self._suppress(email, reason=data.reason, source="staff", note=data.note,
                                           actor=actor)
        await self.session.commit()
        return SuppressionOut.model_validate(suppression)

    async def _suppress(self, email: str, *, reason: str, source: str, note: str | None,
                        actor) -> Suppression:
        """Put an address on the list (or restore its row), whoever decided it: staff, or the customer
        themselves through an unsubscribe link. An address already on it is left as it is. The caller commits.
        """
        actor_id = actor.id if actor else None
        email = (email or "").strip().lower()
        if not email:
            raise ValidationFailedError("An account with no email address cannot be suppressed")
        existing = await self.suppressions.by_email(email, include_deleted=True)
        if existing is not None and existing.deleted_at is None:
            return existing
        if existing is not None:
            existing.reason, existing.note, existing.source = reason, note, source
            existing.updated_by = actor_id
            await self.suppressions.restore(existing)
            suppression = existing
        else:
            suppression = await self.suppressions.add(Suppression(
                email=email, reason=reason, note=note, source=source,
                created_by=actor_id, updated_by=actor_id))
        await self.audit.record("suppression.create", actor=actor, entity_type=SUPPRESSION,
                                entity_id=suppression.id,
                                changes={"email": email, "reason": reason, "source": source})
        return suppression

    async def release(self, suppression_id: int, actor) -> None:
        """Take an address off the list: it may be emailed again (staff decision, not a customer's)."""
        suppression = await self.suppressions.get(suppression_id)
        if suppression is None:
            raise NotFoundError("That address is not on the suppression list")
        await self.suppressions.soft_delete(suppression)
        await self.audit.record("suppression.delete", actor=actor, entity_type=SUPPRESSION,
                                entity_id=suppression.id,
                                changes={"email": suppression.email, "reason": suppression.reason})
        await self.session.commit()

    async def suppressed(self, emails: list[str]) -> set[str]:
        """Which of these addresses must not be emailed (lower-cased) — asked by the sender."""
        return await self.suppressions.suppressed_of(emails)

    async def is_suppressed(self, email: str) -> bool:
        return await self.suppressions.by_email(email) is not None

    # ---- audiences: target lists and their members ------------------------------------------------
    async def list_lists(self, params: PageParams, *, kind: str | None = None,
                         q: str | None = None) -> TargetListPage:
        rows, total = await self.lists.paginate(self.lists.search(kind=kind, q=q), params)
        members, reachable = await self._audience_counts(rows)
        people = await self._people() if any(row.updated_by for row in rows) else {}
        items = []
        for row in rows:
            item = TargetListOut.model_validate(row)
            item.members = members.get(row.id, 0)
            item.reachable = reachable.get(row.id, 0)
            item.updated_by_name = people.get(row.updated_by) if row.updated_by else None
            items.append(item)
        return TargetListPage(items=items, total=total, page=params.page, page_size=params.page_size)

    async def _audience_counts(self, rows: list[TargetList]) -> tuple[dict[int, int], dict[int, int]]:
        """`members`/`reachable` per list: counted in the member table for a static list, and as a query
        over the customers for a segment (which is why a segment is always up to date)."""
        static_ids = [row.id for row in rows if row.kind != "segment"]
        members = await self.members.counts(static_ids)
        reachable = await self.members.reachable(static_ids)
        for row in rows:
            if row.kind == "segment":
                members[row.id] = await self._segment_count(row.rules, reachable=False)
                reachable[row.id] = await self._segment_count(row.rules, reachable=True)
        return members, reachable

    async def _segment_count(self, rules: dict[str, Any] | None, *, reachable: bool) -> int:
        result = await self.session.execute(segments.count_stmt(rules, reachable=reachable))
        return int(result.scalar_one())

    async def _get_list(self, list_id: int) -> TargetList:
        target = await self.lists.get(list_id)
        if target is None:
            raise NotFoundError("List not found")
        return target

    async def get_list(self, list_id: int) -> TargetListOut:
        target = await self._get_list(list_id)
        members, reachable = await self._audience_counts([target])
        people = await self._people() if target.updated_by else {}
        out = TargetListOut.model_validate(target)
        out.members = members.get(target.id, 0)
        out.reachable = reachable.get(target.id, 0)
        out.updated_by_name = people.get(target.updated_by) if target.updated_by else None
        return out

    async def _check_list_name(self, name: str, *, keep: int | None = None) -> None:
        other = await self.lists.by_name(name)
        if other is not None and other.id != keep:
            raise ConflictError(f"There is already a list called “{other.name}”")

    async def create_list(self, data: TargetListIn, actor) -> TargetListOut:
        values = data.model_dump(exclude_unset=True)
        await self._check_list_name(values["name"])
        kind = values.get("kind", "static")
        rules = values.get("rules")
        if kind == "segment" and not rules:
            raise ValidationFailedError("A segment needs at least one rule, or it would be every customer")
        if kind == "static" and rules:
            raise ValidationFailedError(
                "A static list picks its members by hand — make it a segment to use rules")
        target = TargetList(name=values["name"], description=values.get("description"), kind=kind,
                            rules=rules if kind == "segment" else None, created_by=actor.id,
                            updated_by=actor.id)
        await self.lists.add(target)
        await self.audit.record("target_list.create", actor=actor, entity_type=LIST, entity_id=target.id,
                                changes={"name": target.name, "kind": target.kind})
        await self.session.commit()
        return await self.get_list(target.id)

    async def update_list(self, list_id: int, data: TargetListUpdate, actor) -> TargetListOut:
        """PATCH: a field left out is not changed; an emptied description clears it. A segment's rules can be
        rewritten at any time — it is a query, not a stored list. `kind` is fixed when the list is created.
        """
        target = await self._get_list(list_id)
        values = data.model_dump(exclude_unset=True)
        if "rules" in values:
            if target.kind != "segment":
                raise ValidationFailedError("Only a segment has rules — this list picks its members by hand")
            if not values["rules"]:
                raise ValidationFailedError("A segment needs at least one rule, or it would be every customer")
        values = {k: v for k, v in values.items() if v is not None or k == "description"}
        if values.get("name"):
            await self._check_list_name(values["name"], keep=target.id)
        before = _list_snapshot(target)
        self.lists.apply(target, values)
        changes = diff(before, _list_snapshot(target))
        if changes:
            target.updated_by = actor.id
            await self.audit.record("target_list.update", actor=actor, entity_type=LIST, entity_id=target.id,
                                    changes=changes)
        await self.session.commit()
        return await self.get_list(target.id)

    async def delete_list(self, list_id: int, actor) -> None:
        """Soft-delete a list: the memberships stay (a mistake is recoverable) but no campaign sees it."""
        target = await self._get_list(list_id)
        await self.lists.soft_delete(target)
        await self.audit.record("target_list.delete", actor=actor, entity_type=LIST, entity_id=target.id,
                                changes={"name": target.name})
        await self.session.commit()

    async def members_of(self, list_id: int, params: PageParams, *, q: str | None = None) -> MemberPage:
        """Who is in the audience — the members, for a static list; the customers matching a segment's rules
        right now, for a segment — each with the state that decides whether a campaign would reach them."""
        target = await self._get_list(list_id)
        if target.kind == "segment":
            customers, total = await self.customers.paginate(segments.members_stmt(target.rules, q=q), params)
            rows: list[tuple[TargetListMember | None, Customer]] = [(None, customer) for customer in customers]
        else:
            rows, total = await self.members.page(target.id, params, q=q)
        suppressed = await self.suppressed([c.email for _, c in rows if c.email])
        return MemberPage(items=[self._member_out(member, customer, suppressed) for member, customer in rows],
                          total=total, page=params.page, page_size=params.page_size)

    @staticmethod
    def _why_not_reachable(customer: Customer, suppressed: set[str]) -> str | None:
        """Why a campaign would skip this customer — None when it would email them (SPEC §3.6).

        The one place this rule is written, so the audience counts, the member list and the sender cannot
        drift apart: a customer who said no must never be emailed by any of them. The reasons are asked from
        the most particular to the most general, so the one kept on a skipped recipient is the useful one.
        """
        if customer.deleted_at is not None:
            return "customer deleted"
        if not customer.email:
            return "no email address"
        if customer.unsubscribed_at is not None:
            return "unsubscribed"
        if customer.email.lower() in suppressed:
            return "suppressed"  # bounced, complained, or put on the list by hand
        if not customer.marketing_consent:
            return "no marketing consent"
        return None

    def _member_out(self, member: TargetListMember | None, customer: Customer,
                    suppressed: set[str]) -> MemberOut:
        email = (customer.email or "").lower()
        blocked = bool(email) and email in suppressed
        return MemberOut(
            customer_id=customer.id, first_name=customer.first_name, last_name=customer.last_name,
            full_name=customer.full_name, company=customer.company, email=customer.email,
            customer_type=customer.customer_type, marketing_consent=customer.marketing_consent,
            unsubscribed=customer.unsubscribed_at is not None, suppressed=blocked,
            reachable=self._why_not_reachable(customer, suppressed) is None,
            added_at=member.created_at if member is not None else None)

    async def add_members(self, list_id: int, data: MembersIn, actor) -> MembersAdded:
        """Put customers on a list. Already there, or not a live customer: skipped, and told so."""
        target = await self._get_list(list_id)
        if target.kind != "static":
            raise ValidationFailedError("A segment picks its own members — add customers to a static list")
        wanted = list(dict.fromkeys(data.customer_ids))  # keep the order, drop repeats
        live = {c.id for c in await self.customers.list(self.customers.search(ids=wanted))}
        already = await self.members.among(target.id, wanted)
        added = 0
        for customer_id in wanted:
            if customer_id not in live or customer_id in already:
                continue
            await self.members.add(TargetListMember(list_id=target.id, customer_id=customer_id,
                                                   created_by=actor.id))
            await self.audit.record("target_list.member_add", actor=actor, entity_type=LIST,
                                    entity_id=target.id, changes={"customer_id": customer_id})
            added += 1
        target.updated_by = actor.id
        await self.session.commit()
        counts = await self.members.counts([target.id])
        # added + already + missing is always the number of ids asked for, duplicates aside
        return MembersAdded(added=added, already=len(live) - added, missing=len(wanted) - len(live),
                            total=counts.get(target.id, 0))

    async def remove_member(self, list_id: int, customer_id: int, actor) -> None:
        """Take a customer off a list. The row goes; the audit log keeps who took them off."""
        target = await self._get_list(list_id)
        if target.kind != "static":
            raise ValidationFailedError("A segment picks its own members — take customers off a static list")
        member = await self.members.by_pair(target.id, customer_id)
        if member is None:
            raise NotFoundError("That customer is not on this list")
        await self.members.hard_delete(member)
        target.updated_by = actor.id
        await self.audit.record("target_list.member_remove", actor=actor, entity_type=LIST,
                                entity_id=target.id, changes={"customer_id": customer_id})
        await self.session.commit()

    # ---- campaigns ---------------------------------------------------------------------------------
    async def _template_names(self, rows: Sequence[Campaign]) -> dict[int, str]:
        ids = list({row.template_id for row in rows})
        templates = await self.templates.list(
            self.templates.query(include_deleted=True).where(EmailTemplate.id.in_(ids or [0])))
        return {template.id: template.name for template in templates}

    async def _list_names(self, rows: Sequence[Campaign]) -> dict[int, str]:
        """Names of the audiences these campaigns use, deleted ones included: a campaign that has gone out
        still says who it went to, even after the list was archived."""
        ids = list({row.target_list_id for row in rows})
        lists = await self.lists.list(self.lists.query(include_deleted=True).where(TargetList.id.in_(ids or [0])))
        return {target.id: target.name for target in lists}

    async def _audiences_for(self, list_ids: Sequence[int]) -> tuple[dict[int, int], dict[int, int]]:
        """`members`/`reachable` for these audiences as they are now (a draft shows what it would go to)."""
        wanted = list(dict.fromkeys(list_ids))
        rows = list(await self.lists.list(
            self.lists.query(include_deleted=True).where(TargetList.id.in_(wanted or [0]))))
        return await self._audience_counts(rows)

    async def list_campaigns(self, params: PageParams, *, status: str | None = None,
                             q: str | None = None) -> CampaignPage:
        rows, total = await self.campaigns.paginate(self.campaigns.search(status=status, q=q), params)
        counts = await self.recipients.counts([row.id for row in rows])
        templates = await self._template_names(rows)
        names = await self._list_names(rows)
        members, reachable = await self._audiences_for([row.target_list_id for row in rows])
        people = await self._people() if any(row.updated_by for row in rows) else {}
        items = []
        for row in rows:
            item = CampaignSummary.model_validate(row)
            item.template_name = templates.get(row.template_id)
            item.target_list_name = names.get(row.target_list_id)
            item.audience = members.get(row.target_list_id, 0)
            item.reachable = reachable.get(row.target_list_id, 0)
            item.recipients = _recipient_counts(counts.get(row.id))
            item.updated_by_name = people.get(row.updated_by) if row.updated_by else None
            items.append(item)
        return CampaignPage(items=items, total=total, page=params.page, page_size=params.page_size)

    async def _get_campaign(self, campaign_id: int) -> Campaign:
        campaign = await self.campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError("Campaign not found")
        return campaign

    async def get_campaign(self, campaign_id: int) -> CampaignOut:
        """One campaign: what it is written from, who it goes to, and where its recipients are."""
        campaign = await self._get_campaign(campaign_id)
        templates = await self._template_names([campaign])
        names = await self._list_names([campaign])
        counts = await self.recipients.counts([campaign.id])
        members, reachable = await self._audiences_for([campaign.target_list_id])
        target = await self.lists.get(campaign.target_list_id, include_deleted=True)
        people = await self._people() if campaign.updated_by else {}
        out = CampaignOut.model_validate(campaign)
        out.template_name = templates.get(campaign.template_id)
        out.target_list_name = names.get(campaign.target_list_id)
        out.target_list_kind = target.kind if target else "static"
        out.audience = members.get(campaign.target_list_id, 0)
        out.reachable = reachable.get(campaign.target_list_id, 0)
        out.recipients = _recipient_counts(counts.get(campaign.id))
        out.updated_by_name = people.get(campaign.updated_by) if campaign.updated_by else None
        return out

    async def _check_campaign_name(self, name: str, *, keep: int | None = None) -> None:
        other = await self.campaigns.by_name(name)
        if other is not None and other.id != keep:
            raise ConflictError(f"There is already a campaign called “{other.name}”")

    async def _check_parts(self, template_id: int, list_id: int) -> None:
        """A campaign is a template and an audience: both must exist and be live (a deleted one is in the
        archive, not in the pickers)."""
        if await self.templates.get(template_id) is None:
            raise ValidationFailedError("Pick a template — that is the words of the campaign")
        if await self.lists.get(list_id) is None:
            raise ValidationFailedError("Pick an audience — that is who the campaign goes to")

    async def create_campaign(self, data: CampaignIn, actor) -> CampaignOut:
        """Write a campaign down. It starts as a draft: scheduling and sending are separate steps."""
        values = data.model_dump()
        await self._check_campaign_name(values["name"])
        await self._check_parts(values["template_id"], values["target_list_id"])
        campaign = await self.campaigns.add(Campaign(
            name=values["name"], template_id=values["template_id"], target_list_id=values["target_list_id"],
            status=DRAFT, created_by=actor.id, updated_by=actor.id))
        await self.audit.record("campaign.create", actor=actor, entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes=diff({}, _campaign_snapshot(campaign)))
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def update_campaign(self, campaign_id: int, data: CampaignUpdate, actor) -> CampaignOut:
        """Change a campaign that has not started. Once it is going out, its template and its audience are
        part of what was sent, and changing them would be a lie."""
        campaign = await self._get_campaign(campaign_id)
        if campaign.status not in (DRAFT, SCHEDULED):
            raise ValidationFailedError(
                "This campaign has already gone out (or is going out) — its template and audience are part "
                "of what was sent")
        values = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        if not values:
            return await self.get_campaign(campaign.id)
        if values.get("name"):
            await self._check_campaign_name(values["name"], keep=campaign.id)
        await self._check_parts(values.get("template_id", campaign.template_id),
                                values.get("target_list_id", campaign.target_list_id))
        before = _campaign_snapshot(campaign)
        self.campaigns.apply(campaign, values)
        campaign.updated_by = actor.id
        changes = diff(before, _campaign_snapshot(campaign))
        if changes:
            await self.audit.record("campaign.update", actor=actor, entity_type=CAMPAIGN,
                                    entity_id=campaign.id, changes=changes)
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def delete_campaign(self, campaign_id: int, actor) -> None:
        """Soft-delete a campaign: it goes out of the lists, and the dispatcher stops picking it up. A paused
        one can go (nothing more is queued); one that is going out has to be paused first."""
        campaign = await self._get_campaign(campaign_id)
        if campaign.status == SENDING:
            raise ValidationFailedError("This campaign is going out — pause it before deleting it")
        await self.campaigns.soft_delete(campaign)
        await self.audit.record("campaign.delete", actor=actor, entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes={"name": campaign.name, "status": campaign.status})
        await self.session.commit()

    async def schedule_campaign(self, campaign_id: int, data: CampaignSchedule, actor) -> CampaignOut:
        """Put a campaign on the calendar. The job picks it up within the minute after its time."""
        campaign = await self._get_campaign(campaign_id)
        if campaign.status not in (DRAFT, SCHEDULED):
            raise ValidationFailedError("Only a campaign that has not started can be put on the calendar")
        when = data.scheduled_at
        if when.tzinfo is None:  # the API works in UTC; a bare time is UTC too
            when = when.replace(tzinfo=timezone.utc)
        if when <= _now():
            raise ValidationFailedError("Pick a time in the future — to send it now, use “send”")
        before = _campaign_snapshot(campaign)
        campaign.scheduled_at, campaign.status = when, SCHEDULED
        campaign.updated_by = actor.id
        await self.audit.record("campaign.schedule", actor=actor, entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes=diff(before, _campaign_snapshot(campaign)))
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def unschedule_campaign(self, campaign_id: int, actor) -> CampaignOut:
        """Take a campaign off the calendar — it has not gone out, so it goes back to being a draft."""
        campaign = await self._get_campaign(campaign_id)
        if campaign.status != SCHEDULED:
            raise ValidationFailedError("Only a scheduled campaign can be taken off the calendar")
        before = _campaign_snapshot(campaign)
        campaign.scheduled_at, campaign.status = None, DRAFT
        campaign.updated_by = actor.id
        await self.audit.record("campaign.unschedule", actor=actor, entity_type=CAMPAIGN,
                                entity_id=campaign.id, changes=diff(before, _campaign_snapshot(campaign)))
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def start_campaign(self, campaign_id: int, actor) -> CampaignOut:
        """Send it now: the audience is copied in and the job takes it from there."""
        campaign = await self._get_campaign(campaign_id)
        if campaign.status not in (DRAFT, SCHEDULED):
            raise ValidationFailedError("This campaign is already going out, or has gone out")
        if await self._audience_size(campaign.target_list_id) == 0:
            raise ValidationFailedError(
                "There is nobody in this audience — put customers on the list (or loosen the segment's "
                "rules) before sending")
        await self._begin(campaign, actor)
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def pause_campaign(self, campaign_id: int, actor) -> CampaignOut:
        """Hold a campaign: messages already in the outbox still go, but no new recipient is looked at."""
        campaign = await self._get_campaign(campaign_id)
        if campaign.status != SENDING:
            raise ValidationFailedError("Only a campaign that is going out can be paused")
        campaign.status, campaign.updated_by = PAUSED, actor.id
        await self.audit.record("campaign.pause", actor=actor, entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes={"status": [SENDING, PAUSED]})
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def resume_campaign(self, campaign_id: int, actor) -> CampaignOut:
        campaign = await self._get_campaign(campaign_id)
        if campaign.status != PAUSED:
            raise ValidationFailedError("Only a paused campaign can be resumed")
        campaign.status, campaign.updated_by = SENDING, actor.id
        await self.audit.record("campaign.resume", actor=actor, entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes={"status": [PAUSED, SENDING]})
        await self.session.commit()
        return await self.get_campaign(campaign.id)

    async def recipients_of(self, campaign_id: int, params: PageParams, *, status: str | None = None,
                            q: str | None = None) -> RecipientPage:
        """Who this campaign went to (or would go to), what happened to each message, and where the whole
        campaign is at (the counts are for all of it, not just this page)."""
        campaign = await self._get_campaign(campaign_id)
        rows, total = await self.recipients.page(campaign.id, params, status=status, q=q)
        counts = await self.recipients.counts([campaign.id])
        items = [RecipientOut(customer_id=customer.id, full_name=customer.full_name,
                             company=customer.company, email=recipient.email, status=recipient.status,
                             reason=recipient.reason, sent_at=recipient.sent_at)
                 for recipient, customer in rows]
        return RecipientPage(items=items, total=total, page=params.page, page_size=params.page_size,
                             counts=_recipient_counts(counts.get(campaign.id)))

    async def record_event(self, recipient_id: int, kind: str, *, url: str = "") -> bool:
        """Record one campaign event for a recipient and add it to the customer timeline once."""
        row = await self.recipients.with_campaign(recipient_id)
        if row is None:
            return False
        recipient, campaign_name = row
        added = await self.events.add_once(campaign_id=recipient.campaign_id, recipient_id=recipient_id,
                                          kind=kind, url=url)
        if not added:
            return False
        if kind == OPEN:
            message = f"Campaign email opened: {campaign_name}"
        elif kind == CLICK:
            message = f"Campaign link clicked: {campaign_name}"
        elif kind == UNSUBSCRIBED:
            message = f"Customer unsubscribed from {campaign_name}"
        else:
            message = f"Campaign tracking: {campaign_name}"
        await self.timeline.record("customer", recipient.customer_id, "campaign.tracked", message,
                                   data={"campaign_id": recipient.campaign_id, "campaign": campaign_name,
                                         "kind": kind, "url": url or None})
        return True

    async def report(self, campaign_id: int) -> CampaignReport:
        """Per-campaign tracking report: delivered, opened, clicked and unsubscribed counts."""
        campaign = await self._get_campaign(campaign_id)
        counts = await self.recipients.counts([campaign.id])
        recipient_counts = _recipient_counts(counts.get(campaign.id))
        people = await self.events.people(campaign.id)
        delivered = recipient_counts.sent
        opened = people.get(OPEN, 0)
        clicked = people.get(CLICK, 0)
        unsubscribed = people.get(UNSUBSCRIBED, 0)
        template = await self.templates.get(campaign.template_id, include_deleted=True)
        target_list_name = (await self._list_names([campaign])).get(campaign.target_list_id)
        return CampaignReport(
            campaign_id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            scheduled_at=campaign.scheduled_at,
            started_at=campaign.started_at,
            finished_at=campaign.finished_at,
            template_name=template.name if template else None,
            target_list_name=target_list_name,
            recipients=recipient_counts,
            delivered=delivered,
            opened=opened,
            clicked=clicked,
            unsubscribed=unsubscribed,
            open_rate=(opened / delivered) if delivered else None,
            click_rate=(clicked / delivered) if delivered else None,
            links=[LinkClicks(url=url, recipients=n) for url, n in await self.events.links(campaign.id)],
        )

    async def stats(self, days: int = 7) -> CampaignStats:
        """Aggregated campaign activity over a trailing window for the dashboard."""
        if days < 1:
            raise ValidationFailedError("Pick a window of at least one day")
        since = _now() - timedelta(days=days)
        rows = await self.campaigns.started_since(since, limit=500)
        if not rows:
            return CampaignStats(days=days)
        ids = [row.id for row in rows]
        counts = await self.recipients.counts(ids)
        people = await self.events.people_for(ids)
        sent = failed = skipped = opened = clicked = unsubscribed = 0
        for campaign in rows:
            row_counts = _recipient_counts(counts.get(campaign.id))
            sent += row_counts.sent
            failed += row_counts.failed
            skipped += row_counts.skipped
            opened += people.get(campaign.id, {}).get(OPEN, 0)
            clicked += people.get(campaign.id, {}).get(CLICK, 0)
            unsubscribed += people.get(campaign.id, {}).get(UNSUBSCRIBED, 0)
        return CampaignStats(
            days=days,
            campaigns=len(rows),
            sent=sent,
            opened=opened,
            clicked=clicked,
            unsubscribed=unsubscribed,
            failed=failed,
            skipped=skipped,
            open_rate=(opened / sent) if sent else None,
            click_rate=(clicked / sent) if sent else None,
        )

    # ---- the dispatcher (background job) -----------------------------------------------------------
    def _audience_of(self, target: TargetList) -> Select[tuple[int, str | None]]:
        return (self.recipients.audience(rules=target.rules) if target.kind == "segment"
                else self.recipients.audience(list_id=target.id))

    async def _audience_size(self, list_id: int) -> int:
        target = await self.lists.get(list_id, include_deleted=True)
        return await self.recipients.audience_size(self._audience_of(target)) if target else 0

    async def _begin(self, campaign: Campaign, actor=None) -> int:
        """Start a campaign: copy its audience in as recipients (once) and mark it as going out."""
        before = _campaign_snapshot(campaign)
        campaign.status, campaign.started_at, campaign.finished_at = SENDING, _now(), None
        target = await self.lists.get(campaign.target_list_id, include_deleted=True)
        copied = await self.recipients.snapshot(campaign.id, self._audience_of(target)) if target else 0
        await self.audit.record("campaign.start", actor=actor, entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes={**diff(before, _campaign_snapshot(campaign)), "recipients": copied})
        return copied

    async def dispatch_due(self, *, max_campaigns: int = 5, batch: int = 100) -> str | None:
        """The background job (every minute): start the campaigns whose time has come, queue what the outbox
        has room for, and close the ones that are done. Returns a line for the job log.

        Nothing is sent from here: a personalized message is queued into the email outbox, which paces itself
        to the SMTP limits and retries what fails. This job only decides who, and how many at a time — never
        more than could go out right now, so no message ever waits long enough to expire unsent.
        """
        settings: EmailSettings = await self.settings.get_model("email")  # type: ignore[assignment]
        due = await self.campaigns.due(_now())
        active = await self.campaigns.sending(limit=max_campaigns)
        if not settings.enabled:
            waiting = len(due) + len(active)
            return f"email is off — {waiting} campaign(s) waiting" if waiting else None
        started = 0
        for campaign in due[:max_campaigns]:
            await self._begin(campaign)
            active.append(campaign)
            started += 1
        room = await self.outbox.room(settings)
        queued = skipped = finished = 0
        for index, campaign in enumerate(active[:max_campaigns]):
            # learn what the outbox did with our messages, and announce what has gone on the timeline — a
            # message is put there when it has been sent, not when it was queued in the outbox
            for _, customer_id in await self.recipients.sync_outbox(campaign.id):
                await self.timeline.record("customer", customer_id, "campaign.sent",
                                           f"Campaign email sent: {campaign.name}",
                                           data={"campaign_id": campaign.id, "campaign": campaign.name})
            if room > 0:  # nothing may go out right now: queue nothing, and let the next run try again
                share = min(batch, max(1, room // (len(active) - index)))  # a fair slice between campaigns
                sent, passed = await self._queue(campaign, share)
                queued, skipped, room = queued + sent, skipped + passed, room - sent
            if await self._close(campaign):
                finished += 1
        await self.session.commit()
        if not any((started, queued, skipped, finished)):
            return None
        return f"started {started}, queued {queued}, skipped {skipped}, finished {finished}"

    async def _queue(self, campaign: Campaign, take: int) -> tuple[int, int]:
        """Look at up to `take` recipients: queue one personalized message for each one a campaign may
        email, and mark the rest as skipped with the reason. Returns (queued, skipped)."""
        rows = await self.recipients.pending(campaign.id, take)
        if not rows:
            return 0, 0
        template = await self.templates.get(campaign.template_id, include_deleted=True)
        if template is None:  # nothing to render (the foreign key makes this all but impossible)
            return 0, 0
        blocked = await self.suppressed([customer.email for _, customer in rows if customer and customer.email])
        queued = skipped = 0
        for recipient, customer in rows:
            if customer is None:  # the customer row is gone: nothing to render, and nobody to write to
                recipient.status, recipient.reason = SKIPPED, "customer deleted"
                skipped += 1
                continue
            reason = self._why_not_reachable(customer, blocked)
            if reason is not None:  # consent is checked now, not when the audience was written
                recipient.status, recipient.reason = SKIPPED, reason
                skipped += 1
                continue
            rendered = await self._render(subject=template.subject, preheader=template.preheader,
                                          html=template.html, text=template.text, customer=customer,
                                          campaign_id=campaign.id,
                                          recipient_id=recipient.id)  # what makes the message tracked
            message = await self.outbox.queue(
                Mail(to=customer.email or "", subject=rendered.subject, text=rendered.text, html=rendered.html),
                category="campaign")
            recipient.status, recipient.outbox_id, recipient.reason = QUEUED, message.id, None
            queued += 1
        await self.session.flush()
        return queued, skipped

    async def _close(self, campaign: Campaign) -> bool:
        """A campaign with nothing left waiting or queued is done."""
        if campaign.status != SENDING:
            return False
        if (await self.recipients.open_counts([campaign.id])).get(campaign.id, 0):
            return False
        campaign.status, campaign.finished_at = SENT, _now()
        counts = (await self.recipients.counts([campaign.id])).get(campaign.id, {})
        await self.audit.record("campaign.finish", entity_type=CAMPAIGN, entity_id=campaign.id,
                                changes={"sent": counts.get(RECIPIENT_SENT, 0),
                                         "skipped": counts.get(SKIPPED, 0),
                                         "failed": counts.get(RECIPIENT_FAILED, 0)})
        return True

    # ---- the unsubscribe link (no login: the token is the proof) -----------------------------------
    async def _from_token(self, token: str) -> Customer:
        customer_id = read_unsubscribe_token(token)  # None when forged, malformed or expired
        customer = await self.customers.get(customer_id, include_deleted=True) if customer_id else None
        if customer is None:
            raise NotFoundError("That unsubscribe link is not valid any more")
        return customer

    @staticmethod
    def _limit_unsubscribe(ip: str | None) -> None:
        """A public endpoint that does database work: keep a script to a trickle (per worker, like the rest)."""
        if ip is None:
            return
        if rate_limit.unsubscribe_by_ip.is_blocked(ip):
            raise TooManyRequestsError("Too many unsubscribe requests — try again later")
        rate_limit.unsubscribe_by_ip.hit(ip)

    async def unsubscribe_info(self, token: str, *, ip: str | None = None) -> UnsubscribeOut:
        """Who an unsubscribe link belongs to, and whether they have already stopped.

        Changes nothing on purpose: a page can show the customer who they are before they confirm, and a mail
        scanner that follows every link in an email cannot unsubscribe anyone by accident.
        """
        self._limit_unsubscribe(ip)
        customer = await self._from_token(token)
        return UnsubscribeOut(name=customer.full_name, email=customer.email or "",
                              unsubscribed=customer.unsubscribed_at is not None
                              or not customer.marketing_consent)

    async def unsubscribe(self, data: UnsubscribeIn, *, ip: str | None = None) -> UnsubscribeOut:
        """Stop emailing the customer the link belongs to: consent off, the address on the suppression list,
        and the campaign the link came from written down (SPEC §3.6 compliance)."""
        self._limit_unsubscribe(ip)
        customer = await self._from_token(data.token)
        how = "unsubscribe link"
        if data.campaign_id is not None:
            campaign = await self.campaigns.get(data.campaign_id, include_deleted=True)
            if campaign is not None:
                how = f"unsubscribe link, campaign “{campaign.name}”"
        if customer.deleted_at is None:  # a deleted customer is not written to, but is still suppressed
            await CustomerService(self.session).mark_consent(customer.id, False, how)
        if customer.email:
            await self._suppress(customer.email, reason="unsubscribed", source="link", note=how, actor=None)
        if data.campaign_id is not None:
            recipient = await self.recipients.by_campaign_customer(data.campaign_id, customer.id)
            if recipient is not None:
                await self.record_event(recipient.id, UNSUBSCRIBED)
        await self.audit.record("campaign.unsubscribe", entity_type=CAMPAIGN, entity_id=data.campaign_id,
                                ip=ip, changes={"customer_id": customer.id, "email": customer.email})
        await self.session.commit()
        return UnsubscribeOut(name=customer.full_name, email=customer.email or "", unsubscribed=True)
