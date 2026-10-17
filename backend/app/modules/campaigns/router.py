"""HTTP surface for campaigns (SPEC §3.6): email templates, previews, test sends and the suppression list.

Everything here needs `campaigns:view`; writing a template or the suppression list needs `campaigns:edit`,
and sending a test needs `campaigns:send`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, EmailSenderDep, SessionDep, require
from app.modules.users.models import User

from . import render
from .schemas import (
    MergeField, RenderedEmail, SuppressionIn, SuppressionOut, SuppressionPage, TemplateIn, TemplateOut,
    TemplatePage, TemplateUpdate, TestIn, TestSent,
)
from .service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["campaigns"],
                   dependencies=[Depends(require(Permission.CAMPAIGNS_VIEW))])

Editor = Annotated[User, Depends(require(Permission.CAMPAIGNS_EDIT))]
Sender = Annotated[User, Depends(require(Permission.CAMPAIGNS_SEND))]


@router.get("/merge-fields", response_model=list[MergeField])
async def merge_fields() -> list[MergeField]:
    """What a template may write: `{{ customer.first_name }}` and the rest (SPEC §3.6)."""
    return [MergeField(**field) for field in render.merge_fields()]


# ---- email templates ---------------------------------------------------------------------------


@router.get("/templates", response_model=TemplatePage)
async def list_templates(
    session: SessionDep, page: PageDep, q: Annotated[str | None, Query(max_length=120)] = None,
) -> TemplatePage:
    return await CampaignService(session).list_templates(page, q=q)


@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(session: SessionDep, actor: Editor, data: TemplateIn) -> TemplateOut:
    """Save a template. Merge fields are rendered with sample data first, so a typo comes back as 422."""
    return await CampaignService(session).create_template(data, actor)


@router.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(session: SessionDep, template_id: int) -> TemplateOut:
    return await CampaignService(session).get_template(template_id)


@router.patch("/templates/{template_id}", response_model=TemplateOut)
async def update_template(session: SessionDep, actor: Editor, template_id: int,
                          data: TemplateUpdate) -> TemplateOut:
    return await CampaignService(session).update_template(template_id, data, actor)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(session: SessionDep, actor: Editor, template_id: int) -> None:
    await CampaignService(session).delete_template(template_id, actor)


@router.get("/templates/{template_id}/preview", response_model=RenderedEmail)
async def preview_template(
    session: SessionDep, actor: CurrentUser, template_id: int,
    customer_id: Annotated[int | None, Query()] = None,
) -> RenderedEmail:
    """The email as one customer would receive it — merge fields filled, footer and all."""
    return await CampaignService(session).preview(template_id, customer_id, actor)


@router.post("/templates/{template_id}/test", response_model=TestSent, status_code=status.HTTP_202_ACCEPTED)
async def test_template(session: SessionDep, actor: Sender, sender: EmailSenderDep, template_id: int,
                        data: TestIn) -> TestSent:
    """Send yourself the rendered template (SPEC §3.6). Queued in the outbox, so limits and retries apply."""
    return await CampaignService(session, sender).test_send(template_id, data, actor)


# ---- suppression list --------------------------------------------------------------------------


@router.get("/suppressions", response_model=SuppressionPage)
async def list_suppressions(
    session: SessionDep, page: PageDep,
    reason: Annotated[str | None, Query(max_length=20)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> SuppressionPage:
    return await CampaignService(session).list_suppressions(page, reason=reason, q=q)


@router.post("/suppressions", response_model=SuppressionOut, status_code=status.HTTP_201_CREATED)
async def suppress(session: SessionDep, actor: Editor, data: SuppressionIn) -> SuppressionOut:
    """Never email this address again (SPEC §3.6 compliance)."""
    return await CampaignService(session).suppress(data, actor)


@router.delete("/suppressions/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release(session: SessionDep, actor: Editor, suppression_id: int) -> None:
    """Take an address off the list again — a staff decision, audited."""
    await CampaignService(session).release(suppression_id, actor)
