"""The one public route of sales channels: where Etsy sends the browser back after "Allow access".

The one-time `state` stored when the browser left is the only check, so nothing else is trusted from the request;
the person is sent on to Settings → Sales channels with the outcome.
"""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.modules.users.deps import SessionDep

from .connection import EtsyConnectionService
from .etsy.client import EtsyError

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/etsy/callback", include_in_schema=False)
async def etsy_callback(
    session: SessionDep,
    state: Annotated[str | None, Query(max_length=200)] = None,
    code: Annotated[str | None, Query(max_length=2000)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    base = get_settings().site_url.rstrip("/") + "/settings/channels?"
    if error or not (state and code):
        return RedirectResponse(f"{base}etsy=failed&reason={quote(error or 'Etsy did not allow access')}")
    try:
        name = await EtsyConnectionService(session).finish(state, code)
    except (EtsyError, ValidationFailedError) as exc:
        return RedirectResponse(f"{base}etsy=failed&reason={quote(str(exc)[:200])}")
    return RedirectResponse(f"{base}etsy=connected&shop={quote(name)}")
