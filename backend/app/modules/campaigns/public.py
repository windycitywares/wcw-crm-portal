"""The public side of campaigns (SPEC §3.6 compliance): the unsubscribe link a customer clicks.

No login, and nothing else belongs in this file. The link in a campaign email points at the web app
(`{site_url}/unsubscribe?token=…`, built by `tokens.py`), whose page calls these two endpoints:

    GET  /campaigns/unsubscribe?token=…   what the link is for — changes nothing
    POST /campaigns/unsubscribe           the customer said no

The `List-Unsubscribe` header of every campaign message carries the same token as a URL on the API (`tokens.py`
mints it too), and that address has its own pair:

    GET  /campaigns/unsubscribe/one-click?token=…   a browser that followed the header's link: sent on to the
                                                    page above, changing nothing
    POST /campaigns/unsubscribe/one-click?token=…   a mail client finishing it for the reader (RFC 8058 "one
                                                    click"): nothing is read from the body, so the URL carries
                                                    the whole request

The token carries the customer id and an expiry, signed with the app secret: it is the only proof needed, and
it cannot be guessed. Only the POSTs act, so a mail scanner that follows every link in a message cannot
unsubscribe anyone by accident.
"""

import base64
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
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


@router.get("/unsubscribe/one-click")
async def unsubscribe_one_click_link(
    token: Annotated[str, Query(max_length=500)],
    c: Annotated[int | None, Query(ge=1)] = None,
) -> RedirectResponse:
    """A reader (or a scanner) that opened the header's link in a browser instead of posting it goes on to the
    real page, which shows them who they are and asks. Nothing is decided here — a GET never acts — and the
    token travels as it arrived, so this opens the same page as the footer's link."""
    url = f"{get_settings().site_url.rstrip('/')}/unsubscribe?token={quote(token, safe='')}"
    return RedirectResponse(url=f"{url}&c={c}" if c else url, status_code=307)


@router.post("/unsubscribe/one-click", response_model=UnsubscribeOut)
async def unsubscribe_one_click(
    request: Request, session: SessionDep,
    token: Annotated[str, Query(max_length=500)],
    c: Annotated[int | None, Query(ge=1)] = None,
) -> UnsubscribeOut:
    """The click a mail client makes for the reader (RFC 8058): the address in the `List-Unsubscribe` header is
    the whole request. What the client puts in the body is not read — the signed token in the URL is the proof,
    exactly as in the footer's link — and `c` is the campaign it came from, when the header carried one."""
    return await CampaignService(session).unsubscribe(UnsubscribeIn(token=token, campaign_id=c),
                                                      ip=client_ip(request))


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
