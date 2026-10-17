"""HTTP surface for campaigns (SPEC §3.6): email templates, previews, test sends, audiences (target lists,
segments and their members) and the suppression list.

Everything here needs `campaigns:view`; writing a template, an audience or the suppression list needs
`campaigns:edit`, and sending a test needs `campaigns:send`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, EmailSenderDep, SessionDep, require
from app.modules.users.models import User

from . import render, segments
from .schemas import (
    MemberPage, MembersAdded, MembersIn, MergeField, RenderedEmail, SegmentField, SuppressionIn, SuppressionOut,
    SuppressionPage, TargetListIn, TargetListOut, TargetListPage, TargetListUpdate, TemplateIn, TemplateOut,
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


@router.get("/segment-fields", response_model=list[SegmentField])
async def segment_fields() -> list[SegmentField]:
    """What a segment may be built from: each field, how to ask for its value, and the ops it allows."""
    return [SegmentField(**field) for field in segments.fields()]



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


# ---- audiences ---------------------------------------------------------------------------------


@router.get("/lists", response_model=TargetListPage)
async def list_lists(
    session: SessionDep, page: PageDep,
    kind: Annotated[str | None, Query(max_length=10)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> TargetListPage:
    """The audiences: how many customers each has, and how many a campaign could actually email."""
    return await CampaignService(session).list_lists(page, kind=kind, q=q)


@router.post("/lists", response_model=TargetListOut, status_code=status.HTTP_201_CREATED)
async def create_list(session: SessionDep, actor: Editor, data: TargetListIn) -> TargetListOut:
    """An audience: a static list you fill by hand, or a segment defined by rules (see `/segment-fields`)."""
    return await CampaignService(session).create_list(data, actor)


@router.get("/lists/{list_id}", response_model=TargetListOut)
async def get_list(session: SessionDep, list_id: int) -> TargetListOut:
    return await CampaignService(session).get_list(list_id)


@router.patch("/lists/{list_id}", response_model=TargetListOut)
async def update_list(session: SessionDep, actor: Editor, list_id: int, data: TargetListUpdate) -> TargetListOut:
    return await CampaignService(session).update_list(list_id, data, actor)


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_list(session: SessionDep, actor: Editor, list_id: int) -> None:
    await CampaignService(session).delete_list(list_id, actor)


@router.get("/lists/{list_id}/members", response_model=MemberPage)
async def list_members(
    session: SessionDep, page: PageDep, list_id: int,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> MemberPage:
    """Who is in the audience — a static list's members, or the customers a segment matches right now."""
    return await CampaignService(session).members_of(list_id, page, q=q)


@router.post("/lists/{list_id}/members", response_model=MembersAdded)
async def add_members(session: SessionDep, actor: Editor, list_id: int, data: MembersIn) -> MembersAdded:
    """Put customers on a list; ids already on it, or not a live customer, are skipped and counted."""
    return await CampaignService(session).add_members(list_id, data, actor)


@router.delete("/lists/{list_id}/members/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(session: SessionDep, actor: Editor, list_id: int, customer_id: int) -> None:
    await CampaignService(session).remove_member(list_id, customer_id, actor)


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
