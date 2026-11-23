from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .service import EtsySkuPush, UrnService

router = APIRouter(prefix="/urns", tags=["urns"], dependencies=[Depends(require(Permission.CHANNELS_VIEW))])
Worker = Annotated[User, Depends(require(Permission.CHANNELS_EDIT))]     # names, suppliers, variations
Owner = Annotated[User, Depends(require(Permission.CHANNELS_MANAGE))]    # prices, extras, sizes, SKU format
Needs = Literal["supplier", "review", "prices", "ready"]


class SizeIn(BaseModel):
    type_id: int | None = None
    code: str | None = Field(default=None, max_length=10)
    label: str | None = Field(default=None, max_length=40)
    position: int | None = None
    aliases: list[str] | None = Field(default=None, max_length=30)
    active: bool | None = None


class SizeOut(BaseModel):
    id: int
    type_id: int
    code: str
    label: str
    position: int
    aliases: list[str]
    active: bool


class TypeIn(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    code: str | None = Field(default=None, max_length=10)
    template: str | None = Field(default=None, max_length=80)
    size_format: str | None = Field(default=None, max_length=20)
    separator: str | None = Field(default=None, max_length=3)
    position: int | None = None
    active: bool | None = None


class TypeOut(BaseModel):
    id: int
    name: str
    code: str | None
    template: str
    size_format: str
    separator: str
    position: int
    active: bool
    sizes: list[SizeOut]
    products: int
    examples: list[str]
    problems: list[str]


class FormatCheck(BaseModel):
    template: str | None = Field(default=None, max_length=80)
    size_format: str | None = Field(default=None, max_length=20)
    separator: str | None = Field(default=None, max_length=3)
    code: str | None = Field(default=None, max_length=10)


class FormatOut(BaseModel):
    problems: list[str]
    examples: list[str]


class UrnUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    type_id: int | None = None
    supplier_id: int | None = None
    notes: str | None = Field(default=None, max_length=5000)


class AssignIn(BaseModel):
    urn_ids: list[int] = Field(min_length=1, max_length=500)
    supplier_id: int | None


class AssignTypeIn(BaseModel):
    urn_ids: list[int] = Field(min_length=1, max_length=500)
    type_id: int


class QuantitiesIn(BaseModel):
    quantities: dict[str, int]


class ApproveIn(BaseModel):
    urn_ids: list[int] | None = None
    variation_ids: list[int] | None = None


class PriceIn(BaseModel):
    size_code: str = Field(max_length=10)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    effective_from: date | None = None


class ExtraIn(BaseModel):
    urn_id: int | None = None
    type_id: int | None = None
    name: str = Field(min_length=1, max_length=80)
    mode: Literal["amount", "percent"] = "amount"
    value: Decimal = Field(max_digits=12, decimal_places=4)
    applies: Literal["piece", "order"] = "piece"
    size_code: str | None = Field(default=None, max_length=10)
    party: Literal["supplier", "ours"] = "supplier"
    effective_from: date | None = None
    effective_to: date | None = None


class EndIn(BaseModel):
    on: date | None = None


def _size(s) -> SizeOut:
    return SizeOut(id=s.id, type_id=s.type_id, code=s.code, label=s.label, position=s.position, aliases=list(s.aliases or []),
                   active=s.active)


@router.get("/summary")
async def summary(session: SessionDep) -> dict[str, int]:
    """The setup to-do list: listings without a urn, urns without a supplier or prices, variations to review."""
    return await UrnService(session).summary()


async def _type_out(svc: UrnService, t) -> TypeOut:
    from sqlalchemy import func, select

    from .models import Urn

    n = (await svc.session.execute(select(func.count()).select_from(Urn).where(
        Urn.type_id == t.id, Urn.deleted_at.is_(None)))).scalar_one()
    _, problems, examples = await svc.check_format(t.id, {})
    return TypeOut(id=t.id, name=t.name, code=t.code, template=t.template, size_format=t.size_format,
                   separator=t.separator, position=t.position, active=t.active,
                   sizes=[_size(s) for s in await svc.sizes(t.id)], products=n, examples=examples, problems=problems)


@router.get("/types", response_model=list[TypeOut])
async def product_types(session: SessionDep) -> list[TypeOut]:
    """Product types, each with its SKU format, its sizes and how many products it has."""
    svc = UrnService(session)
    return [await _type_out(svc, t) for t in await svc.types()]


@router.post("/types", response_model=TypeOut, status_code=status.HTTP_201_CREATED)
async def add_type(session: SessionDep, actor: Owner, data: TypeIn) -> TypeOut:
    """A new type starts as one item, one price (no sizes); add sizes to it if it comes in sizes."""
    svc = UrnService(session)
    return await _type_out(svc, await svc.save_type(None, data.model_dump(exclude_unset=True), actor))


@router.patch("/types/{type_id}", response_model=TypeOut)
async def edit_type(session: SessionDep, actor: Owner, type_id: int, data: TypeIn) -> TypeOut:
    """Rename a type or change its SKU format. Its products' SKUs change in the CRM; nothing is sent to Etsy."""
    svc = UrnService(session)
    return await _type_out(svc, await svc.save_type(type_id, data.model_dump(exclude_unset=True), actor))


@router.post("/types/{type_id}/check", response_model=FormatOut)
async def check_type_format(session: SessionDep, type_id: int, data: FormatCheck) -> FormatOut:
    """Try a format for a type without saving: its problems and example SKUs."""
    _, problems, examples = await UrnService(session).check_format(type_id, data.model_dump(exclude_none=True))
    return FormatOut(problems=problems, examples=examples)


@router.get("/sizes", response_model=list[SizeOut])
async def sizes(session: SessionDep, type_id: int | None = None) -> list[SizeOut]:
    return [_size(s) for s in await UrnService(session).sizes(type_id)]


@router.post("/sizes", response_model=SizeOut, status_code=status.HTTP_201_CREATED)
async def add_size(session: SessionDep, actor: Owner, data: SizeIn) -> SizeOut:
    return _size(await UrnService(session).save_size(None, data.model_dump(exclude_unset=True), actor))


@router.patch("/sizes/{size_id}", response_model=SizeOut)
async def edit_size(session: SessionDep, actor: Owner, size_id: int, data: SizeIn) -> SizeOut:
    return _size(await UrnService(session).save_size(size_id, data.model_dump(exclude_unset=True), actor))


@router.post("/setup")
async def setup(session: SessionDep, actor: Worker) -> dict[str, int]:
    """A urn draft for every Etsy listing without one, with its variations read. Safe to run again."""
    return await UrnService(session).setup_from_listings(actor)


@router.get("/review")
async def review(session: SessionDep, state: Literal["open", "proposed", "unclear", "approved", "all"] = "open",
                 page: Annotated[int, Query(ge=1)] = 1,
                 page_size: Annotated[int, Query(ge=1, le=500)] = 100) -> dict[str, Any]:
    return await UrnService(session).review(state=state, page=page, page_size=page_size)


@router.post("/approve")
async def approve(session: SessionDep, actor: Worker, data: ApproveIn) -> dict[str, int]:
    """Approve what was read (never the unclear ones) — for some urns, some variations, or everything."""
    return {"approved": await UrnService(session).approve(data.urn_ids, actor, data.variation_ids)}


@router.post("/assign-supplier")
async def assign_supplier(session: SessionDep, actor: Worker, data: AssignIn) -> dict[str, int]:
    return {"updated": await UrnService(session).assign_supplier(data.urn_ids, data.supplier_id, actor)}


@router.post("/assign-type")
async def assign_type(session: SessionDep, actor: Worker, data: AssignTypeIn) -> dict[str, int]:
    """Set the type of several products; their variations are read again with that type's sizes."""
    return {"updated": await UrnService(session).assign_type(data.urn_ids, data.type_id, actor)}


@router.get("/sku-preview")
async def sku_preview(session: SessionDep, only_different: bool = False) -> dict[str, Any]:
    """What Etsy has next to the SKU the CRM would write, per variation. Sending them to Etsy is switched off."""
    svc = UrnService(session)
    return {"items": await svc.sku_preview(only_different=only_different),
            "etsy_push_enabled": (await svc.sku_settings()).etsy_push_enabled}


@router.post("/sku-preview/apply", status_code=status.HTTP_204_NO_CONTENT)
async def push_skus(session: SessionDep, actor: Owner) -> None:
    await EtsySkuPush(session).apply(actor)


@router.get("/extras")
async def shared_extras(session: SessionDep, type_id: int | None = None) -> list[dict[str, Any]]:
    """Extra costs for every product (no type_id) or for every product of one type."""
    svc = UrnService(session)
    return [svc.extra_out(e) for e in await svc.extras(None, type_id=type_id)]


@router.post("/extras", status_code=status.HTTP_201_CREATED)
async def add_extra(session: SessionDep, actor: Owner, data: ExtraIn) -> dict[str, Any]:
    svc = UrnService(session)
    return svc.extra_out(await svc.save_extra(None, data.model_dump(), actor))


@router.patch("/extras/{extra_id}")
async def edit_extra(session: SessionDep, actor: Owner, extra_id: int, data: ExtraIn) -> dict[str, Any]:
    svc = UrnService(session)
    return svc.extra_out(await svc.save_extra(extra_id, data.model_dump(exclude_unset=True), actor))


@router.post("/extras/{extra_id}/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_extra(session: SessionDep, actor: Owner, extra_id: int, data: EndIn) -> None:
    await UrnService(session).end_extra(extra_id, data.on, actor)


@router.get("")
async def list_urns(session: SessionDep, q: Annotated[str | None, Query(max_length=120)] = None,
                    supplier_id: int | None = None, needs: Needs | None = None, type_id: int | None = None,
                    page: Annotated[int, Query(ge=1)] = 1,
                    page_size: Annotated[int, Query(ge=1, le=200)] = 50) -> dict[str, Any]:
    return await UrnService(session).list(q=q, supplier_id=supplier_id, needs=needs, page=page, page_size=page_size,
                                          type_id=type_id)


@router.get("/{urn_id}")
async def get_urn(session: SessionDep, urn_id: int) -> dict[str, Any]:
    return await UrnService(session).detail(urn_id)


@router.patch("/{urn_id}")
async def update_urn(session: SessionDep, actor: Worker, urn_id: int, data: UrnUpdate) -> dict[str, Any]:
    svc = UrnService(session)
    await svc.update(urn_id, data.model_dump(exclude_unset=True), actor)
    return await svc.detail(urn_id)


@router.delete("/{urn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_urn(session: SessionDep, actor: Owner, urn_id: int) -> None:
    await UrnService(session).delete(urn_id, actor)


@router.post("/{urn_id}/refresh")
async def refresh(session: SessionDep, actor: Worker, urn_id: int) -> dict[str, Any]:
    """Read the listing's variations again (new ones are read, gone ones hidden; approved ones untouched)."""
    svc = UrnService(session)
    await svc.refresh(urn_id)
    return await svc.detail(urn_id)


@router.put("/{urn_id}/variations/{variation_id}")
async def set_variation(session: SessionDep, actor: Worker, urn_id: int, variation_id: int,
                        data: QuantitiesIn) -> dict[str, Any]:
    svc = UrnService(session)
    return svc.variation_out(await svc.set_variation(urn_id, variation_id, data.quantities, actor))


@router.post("/{urn_id}/prices", status_code=status.HTTP_204_NO_CONTENT)
async def set_price(session: SessionDep, actor: Owner, urn_id: int, data: PriceIn) -> None:
    """The supplier's price for one piece of a size, from a date (default today). Earlier sales keep their price."""
    await UrnService(session).set_price(urn_id, data.size_code, data.amount, data.effective_from, actor)


@router.delete("/{urn_id}/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(session: SessionDep, actor: Owner, urn_id: int, price_id: int) -> None:
    await UrnService(session).delete_price(urn_id, price_id, actor)
