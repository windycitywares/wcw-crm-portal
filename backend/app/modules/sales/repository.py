from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import Deal, DealItem, Pipeline, PipelineStage


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PipelineRepository(BaseRepository[Pipeline]):
    model = Pipeline

    def ordered(self) -> Select[tuple[Pipeline]]:
        return self.query().order_by(Pipeline.is_default.desc(), Pipeline.name.asc(), Pipeline.id)

    async def default(self) -> Pipeline | None:
        """The pipeline a new deal lands on when none is given: the default one, else the first."""
        rows = await self.list(self.query().order_by(Pipeline.is_default.desc(), Pipeline.id).limit(1))
        return rows[0] if rows else None

    async def by_name(self, name: str) -> Pipeline | None:
        rows = await self.list(self.query().where(func.lower(Pipeline.name) == name.strip().lower()))
        return rows[0] if rows else None


class PipelineStageRepository(BaseRepository[PipelineStage]):
    model = PipelineStage

    def for_pipeline(self, pipeline_id: int) -> Select[tuple[PipelineStage]]:
        return (self.query().where(PipelineStage.pipeline_id == pipeline_id)
                .order_by(PipelineStage.position, PipelineStage.id))

    async def stages(self, pipeline_id: int) -> list[PipelineStage]:
        return list((await self.session.execute(self.for_pipeline(pipeline_id))).scalars())

    async def stages_for(self, pipeline_ids: list[int]) -> list[PipelineStage]:
        if not pipeline_ids:
            return []
        stmt = (self.query().where(PipelineStage.pipeline_id.in_(pipeline_ids))
                .order_by(PipelineStage.pipeline_id, PipelineStage.position, PipelineStage.id))
        return list((await self.session.execute(stmt)).scalars())

    async def max_position(self, pipeline_id: int) -> int:
        stmt = select(func.coalesce(func.max(PipelineStage.position), -1)) \
            .where(PipelineStage.pipeline_id == pipeline_id)
        return int((await self.session.execute(stmt)).scalar_one())


class DealRepository(BaseRepository[Deal]):
    model = Deal

    def search(self, *, pipeline_id: int | None = None, stage_id: int | None = None, status: str | None = None,
               owner_id: int | None = None, unassigned: bool = False, customer_id: int | None = None,
               close_before: date | None = None, q: str | None = None) -> Select[tuple[Deal]]:
        stmt = self.query()
        if pipeline_id is not None:
            # a deal's pipeline is its stage's pipeline (there is no pipeline_id column to keep in step)
            stmt = stmt.join(PipelineStage, Deal.stage_id == PipelineStage.id) \
                .where(PipelineStage.pipeline_id == pipeline_id)
        if stage_id is not None:
            stmt = stmt.where(Deal.stage_id == stage_id)
        if status:
            stmt = stmt.where(Deal.status == status)
        if owner_id is not None:
            stmt = stmt.where(Deal.owner_id == owner_id)
        if unassigned:
            stmt = stmt.where(Deal.owner_id.is_(None))
        if customer_id is not None:
            stmt = stmt.where(Deal.customer_id == customer_id)
        if close_before is not None:
            stmt = stmt.where(Deal.expected_close_on < close_before)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(func.lower(Deal.title).like(p), func.lower(Deal.description).like(p)))
        # soonest expected close first (undated last), then newest
        return stmt.order_by(Deal.expected_close_on.asc().nullslast(), Deal.id.desc())

    async def for_stages(self, stage_ids: list[int], *, status: str = "open") -> list[Deal]:
        if not stage_ids:
            return []
        stmt = (self.query().where(Deal.stage_id.in_(stage_ids), Deal.status == status)
                .order_by(Deal.position, Deal.id))
        return list((await self.session.execute(stmt)).scalars())

    async def count_where(self, *conditions) -> int:
        stmt = select(func.count()).select_from(Deal).where(Deal.deleted_at.is_(None), *conditions)
        return int((await self.session.execute(stmt)).scalar_one())

    async def sum_where(self, column, *conditions) -> Decimal:
        stmt = select(func.coalesce(func.sum(column), 0)).select_from(Deal) \
            .where(Deal.deleted_at.is_(None), *conditions)
        return Decimal((await self.session.execute(stmt)).scalar_one() or 0)

    async def max_position(self, stage_id: int) -> int:
        stmt = select(func.coalesce(func.max(Deal.position), -1)).where(Deal.stage_id == stage_id)
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_in_stage(self, stage_id: int, *, status: str | None = None) -> int:
        conditions = [Deal.stage_id == stage_id]
        if status:
            conditions.append(Deal.status == status)
        return await self.count_where(*conditions)

    async def count_in_pipeline(self, pipeline_id: int, *, status: str | None = None) -> int:
        stmt = (select(func.count()).select_from(Deal)
                .join(PipelineStage, Deal.stage_id == PipelineStage.id)
                .where(Deal.deleted_at.is_(None), PipelineStage.pipeline_id == pipeline_id))
        if status:
            stmt = stmt.where(Deal.status == status)
        return int((await self.session.execute(stmt)).scalar_one())


class DealItemRepository(BaseRepository[DealItem]):
    model = DealItem

    def for_deal(self, deal_id: int) -> Select[tuple[DealItem]]:
        return self.query().where(DealItem.deal_id == deal_id).order_by(DealItem.position, DealItem.id)

    async def lines(self, deal_id: int) -> list[DealItem]:
        return list((await self.session.execute(self.for_deal(deal_id))).scalars())

    async def max_position(self, deal_id: int) -> int:
        stmt = select(func.coalesce(func.max(DealItem.position), -1)).where(DealItem.deal_id == deal_id)
        return int((await self.session.execute(stmt)).scalar_one())

    async def total(self, deal_id: int) -> Decimal:
        """Quantity × unit price, added up — what the lines come to (compare it with the deal's value)."""
        stmt = (select(func.coalesce(func.sum(DealItem.quantity * DealItem.unit_price), 0))
                .select_from(DealItem).where(DealItem.deal_id == deal_id, DealItem.deleted_at.is_(None)))
        return Decimal((await self.session.execute(stmt)).scalar_one() or 0).quantize(Decimal("0.01"))
