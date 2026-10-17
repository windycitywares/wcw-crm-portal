"""The public side of campaigns (SPEC §3.6 compliance): the unsubscribe link a customer clicks.

No login, and nothing else belongs in this file. The link in a campaign email points at the web app
(`{site_url}/unsubscribe?token=…`, built by `tokens.py`), whose page calls these two endpoints:

    GET  /campaigns/unsubscribe?token=…   what the link is for — changes nothing
    POST /campaigns/unsubscribe           the customer said no

The token carries the customer id and an expiry, signed with the app secret: it is the only proof needed, and
it cannot be guessed. Only the POST acts, so a mail scanner that follows every link in a message cannot
unsubscribe anyone by accident.
"""

import base64
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.exceptions import NotFoundError
from app.core.request import client_ip
from app.modules.users.deps import SessionDep

from .models import CLICK, OPEN
from .schemas import UnsubscribeIn, UnsubscribeOut
from .service import CampaignService
from .tokens import read_click_token, read_open_token

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_TRACKING_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")


@router.get("/unsubscribe", response_model=UnsubscribeOut)
async def unsubscribe_info(
    request: Request, session: SessionDep,
    token: Annotated[str, Query(max_length=500)],
) -> UnsubscribeOut:
    """Who an unsubscribe link belongs to, and whether they have already stopped. Changes nothing."""
    return await CampaignService(session).unsubscribe_info(token, ip=client_ip(request))


@router.post("/unsubscribe", response_model=UnsubscribeOut)
async def unsubscribe(request: Request, session: SessionDep, data: UnsubscribeIn) -> UnsubscribeOut:
    """Stop emailing the customer the link belongs to (consent off, address suppressed). No login: the token
    in the email is the proof."""
    return await CampaignService(session).unsubscribe(data, ip=client_ip(request))


@router.get("/open")
async def open_tracking(session: SessionDep, token: Annotated[str, Query(max_length=500)]) -> Response:
    """Pixel fetch: a notified open is a one-recipient event, and it is idempotent per recipient."""
    recipient_id = read_open_token(token)
    if recipient_id is None:
        raise NotFoundError("That tracking link is not valid any more")
    await CampaignService(session).record_event(recipient_id, OPEN, url="")
    return Response(content=_TRACKING_PIXEL, media_type="image/gif")


@router.get("/click")
async def click_tracking(session: SessionDep, token: Annotated[str, Query(max_length=1000)]) -> RedirectResponse:
    """Wrapped link click: record a single click per recipient and redirect to the real destination."""
    parsed = read_click_token(token)
    if parsed is None:
        raise NotFoundError("That tracking link is not valid any more")
    recipient_id, destination = parsed
    await CampaignService(session).record_event(recipient_id, CLICK, url=destination)
    return RedirectResponse(url=destination, status_code=307)
