from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.core.rate_limit import RateLimiter
from app.core.request import client_ip
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .schemas import ShopEventOut, ShopEventPage, ShopStatus
from .service import ShopEventService, WebhookRejected

router = APIRouter(prefix="/integrations/shop", tags=["integrations"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]
bad_signatures = RateLimiter(max_hits=30, window_seconds=600)
WEBHOOK_PATH = "/integrations/shop/webhook"


@router.post("/webhook", include_in_schema=False)
async def shop_webhook(request: Request, session: SessionDep) -> JSONResponse:
    """Signed events from the shop. Not behind a login: the HMAC signature is the authentication."""
    ip = client_ip(request)
    if bad_signatures.is_blocked(ip):
        return JSONResponse({"detail": "Too many invalid requests"}, status_code=429)
    body = await request.body()
    try:
        result = await ShopEventService(session).receive(
            body, request.headers.get("x-wcw-timestamp"), request.headers.get("x-wcw-signature"))
    except WebhookRejected as exc:
        if exc.status_code == 401:
            bad_signatures.hit(ip)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse({"status": result})


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and request.headers.get("x-forwarded-proto") == "https":
        base = "https://" + base.removeprefix("http://")
    return f"{base}{get_settings().api_prefix}{WEBHOOK_PATH}"


@router.get("/status", response_model=ShopStatus)
async def shop_status(request: Request, session: SessionDep, _: Admin) -> ShopStatus:
    return await ShopEventService(session).status(_webhook_url(request))


@router.get("/events", response_model=ShopEventPage)
async def shop_events(session: SessionDep, _: Admin, page: PageDep,
                      status: Literal["pending", "done", "failed", "ignored"] | None = None) -> ShopEventPage:
    return await ShopEventService(session).list(page, status)


@router.post("/events/{event_id}/retry", response_model=ShopEventOut)
async def retry_event(session: SessionDep, _: Admin, event_id: int) -> ShopEventOut:
    return await ShopEventService(session).retry(event_id)
