"""The public side of campaigns (SPEC §3.6 compliance): the unsubscribe link a customer clicks.

No login, and nothing else belongs in this file. The link in a campaign email points at the web app
(`{site_url}/unsubscribe?token=…`, built by `tokens.py`), whose page calls these two endpoints:

    GET  /campaigns/unsubscribe?token=…   what the link is for — changes nothing
    POST /campaigns/unsubscribe           the customer said no

The token carries the customer id and an expiry, signed with the app secret: it is the only proof needed, and
it cannot be guessed. Only the POST acts, so a mail scanner that follows every link in a message cannot
unsubscribe anyone by accident.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.core.request import client_ip
from app.modules.users.deps import SessionDep

from .schemas import UnsubscribeIn, UnsubscribeOut
from .service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


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
