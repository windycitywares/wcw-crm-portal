"""Sales channels (External shops): which marketplaces exist and are connected, and the Etsy connection."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .catalog import CHANNELS
from .connection import EtsyConnectionService
from .dashboard import EtsyDashboard
from .handover import ShopHandover, handover
from .etsy import status as etsy_status
from .listings import EtsyListingSync, ListingService
from .orders import OrderService
from .orders_sync import EtsyOrderSync
from .payments import SupplierPayments

router = APIRouter(prefix="/channels", tags=["channels"], dependencies=[Depends(require(Permission.CHANNELS_VIEW))])
Manager = Annotated[User, Depends(require(Permission.CHANNELS_MANAGE))]
Worker = Annotated[User, Depends(require(Permission.CHANNELS_EDIT))]
Payer = Annotated[User, Depends(require(Permission.CHANNELS_PAYMENTS))]
PaymentState = Literal["pending", "settled", "cost_missing", "all"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CredentialsIn(BaseModel):
    client_id: str | None = Field(default=None, max_length=100)
    client_secret: str | None = Field(default=None, max_length=200)


@router.get("")
async def channels(response: Response, session: SessionDep) -> dict[str, Any]:
    """Every marketplace, whether it can be connected yet and whether it is: the sidebar's External shops group
    shows one entry per connected channel."""
    response.headers["Cache-Control"] = "no-store"
    etsy = await EtsyConnectionService(session).connected()
    return {"items": [{"key": c.key, "label": c.label, "available": c.available,
                       "connected": etsy if c.key == "etsy" else False} for c in CHANNELS.values()]}


@router.get("/etsy/connection")
async def etsy_connection(response: Response, session: SessionDep) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await EtsyConnectionService(session).status()


@router.put("/etsy/credentials")
async def save_credentials(body: CredentialsIn, session: SessionDep, actor: Manager) -> dict[str, Any]:
    service = EtsyConnectionService(session)
    await service.save_credentials(actor, body.client_id, body.client_secret)
    return await service.status()


@router.post("/etsy/connect")
async def connect(session: SessionDep, actor: Manager) -> dict[str, str]:
    """The address of Etsy's "Allow access" screen; the browser goes there and Etsy sends it back to the callback."""
    return {"url": await EtsyConnectionService(session).start(actor)}


@router.post("/etsy/disconnect")
async def disconnect(session: SessionDep, actor: Manager) -> dict[str, Any]:
    service = EtsyConnectionService(session)
    await service.disconnect(actor)
    return await service.status()


# ---- listings (Etsy's own fields are read-only; the team keeps supplier, cost and notes) ----------------


class ListingTeamIn(BaseModel):
    supplier_account_id: int | None = None
    purchase_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    notes: str | None = Field(default=None, max_length=5000)


