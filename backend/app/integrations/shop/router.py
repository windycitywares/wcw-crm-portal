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

from .backfill import BackfillOut, ShopBackfillService
from .orders import ShopOrderOut, orders_for_customer
from .schemas import ShopEventOut, ShopEventPage, ShopStatus
from .service import ShopEventService, WebhookRejected

router = APIRouter(prefix="/integrations/shop", tags=["integrations"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]
Viewer = Annotated[User, Depends(require(Permission.CUSTOMERS_VIEW))]
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


@router.get("/test", response_model=dict)
async def test_shop_api(session: SessionDep, _: Admin) -> dict:
    """Check the shop API address and token (Integrations → Test connection)."""
    return await ShopBackfillService(session).test_connection()


@router.get("/backfill", response_model=BackfillOut)
async def backfill_state(session: SessionDep, _: Admin) -> BackfillOut:
    return await ShopBackfillService(session).state()


@router.post("/backfill", response_model=BackfillOut)
async def start_backfill(session: SessionDep, actor: Admin) -> BackfillOut:
    return await ShopBackfillService(session).start(actor)


@router.post("/backfill/cancel", response_model=BackfillOut)
async def cancel_backfill(session: SessionDep, actor: Admin) -> BackfillOut:
    return await ShopBackfillService(session).cancel(actor)


@router.get("/customers/{customer_id}/orders", response_model=list[ShopOrderOut])
async def customer_orders(session: SessionDep, _: Viewer, customer_id: int) -> list[ShopOrderOut]:
    """The customer's shop orders (newest first), from the copies the events keep up to date."""
    return await orders_for_customer(session, customer_id)
