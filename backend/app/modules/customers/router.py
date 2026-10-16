from typing import Annotated, Literal

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .repository import SORTS
from .schemas import CustomerCreate, CustomerOut, CustomerPage, CustomerUpdate, EmailCheck
from .service import CustomerService
from .transfer import COLUMNS, CustomerTransfer, ImportResult

router = APIRouter(prefix="/customers", tags=["customers"], dependencies=[Depends(require(Permission.CUSTOMERS_VIEW))])
Sort = Literal[tuple(SORTS)]  # type: ignore[valid-type]
DataTools = Annotated[User, Depends(require(Permission.DATA_EXPORT))]


@router.get("", response_model=CustomerPage)
async def list_customers(
    session: SessionDep, user: CurrentUser, page: PageDep, q: str | None = None, type: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None, owner: Literal["me", "any"] = "any",
    owner_id: int | None = None, tag_id: int | None = None, has_orders: bool | None = None, deleted: bool = False,
    sort: Sort = "-updated",
) -> CustomerPage:
    return await CustomerService(session).list(
        page, q=q, customer_type=type, status=status_, owner_id=user.id if owner == "me" else owner_id,
        tag_id=tag_id, has_orders=has_orders, deleted=deleted, sort=sort,
    )


@router.get("/export")
async def export_customers(
    session: SessionDep, user: DataTools, format: Literal["csv", "xlsx"] = "csv", q: str | None = None,
    type: str | None = None, status_: Annotated[str | None, Query(alias="status")] = None,
    owner: Literal["me", "any"] = "any", tag_id: int | None = None, has_orders: bool | None = None,
    deleted: bool = False, sort: Sort = "-updated",
) -> Response:
    """The customers matching the list's filters, as CSV or Excel (managers and admins)."""
    transfer = CustomerTransfer(session)
    header, rows = await transfer.export_rows(dict(
        q=q, customer_type=type, status=status_, owner_id=user.id if owner == "me" else None, tag_id=tag_id,
        has_orders=has_orders, deleted=deleted, sort=sort), user)
    name = f"customers-{date.today().isoformat()}.{format}"
    if format == "xlsx":
        body = transfer.to_xlsx(header, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body, media = transfer.to_csv(header, rows), "text/csv; charset=utf-8"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/import/template")
async def import_template(_: DataTools) -> Response:
    """An empty CSV with the columns the import understands."""
    header = ",".join(f for f in COLUMNS if f != "full_name") + "\r\n"
    return Response("\ufeff" + header, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="customers-import-template.csv"'})


@router.post("/import", response_model=ImportResult)
async def import_customers(
    session: SessionDep, user: DataTools, file: Annotated[UploadFile, File()],
    mode: Annotated[Literal["skip", "update"], Form()] = "skip", dry_run: Annotated[bool, Form()] = True,
) -> ImportResult:
    """Check (dry run) or import a CSV/Excel file of customers. Existing emails are skipped or updated (`mode`)."""
    data = await file.read(5 * 1024 * 1024 + 1)
    return await CustomerTransfer(session).import_file(file.filename or "upload.csv", data, user, mode=mode, dry_run=dry_run)


@router.get("/check-email", response_model=EmailCheck)
async def check_email(session: SessionDep, email: Annotated[str, Query(max_length=320)], exclude_id: int | None = None) -> EmailCheck:
    return await CustomerService(session).check_email(email, exclude_id)


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(session: SessionDep, actor: Annotated[User, Depends(require(Permission.CUSTOMERS_EDIT_OWN))],
                          data: CustomerCreate) -> CustomerOut:
    return await CustomerService(session).create(data, actor)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(session: SessionDep, customer_id: int, deleted: bool = False) -> CustomerOut:
    return await CustomerService(session).get(customer_id, include_deleted=deleted)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(session: SessionDep, actor: CurrentUser, customer_id: int, data: CustomerUpdate) -> CustomerOut:
    return await CustomerService(session).update(customer_id, data, actor)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(session: SessionDep, actor: CurrentUser, customer_id: int) -> None:
    await CustomerService(session).delete(customer_id, actor)


@router.post("/{customer_id}/restore", response_model=CustomerOut)
async def restore_customer(session: SessionDep, actor: CurrentUser, customer_id: int) -> CustomerOut:
    return await CustomerService(session).restore(customer_id, actor)