@router.get("/etsy/listings")
async def etsy_listings(
    response: Response, session: SessionDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    state: Annotated[str | None, Query(max_length=20)] = None,
    supplier: Annotated[str | None, Query(max_length=20, description="an account id, or 'none'")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await ListingService(session).search(q=q, state=state, supplier=supplier, page=page, page_size=page_size)


@router.patch("/etsy/listings/{listing_id}")
async def update_etsy_listing(listing_id: int, body: ListingTeamIn, session: SessionDep, actor: Worker) -> dict[str, Any]:
    return await ListingService(session).update(listing_id, body.model_dump(exclude_unset=True), actor)


@router.post("/etsy/sync")
async def sync_etsy_now(session: SessionDep, actor: Worker) -> dict[str, Any]:
    """Bring Etsy's listings and orders in now instead of waiting for the next pass."""
    listings = await EtsyListingSync(session).run(force=True)
    return {"listings": listings, "orders": await EtsyOrderSync(session).run(force=True)}


# ---- orders ---------------------------------------------------------------------------------------------------


class OrderPatch(BaseModel):
    purchase_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    shipping_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    supplier_account_id: int | None = None
    supplier_order_number: str | None = Field(default=None, max_length=100)
    carrier: str | None = Field(default=None, max_length=60)
    tracking_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    buyer_phone: str | None = Field(default=None, max_length=50)


class StatusIn(BaseModel):
    status: str = Field(max_length=20)
    note: str | None = Field(default=None, max_length=300)


@router.get("/etsy/statuses")
async def order_statuses() -> dict[str, Any]:
    """Every order status with its label, the main path and which ones count as open."""
    return {"labels": etsy_status.LABELS, "main_path": list(etsy_status.MAIN_PATH),
            "exceptions": list(etsy_status.EXCEPTIONS), "open": list(etsy_status.OPEN_STATUSES)}


@router.get("/etsy/orders")
async def etsy_orders(
    response: Response, session: SessionDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    attention: bool = False,
    supplier: Annotated[str | None, Query(max_length=20, description="an account id, or 'none'")] = None,
    listing_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await OrderService(session).search(q=q, status=status, attention=attention, supplier=supplier,
                                              listing_id=listing_id, date_from=date_from, date_to=date_to,
                                              page=page, page_size=page_size)


@router.get("/etsy/orders/{order_id}")
async def etsy_order(order_id: int, response: Response, session: SessionDep) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await OrderService(session).detail(order_id)


@router.patch("/etsy/orders/{order_id}")
async def update_etsy_order(order_id: int, body: OrderPatch, session: SessionDep, actor: Worker) -> dict[str, Any]:
    return await OrderService(session).update(order_id, actor, body.model_dump(exclude_unset=True))


@router.post("/etsy/orders/{order_id}/status")
async def set_etsy_order_status(order_id: int, body: StatusIn, session: SessionDep, actor: Worker) -> dict[str, Any]:
    return await OrderService(session).set_status(order_id, actor, body.status, body.note)


# ---- supplier payments: what each supplier is owed (purchase + shipping cost), recorded and exported -------------


class SettleIn(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=500)
    paid_on: date | None = None
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=300)
    amount: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = None


class UndoIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


def _today() -> date:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).date()


@router.get("/etsy/supplier-payments/overview")
async def payments_overview(
    response: Response, session: SessionDep,
    supplier: Annotated[str | None, Query(max_length=20)] = None,
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await SupplierPayments(session).overview(supplier, date_from, date_to)


@router.get("/etsy/supplier-payments")
async def payments_list(
    response: Response, session: SessionDep, state: PaymentState = "pending",
    supplier: Annotated[str | None, Query(max_length=20)] = None,
    date_from: date | None = None, date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    rows, total = await SupplierPayments(session).rows(state, supplier, date_from, date_to, page_size,
                                                       (page - 1) * page_size)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/etsy/supplier-payments/export")
async def payments_export(
    session: SessionDep, format: Literal["csv", "xlsx"] = "csv", state: PaymentState = "pending",
    supplier: Annotated[str | None, Query(max_length=20)] = None,
    date_from: date | None = None, date_to: date | None = None,
) -> Response:
    service = SupplierPayments(session)
    rows, _ = await service.rows(state, supplier, date_from, date_to)
    name = f"supplier-payments-{state}-{_today().isoformat()}"
    if format == "xlsx":
        data, mime, ext = service.xlsx_bytes(rows, f"{state.title()} payments"), XLSX_MIME, "xlsx"
    else:
        data, mime, ext = service.csv_bytes(rows), "text/csv; charset=utf-8", "csv"
    return Response(data, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{name}.{ext}"', "Cache-Control": "no-store"})


@router.post("/etsy/supplier-payments/settle")
async def payments_settle(body: SettleIn, session: SessionDep, actor: Payer) -> dict[str, Any]:
    return await SupplierPayments(session).settle(actor, body.order_ids, body.paid_on or _today(), body.reference,
                                                  body.note, body.amount)


@router.post("/etsy/supplier-payments/{order_id}/undo")
async def payments_undo(order_id: int, body: UndoIn, session: SessionDep, actor: Payer) -> dict[str, bool]:
    await SupplierPayments(session).unsettle(actor, order_id, body.reason)
    return {"ok": True}


@router.get("/etsy/dashboard")
async def etsy_dashboard(
    response: Response, session: SessionDep, start: date | None = None, end: date | None = None,
    listing_id: int | None = None, supplier: Annotated[str | None, Query(max_length=20)] = None,
) -> dict[str, Any]:
    """Sales, costs, profit and fulfilment for the period (default: the last 30 days) against the one before it."""
    response.headers["Cache-Control"] = "no-store"
    board = EtsyDashboard(session)
    return await board.build(await board.range(start, end), listing_id, supplier)


@router.post("/etsy/import-from-shop")
async def import_from_shop(session: SessionDep, actor: Manager) -> dict[str, Any]:
    """Copy the team's Etsy work (costs, suppliers, notes, tracking, payments, history) from the shop once; safe to rerun."""
    return await handover(session, actor)


@router.get("/etsy/import-from-shop/check")
async def import_check(session: SessionDep, _: Manager) -> dict[str, Any]:
    from app.core.exceptions import ValidationFailedError
    from app.integrations.shop.client import ShopApiError

    try:
        return await ShopHandover(session).check()
    except ShopApiError as exc:
        raise ValidationFailedError(f"The shop didn't answer: {exc}") from exc
