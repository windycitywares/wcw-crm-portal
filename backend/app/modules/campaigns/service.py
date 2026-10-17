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
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.entities import check_entity_access
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.pagination import PageParams
from app.integrations.email import EmailSender, Mail, get_email_sender
from app.modules.audit.service import AuditService, diff
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.lookups.service import LookupService
from app.modules.settings.groups import EmailSettings
from app.modules.settings.service import SettingsService
from app.modules.users.service import UserService

from . import render
from .models import EmailTemplate, Suppression
from .repository import EmailTemplateRepository, SuppressionRepository
from .schemas import (
    RenderedEmail, SuppressionIn, SuppressionOut, SuppressionPage, TemplateIn, TemplateOut, TemplatePage,
    TemplateSummary, TemplateUpdate, TestIn, TestSent,
)
from .tokens import unsubscribe_url

ENTITY = "email_template"
SUPPRESSION = "suppression"
TRACKED = ("name", "subject", "preheader", "version")


def _snapshot(template: EmailTemplate) -> dict[str, Any]:
    """What the audit log keeps: the words that matter and the size of the two bodies."""
    snap: dict[str, Any] = {key: getattr(template, key) for key in TRACKED}
    snap["html"] = f"{len(template.html)} chars"
    snap["text"] = f"{len(template.text)} chars"
    return snap


class CampaignService:
    def __init__(self, session: AsyncSession, email_sender: EmailSender | None = None):
        self.session = session
        self.repo = EmailTemplateRepository(session)
        self.suppressions = SuppressionRepository(session)
        self.audit = AuditService(session)
        self.settings = SettingsService(session)
        self.lookups = LookupService(session)
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

    async def _context(self, customer: Customer | None) -> dict[str, Any]:
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
            unsubscribe = unsubscribe_url(customer.id, base_url=base)
        prefs: EmailSettings = await self.settings.get_model("email")  # type: ignore[assignment]
        return {"customer": fields, "sender_name": prefs.from_name, "unsubscribe_url": unsubscribe}

    async def _render(self, *, subject: str, preheader: str | None, html: str, text: str,
                      customer: Customer | None) -> RenderedEmail:
        """What one customer would get in their inbox: subject, preheader, HTML and text, footer included."""
        prefs: EmailSettings = await self.settings.get_model("email")  # type: ignore[assignment]
        context = await self._context(customer)
        rendered_subject = render.render(subject, context).strip()
        if not rendered_subject:
            raise ValidationFailedError(
                "The subject comes out empty for this customer — add a fallback, e.g. "
                "“{{ customer.full_name }}”")
        body = render.render(html, context, html=True)
        rendered_text = render.render(text, context)
        body, rendered_text = render.with_footer(body, rendered_text, sender_name=prefs.from_name,
                                                footer_address=prefs.footer_address,
                                                unsubscribe_url=context["unsubscribe_url"])
        rendered_preheader = render.render(preheader, context).strip() if preheader else None
        return RenderedEmail(subject=rendered_subject, preheader=rendered_preheader, html=body,
                             text=rendered_text)

    async def _check(self, *, subject: str, preheader: str | None, html: str, text: str) -> None:
        """Render a template with sample data before it is stored, so typos are caught here."""
        await self._render(subject=subject, preheader=preheader, html=html, text=text, customer=None)

    # ---- templates -----------------------------------------------------------------------------
    async def list_templates(self, params: PageParams, *, q: str | None = None) -> TemplatePage:
        rows, total = await self.repo.paginate(self.repo.search(q=q), params)
        people = await self._people() if any(row.updated_by for row in rows) else {}
        items = []
        for row in rows:
            item = TemplateSummary.model_validate(row)
            item.updated_by_name = people.get(row.updated_by) if row.updated_by else None
            items.append(item)
        return TemplatePage(items=items, total=total, page=params.page, page_size=params.page_size)

    async def _get(self, template_id: int) -> EmailTemplate:
        template = await self.repo.get(template_id)
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
        other = await self.repo.by_name(name)
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
        await self.repo.add(template)
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
        self.repo.apply(template, values)
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
        await self.repo.soft_delete(template)
        await self.audit.record("email_template.delete", actor=actor, entity_type=ENTITY, entity_id=template.id,
                                changes={"name": template.name})
        await self.session.commit()

    # ---- preview and test send ------------------------------------------------------------------
    async def _customer(self, customer_id: int | None, actor) -> Customer | None:
        if customer_id is None:
            return None
        await check_entity_access(self.session, actor, "customer", customer_id, write=False)
        customer = await CustomerRepository(self.session).get(customer_id)
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
        if existing is not None:
            existing.reason, existing.note, existing.source = data.reason, data.note, "staff"
            existing.updated_by = actor.id
            await self.suppressions.restore(existing)
            suppression = existing
        else:
            suppression = await self.suppressions.add(Suppression(
                email=email, reason=data.reason, note=data.note, source="staff",
                created_by=actor.id, updated_by=actor.id))
        await self.audit.record("suppression.create", actor=actor, entity_type=SUPPRESSION,
                                entity_id=suppression.id, changes={"email": email, "reason": data.reason})
        await self.session.commit()
        return SuppressionOut.model_validate(suppression)

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
