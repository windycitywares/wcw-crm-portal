from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import (
    Board, DealCreate, DealItemIn, DealItemOut, DealItems, DealItemUpdate, DealOut, DealPage, DealUpdate,
    PipelineIn, PipelineOut, PipelineUpdate, SalesSummary, ShopProductOut, StageIn, StageOut, StageUpdate,
)
from .service import SalesService

router = APIRouter(prefix="/sales", tags=["sales"], dependencies=[Depends(require(Permission.SALES_VIEW))])

Owner = Annotated[User, Depends(require(Permission.SALES_EDIT_OWN))]
Admin = Annotated[User, Depends(require(Permission.LOOKUPS_MANAGE))]


# ---- static paths first, so they aren't read as a deal id ---------------------------------

@router.get("/summary", response_model=SalesSummary)
async def sales_summary(session: SessionDep, user: CurrentUser) -> SalesSummary:
    """Open pipeline value, the weighted forecast, and what was won/lost this month."""
    return await SalesService(session).summary(user)


@router.get("/board", response_model=Board)
async def sales_board(session: SessionDep, pipeline_id: int | None = None) -> Board:
    """The kanban: every stage of a pipeline with its open deals (the default pipeline when none is given)."""
    return await SalesService(session).board(pipeline_id)


@router.get("/shop-products", response_model=list[ShopProductOut])
async def shop_products(session: SessionDep, q: str = "", limit: int = Query(20, ge=1, le=50)) -> list[ShopProductOut]:
    """Search the shop's catalog when adding a line to a deal (`shop_product_id` and SKU come across)."""
    return await SalesService(session).shop_products(q, limit)


@router.get("/pipelines", response_model=list[PipelineOut])
async def list_pipelines(session: SessionDep) -> list[PipelineOut]:
    return await SalesService(session).list_pipelines()


@router.post("/pipelines", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
async def create_pipeline(session: SessionDep, actor: Admin, data: PipelineIn) -> PipelineOut:
    return await SalesService(session).create_pipeline(data, actor)


@router.patch("/pipelines/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline(session: SessionDep, actor: Admin, pipeline_id: int, data: PipelineUpdate) -> PipelineOut:
    return await SalesService(session).update_pipeline(pipeline_id, data, actor)


@router.delete("/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(session: SessionDep, actor: Admin, pipeline_id: int) -> None:
    """Remove a board. Refused while it still has open deals, so live work is never orphaned."""
    await SalesService(session).delete_pipeline(pipeline_id, actor)


@router.post("/pipelines/{pipeline_id}/stages", response_model=StageOut, status_code=status.HTTP_201_CREATED)
async def add_stage(session: SessionDep, actor: Admin, pipeline_id: int, data: StageIn) -> StageOut:
    return await SalesService(session).add_stage(pipeline_id, data, actor)


@router.patch("/pipelines/{pipeline_id}/stages/{stage_id}", response_model=StageOut)
async def update_stage(session: SessionDep, actor: Admin, pipeline_id: int, stage_id: int,
                       data: StageUpdate) -> StageOut:
    return await SalesService(session).update_stage(pipeline_id, stage_id, data, actor)


@router.delete("/pipelines/{pipeline_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(session: SessionDep, actor: Admin, pipeline_id: int, stage_id: int) -> None:
    await SalesService(session).delete_stage(pipeline_id, stage_id, actor)


# ---- deals ---------------------------------------------------------------------------------

@router.get("/deals", response_model=DealPage)
async def list_deals(
    session: SessionDep, user: CurrentUser, page: PageDep,
    view: Literal["all", "mine", "unassigned"] = "all",
    status_: Annotated[Literal["open", "won", "lost", "all"], Query(alias="status")] = "open",
    pipeline_id: int | None = None, stage_id: int | None = None, owner_id: int | None = None,
    customer_id: int | None = None, q: Annotated[str | None, Query(max_length=100)] = None,
) -> DealPage:
    return await SalesService(session).list(
        user, page, view=view, status=None if status_ == "all" else status_, pipeline_id=pipeline_id,
        stage_id=stage_id, owner_id=owner_id, customer_id=customer_id, q=q)


@router.post("/deals", response_model=DealOut, status_code=status.HTTP_201_CREATED)
async def create_deal(session: SessionDep, actor: Owner, data: DealCreate) -> DealOut:
    return await SalesService(session).create(data, actor)


@router.get("/deals/{deal_id}", response_model=DealOut)
async def get_deal(session: SessionDep, deal_id: int) -> DealOut:
    return await SalesService(session).get(deal_id)


@router.patch("/deals/{deal_id}", response_model=DealOut)
async def update_deal(session: SessionDep, actor: CurrentUser, deal_id: int, data: DealUpdate) -> DealOut:
    """Edit a deal, or move it: sending `stage_id` adopts that stage's probability and outcome (won/lost)."""
    return await SalesService(session).update(deal_id, data, actor)


@router.delete("/deals/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deal(session: SessionDep, actor: CurrentUser, deal_id: int) -> None:
    await SalesService(session).delete(deal_id, actor)


# ---- lines on a deal (products from the shop catalog, or typed in) --------------------------

@router.get("/deals/{deal_id}/items", response_model=DealItems)
async def list_deal_items(session: SessionDep, deal_id: int) -> DealItems:
    """What the deal is made of, and what the lines add up to."""
    return await SalesService(session).items(deal_id)


@router.post("/deals/{deal_id}/items", response_model=DealItemOut, status_code=status.HTTP_201_CREATED)
async def add_deal_item(session: SessionDep, actor: CurrentUser, deal_id: int, data: DealItemIn) -> DealItemOut:
    return await SalesService(session).add_item(deal_id, data, actor)


@router.patch("/deals/{deal_id}/items/{item_id}", response_model=DealItemOut)
async def update_deal_item(session: SessionDep, actor: CurrentUser, deal_id: int, item_id: int,
                           data: DealItemUpdate) -> DealItemOut:
    return await SalesService(session).update_item(deal_id, item_id, data, actor)


@router.delete("/deals/{deal_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deal_item(session: SessionDep, actor: CurrentUser, deal_id: int, item_id: int) -> None:
    await SalesService(session).remove_item(deal_id, item_id, actor)
