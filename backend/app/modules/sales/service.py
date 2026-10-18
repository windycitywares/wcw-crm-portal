"""Sales (SPEC §3.3): pipelines, their stages, and the deals that move through them.

Rules:
- `sales:view` reads everything; `sales:edit_own` adds deals and changes the ones you own or created;
  `sales:edit_any` changes anyone's deal and hands one to someone else;
- pipelines and stages are configured by `lookups:manage` (Admin → Settings → Pipelines);
- the **stage decides the outcome**: a stage with `is_won` / `is_lost` marks the deal won or lost when it
  lands there (that is what dropping a card on the kanban does); any other stage makes it open again. The
  stage's `probability` is the default the deal adopts — the weighted forecast is value × probability;
- a deal about a customer needs read access to that customer; the customer's timeline shows the deal being
  opened, moving stage, being won or lost (the deal keeps its own timeline too);
- the **lines** on a deal follow the deal's own rule: `sales:edit_own` adds and edits the lines on your own
  deals. A line total never overwrites the deal's value — the two are shown side by side, so a quote the
  salesperson typed is not silently replaced by the sum of the products;
- a pipeline is soft-deleted, and neither a pipeline nor a stage can be removed while it still has open
  deals, so no live work is ever orphaned.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, check_entity_access, entity_labels, register_entity
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customfields.service import CustomFieldService
from app.modules.lookups.service import LookupService
from app.modules.settings.service import SettingsService
from app.modules.users.service import UserService
from app.shared.time import utcnow

from .models import Deal, DealItem, Pipeline, PipelineStage
from .repository import DealItemRepository, DealRepository, PipelineRepository, PipelineStageRepository
from .schemas import (
    Board, BoardStage, DealCreate, DealItemIn, DealItemOut, DealItems, DealItemUpdate, DealOut, DealPage,
    DealUpdate, PipelineIn, PipelineOut, PipelineUpdate, SalesSummary, StageIn, StageOut, StageUpdate,
)

ENTITY = "deal"
TRACKED = ("title", "description", "customer_id", "stage_id", "status", "value", "currency", "probability",
           "expected_close_on", "closed_at", "owner_id", "source", "lost_reason", "position")

# Starter board (SPEC §3.3 mentions Custom order and Wholesale as examples), used when a pipeline is
# created without stages. Values: (name, probability, is_won, is_lost, colour).
STARTER_STAGES: tuple[tuple[str, int, bool, bool, str], ...] = (
    ("New", 10, False, False, "neutral"),
    ("Qualified", 30, False, False, "info"),
    ("Proposal", 50, False, False, "warning"),
    ("Negotiation", 70, False, False, "accent"),
    ("Won", 100, True, False, "success"),
    ("Lost", 0, False, True, "danger"),
)
DEFAULT_PIPELINE = "Sales"


def _stage_status(stage: PipelineStage | None) -> str:
    if stage is not None and stage.is_won:
        return "won"
    if stage is not None and stage.is_lost:
        return "lost"
    return "open"


def _stage_snapshot(stage: PipelineStage) -> dict[str, Any]:
    return {"name": stage.name, "probability": stage.probability, "is_won": stage.is_won,
            "is_lost": stage.is_lost, "color": stage.color, "position": stage.position}


def weighted_value(deal: Deal) -> Decimal:
    """What the deal counts for in the forecast: its value × probability."""
    return (deal.value * deal.probability / Decimal(100)).quantize(Decimal("0.01"))


def _snapshot(d: Deal) -> dict[str, Any]:
    """Audit-friendly values: the audit log is JSON, so dates and money become text."""
    out: dict[str, Any] = {}
    for key in TRACKED:
        value = getattr(d, key)
        out[key] = str(value) if isinstance(value, Decimal) else (
            value.isoformat() if isinstance(value, (date, datetime)) else value)
    return out


def _quantity(value: Decimal) -> str:
    """2, 1.5, 10.5 — a quantity without the trailing zeros the money column pads it with."""
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


def _item_snapshot(item: DealItem) -> dict[str, Any]:
    return {"name": item.name, "sku": item.sku, "shop_product_id": item.shop_product_id,
            "quantity": str(item.quantity), "unit_price": str(item.unit_price), "position": item.position}


def _item_title(item: DealItem) -> str:
    """How a line reads on a timeline: "2 × Windy Widget = 30.00"."""
    return f"{_quantity(item.quantity)} × {item.name} = {item.total}"


async def _exists(session, entity_id: int) -> bool:
    return await DealRepository(session).get(entity_id) is not None


def _may_change(user, deal: Deal) -> bool:
    return has_permission(user.role, Permission.SALES_EDIT_ANY) or (
        has_permission(user.role, Permission.SALES_EDIT_OWN) and user.id in (deal.owner_id, deal.created_by))


async def _can_edit(session, user, entity_id: int) -> bool:
    deal = await DealRepository(session).get(entity_id)
    return deal is not None and _may_change(user, deal)


async def _labels(session, ids: list[int]) -> dict[int, str]:
    repo = DealRepository(session)
    return {d.id: d.title for d in await repo.list(repo.query(include_deleted=True).where(Deal.id.in_(ids)))}


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Deal", view=(Permission.SALES_VIEW,),
        edit=(Permission.SALES_EDIT_OWN, Permission.SALES_EDIT_ANY), exists=_exists, can_edit=_can_edit,
        labels=_labels,
    ))


class SalesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DealRepository(session)
        self.pipelines = PipelineRepository(session)
        self.stages = PipelineStageRepository(session)
        self.lines = DealItemRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)
        self.fields = CustomFieldService(session)

    # ---- helpers ------------------------------------------------------------------------------
    async def _out(self, deals: list[Deal]) -> list[DealOut]:
        if not deals:
            return []
        stage_ids = sorted({d.stage_id for d in deals if d.stage_id})
        stage_rows = await self.stages.list(self.stages.query().where(PipelineStage.id.in_(stage_ids)))
        stages = {s.id: s for s in stage_rows}
        pipeline_ids = sorted({s.pipeline_id for s in stage_rows})
        pipeline_rows = await self.pipelines.list(self.pipelines.query().where(Pipeline.id.in_(pipeline_ids)))
        pipelines = {p.id: p.name for p in pipeline_rows}
        customer_ids = [d.customer_id for d in deals if d.customer_id]
        names = await entity_labels(self.session, "customer", customer_ids) if customer_ids else {}
        people = {u.id: u.full_name for u in await UserService(self.session).directory()}
        out = []
        for d in deals:
            item = DealOut.model_validate(d)
            stage = stages.get(d.stage_id) if d.stage_id else None
            item.stage_name = stage.name if stage else None
            item.pipeline_id = stage.pipeline_id if stage else None
            item.pipeline_name = pipelines.get(stage.pipeline_id) if stage else None
            item.customer_name = names.get(d.customer_id) if d.customer_id else None
            item.owner_name = people.get(d.owner_id) if d.owner_id else None
            item.weighted_value = weighted_value(d)
            out.append(item)
        return out

    async def _get(self, deal_id: int) -> Deal:
        deal = await self.repo.get(deal_id)
        if deal is None:
            raise NotFoundError("Deal not found")
        return deal

    async def _stage(self, stage_id: int) -> PipelineStage:
        stage = await self.stages.get(stage_id)
        if stage is None:
            raise NotFoundError("Stage not found")
        return stage

    async def _pipeline(self, pipeline_id: int | None) -> Pipeline:
        pipeline = await self.pipelines.get(pipeline_id) if pipeline_id is not None else await self.pipelines.default()
        if pipeline is None:
            raise ValidationFailedError("Set up a pipeline first (Admin → Settings → Pipelines)")
        return pipeline

    async def _tz(self) -> ZoneInfo:
        hours = await SettingsService(self.session).get_model("business_hours")
        return ZoneInfo(getattr(hours, "timezone", "America/Chicago"))

    async def _month_start(self) -> datetime:
        """Midnight on the 1st in the business timezone: what the summary counts as "this month"."""
        tz = await self._tz()
        return datetime.combine(datetime.now(tz).date().replace(day=1), time(0), tz).astimezone(timezone.utc)

    def _check_owner(self, user, owner_id: int | None, current: int | None = None) -> None:
        if owner_id is not None and owner_id != user.id and owner_id != current \
                and not has_permission(user.role, Permission.SALES_EDIT_ANY):
            raise PermissionDeniedError("Only managers can give deals to someone else")

    async def _check_lookups(self, values: dict[str, Any], current: Deal | None = None) -> None:
        if values.get("source"):
            values["source"] = await self.lookups.require(
                "lead_source", values["source"], allow_inactive_key=current.source if current else None)
        if values.get("lost_reason"):
            values["lost_reason"] = await self.lookups.require(
                "lost_reason", values["lost_reason"], allow_inactive_key=current.lost_reason if current else None)

    async def _line(self, deal: Deal, kind: str, title: str, actor) -> None:
        """Same line on the deal and on its customer (SPEC §3.2: the customer timeline lists deals)."""
        await self.timeline.record(ENTITY, deal.id, kind, title, actor=actor)
        if deal.customer_id:
            await self.timeline.record("customer", deal.customer_id, kind, title, actor=actor, data={"deal_id": deal.id})

    # ---- reads --------------------------------------------------------------------------------
    async def list(self, user, params: PageParams, *, view: str = "all", status: str | None = None,
                   pipeline_id: int | None = None, stage_id: int | None = None, owner_id: int | None = None,
                   customer_id: int | None = None, q: str | None = None) -> DealPage:
        filters: dict[str, Any] = {"status": status, "pipeline_id": pipeline_id, "stage_id": stage_id,
                                   "customer_id": customer_id, "q": q}
        if view == "mine":
            filters["owner_id"] = user.id
        elif view == "unassigned":
            filters["unassigned"] = True
        elif owner_id is not None:
            filters["owner_id"] = owner_id
        rows, total = await self.repo.paginate(self.repo.search(**filters), params)
        return DealPage(items=await self._out(list(rows)), total=total, page=params.page,
                        page_size=params.page_size)

    async def get(self, deal_id: int) -> DealOut:
        return (await self._out([await self._get(deal_id)]))[0]

    async def board(self, pipeline_id: int | None = None) -> Board:
        """The kanban: the pipeline's stages in order, each with its open deals and its money."""
        pipeline = await self._pipeline(pipeline_id)
        stages = await self.stages.stages(pipeline.id)
        items = await self._out(await self.repo.for_stages([s.id for s in stages]))
        by_stage: dict[int, list[DealOut]] = {}
        for item in items:
            by_stage.setdefault(item.stage_id or 0, []).append(item)
        columns = []
        for stage in stages:
            deals = by_stage.get(stage.id, [])
            columns.append(BoardStage(
                stage=StageOut.model_validate(stage), deals=deals,
                total_value=sum((d.value for d in deals), Decimal("0")),
                weighted_value=sum((d.weighted_value for d in deals), Decimal("0")),
            ))
        return Board(pipeline_id=pipeline.id, pipeline_name=pipeline.name, stages=columns)

    async def summary(self, user) -> SalesSummary:
        start = await self._month_start()
        return SalesSummary(
            open_count=await self.repo.count_where(Deal.status == "open"),
            open_value=await self.repo.sum_where(Deal.value, Deal.status == "open"),
            weighted_value=await self.repo.sum_where(Deal.value * Deal.probability / 100, Deal.status == "open"),
            won_count=await self.repo.count_where(Deal.status == "won", Deal.closed_at >= start),
            won_value=await self.repo.sum_where(Deal.value, Deal.status == "won", Deal.closed_at >= start),
            lost_count=await self.repo.count_where(Deal.status == "lost", Deal.closed_at >= start),
        )

    # ---- deal writes --------------------------------------------------------------------------
    async def create(self, data: DealCreate, actor, *, commit: bool = True) -> DealOut:
        """Open a deal. Callers inside a bigger change (converting a lead) pass `commit=False`, so the deal is
        committed together with it."""
        values = data.model_dump(exclude_unset=True)
        if not values.get("title"):
            raise ValidationFailedError("A deal needs a title")
        owner_id = values.pop("owner_id", None) or actor.id
        self._check_owner(actor, owner_id)
        if values.get("customer_id") is not None:
            await check_entity_access(self.session, actor, "customer", values["customer_id"], write=False)
        stage = await self._stage(values["stage_id"]) if values.get("stage_id") is not None else None
        if "stage_id" not in values:
            first = await self.stages.stages((await self._pipeline(None)).id)
            stage = first[0] if first else None
        values["stage_id"] = stage.id if stage else None
        if values.get("status") is None:
            values["status"] = _stage_status(stage)  # the stage decides, unless the caller was explicit
        if values.get("probability") is None:
            values["probability"] = stage.probability if stage else 0
        await self._check_lookups(values)
        if values.get("custom_fields") is not None:
            values["custom_fields"] = await self.fields.validate(ENTITY, values["custom_fields"] or {})
        deal = Deal(**{k: v for k, v in values.items() if v is not None}, owner_id=owner_id,
                    created_by=actor.id, updated_by=actor.id)
        if deal.status in ("won", "lost"):
            deal.closed_at = utcnow()
        elif deal.stage_id is not None:
            deal.position = await self.repo.max_position(deal.stage_id) + 1
        await self.repo.add(deal)
        await self.audit.record("deal.create", actor=actor, entity_type=ENTITY, entity_id=deal.id,
                                changes=diff({}, _snapshot(deal)))
        await self._line(deal, "deal.created", f"Deal opened: {deal.title}", actor)
        if commit:
            await self.session.commit()
        return await self.get(deal.id)

    async def update(self, deal_id: int, data: DealUpdate, actor) -> DealOut:
        deal = await self._get(deal_id)
        if not _may_change(actor, deal):
            raise PermissionDeniedError("You can only change deals you own")
        values = data.model_dump(exclude_unset=True)
        if "title" in values and not values["title"]:
            raise ValidationFailedError("A deal needs a title")
        if "owner_id" in values:
            if values["owner_id"] is None:
                values["owner_id"] = deal.owner_id
            self._check_owner(actor, values["owner_id"], deal.owner_id)
        if values.get("customer_id") is not None and values["customer_id"] != deal.customer_id:
            await check_entity_access(self.session, actor, "customer", values["customer_id"], write=False)
        await self._check_lookups(values, deal)

        moved = "stage_id" in values and values["stage_id"] != deal.stage_id
        if moved:
            stage = await self._stage(values["stage_id"]) if values["stage_id"] is not None else None
            values["stage_id"] = stage.id if stage else None
            if values.get("probability") is None:
                values["probability"] = stage.probability if stage else deal.probability
            values["status"] = _stage_status(stage)
            if "position" not in values:
                values["position"] = (await self.repo.max_position(stage.id) + 1) if stage else deal.position
        before = _snapshot(deal)
        self.repo.apply(deal, values)
        if deal.status in ("won", "lost"):
            if deal.closed_at is None or moved:
                deal.closed_at = utcnow()
            if deal.status == "won":
                deal.lost_reason = None  # a won deal isn't a lost one
        else:
            deal.closed_at = None
        deal.updated_by = actor.id
        await self.session.flush()
        changes = diff(before, _snapshot(deal))
        if changes:
            await self.audit.record("deal.update", actor=actor, entity_type=ENTITY, entity_id=deal.id, changes=changes)
            await self._move_line(deal, before, actor)
        await self.session.commit()
        return await self.get(deal.id)

    async def _move_line(self, deal: Deal, before: dict[str, Any], actor) -> None:
        if deal.status != before["status"] and deal.status in ("won", "lost"):
            await self._line(deal, f"deal.{deal.status}", f"Deal {deal.status}: {deal.title}", actor)
        elif deal.stage_id != before["stage_id"]:
            stage = await self._stage(deal.stage_id) if deal.stage_id else None
            where = stage.name if stage else "no board"
            await self._line(deal, "deal.moved", f"Deal moved to {where}: {deal.title}", actor)

    async def delete(self, deal_id: int, actor) -> None:
        deal = await self._get(deal_id)
        if not _may_change(actor, deal):
            raise PermissionDeniedError("You can only delete deals you own")
        await self.repo.soft_delete(deal)
        await self.audit.record("deal.delete", actor=actor, entity_type=ENTITY, entity_id=deal.id,
                                changes={"title": deal.title})
        await self._line(deal, "deal.deleted", f"Deal deleted: {deal.title}", actor)
        await self.session.commit()

    # ---- lines on a deal (SPEC §3.3: products from the shop catalog, or typed in by hand) ------

    async def _deal_to_change(self, deal_id: int, actor) -> Deal:
        deal = await self._get(deal_id)
        if not _may_change(actor, deal):
            raise PermissionDeniedError("You can only change the lines on your own deals")
        return deal

    async def _item(self, deal_id: int, item_id: int) -> DealItem:
        item = await self.lines.get(item_id)
        if item is None or item.deal_id != deal_id:
            raise NotFoundError("Line not found")  # or it belongs to another deal
        return item

    async def _deal_items(self, deal_id: int) -> DealItems:
        rows = await self.lines.lines(deal_id)
        return DealItems(items=[DealItemOut.model_validate(i) for i in rows], count=len(rows),
                         total=await self.lines.total(deal_id))

    async def items(self, deal_id: int) -> DealItems:
        """The lines on a deal. Anyone who can see sales can see what a deal is made of."""
        await self._get(deal_id)  # a missing deal is a 404, not an empty list
        return await self._deal_items(deal_id)

    async def add_item(self, deal_id: int, data: DealItemIn, actor) -> DealItemOut:
        deal = await self._deal_to_change(deal_id, actor)
        values = data.model_dump(exclude_unset=True)
        if not values.get("name"):
            raise ValidationFailedError("Give the line a name")
        position = values.pop("position", None)
        if position is None:
            position = await self.lines.max_position(deal.id) + 1  # new lines go to the bottom
        item = DealItem(deal_id=deal.id, position=position, created_by=actor.id, updated_by=actor.id, **values)
        await self.lines.add(item)
        await self._line(deal, "deal.item_added", f"Line added: {_item_title(item)}", actor)
        await self.audit.record("deal_item.create", actor=actor, entity_type=ENTITY, entity_id=deal.id,
                                changes=_item_snapshot(item) | {"item_id": item.id})
        await self.session.commit()
        return DealItemOut.model_validate(item)

    async def update_item(self, deal_id: int, item_id: int, data: DealItemUpdate, actor) -> DealItemOut:
        deal = await self._deal_to_change(deal_id, actor)
        item = await self._item(deal_id, item_id)
        values = data.model_dump(exclude_unset=True)
        # a form sends null for a field it isn't changing, and a name and money are never empty
        for key in ("name", "quantity", "unit_price"):
            if values.get(key) is None:
                values.pop(key, None)
        if not values:
            return DealItemOut.model_validate(item)
        before = _item_snapshot(item)
        self.lines.apply(item, values)
        item.updated_by = actor.id
        await self.session.flush()
        changes = diff(before, _item_snapshot(item))
        if changes:
            await self._line(deal, "deal.item_changed", f"Line changed: {_item_title(item)}", actor)
            await self.audit.record("deal_item.update", actor=actor, entity_type=ENTITY, entity_id=deal.id,
                                    changes=changes | {"item_id": item.id})
        await self.session.commit()
        return DealItemOut.model_validate(item)

    async def remove_item(self, deal_id: int, item_id: int, actor) -> None:
        deal = await self._deal_to_change(deal_id, actor)
        item = await self._item(deal_id, item_id)
        await self.lines.soft_delete(item)
        await self._line(deal, "deal.item_removed", f"Line removed: {_item_title(item)}", actor)
        await self.audit.record("deal_item.delete", actor=actor, entity_type=ENTITY, entity_id=deal.id,
                                changes={"item_id": item.id, "name": item.name})
        await self.session.commit()

    # ---- pipelines & stages (Admin → Settings → Pipelines) -------------------------------------
    async def list_pipelines(self) -> list[PipelineOut]:
        rows = list(await self.pipelines.list(self.pipelines.ordered()))
        by_pipeline: dict[int, list[PipelineStage]] = {}
        for stage in await self.stages.stages_for([p.id for p in rows]):
            by_pipeline.setdefault(stage.pipeline_id, []).append(stage)
        out = []
        for p in rows:
            item = PipelineOut.model_validate(p)
            item.stages = [StageOut.model_validate(s) for s in by_pipeline.get(p.id, [])]
            out.append(item)
        return out

    async def _get_pipeline(self, pipeline_id: int) -> Pipeline:
        pipeline = await self.pipelines.get(pipeline_id)
        if pipeline is None:
            raise NotFoundError("Pipeline not found")
        return pipeline

    async def _make_default(self, pipeline: Pipeline) -> None:
        for other in await self.pipelines.list(self.pipelines.query().where(Pipeline.is_default.is_(True))):
            if other.id != pipeline.id:
                other.is_default = False

    async def create_pipeline(self, data: PipelineIn, actor) -> PipelineOut:
        if not data.name:
            raise ValidationFailedError("A pipeline needs a name")
        if await self.pipelines.by_name(data.name):
            raise ValidationFailedError("There is already a pipeline with that name")
        first = not await self.pipelines.count()
        pipeline = await self.pipelines.add(Pipeline(
            name=data.name, is_default=data.is_default or first, created_by=actor.id, updated_by=actor.id))
        if pipeline.is_default:
            await self._make_default(pipeline)
        starter = data.stages if data.stages else [StageIn(name=n, probability=p, is_won=w, is_lost=l, color=c)
                                                   for n, p, w, l, c in STARTER_STAGES]
        for position, stage in enumerate(starter):
            await self.stages.add(PipelineStage(**stage.model_dump(), pipeline_id=pipeline.id, position=position))
        await self.audit.record("pipeline.create", actor=actor, entity_type="pipeline", entity_id=pipeline.id,
                                changes={"name": pipeline.name, "stages": [s.name for s in starter]})
        await self.session.commit()
        return next(p for p in await self.list_pipelines() if p.id == pipeline.id)

    async def update_pipeline(self, pipeline_id: int, data: PipelineUpdate, actor) -> PipelineOut:
        pipeline = await self._get_pipeline(pipeline_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and not changes["name"]:
            raise ValidationFailedError("A pipeline needs a name")
        if changes.get("name"):
            clash = await self.pipelines.by_name(changes["name"])
            if clash is not None and clash.id != pipeline.id:
                raise ValidationFailedError("There is already a pipeline with that name")
        before = {"name": pipeline.name, "is_default": pipeline.is_default}
        self.pipelines.apply(pipeline, changes)
        pipeline.updated_by = actor.id
        if pipeline.is_default:
            await self._make_default(pipeline)
        after = {"name": pipeline.name, "is_default": pipeline.is_default}
        await self.audit.record("pipeline.update", actor=actor, entity_type="pipeline", entity_id=pipeline.id,
                                changes=diff(before, after))
        await self.session.commit()
        return next(p for p in await self.list_pipelines() if p.id == pipeline.id)

    async def delete_pipeline(self, pipeline_id: int, actor) -> None:
        pipeline = await self._get_pipeline(pipeline_id)
        if await self.repo.count_in_pipeline(pipeline.id, status="open"):
            raise ValidationFailedError("Move this pipeline's open deals to another pipeline first")
        await self.pipelines.soft_delete(pipeline)
        await self.audit.record("pipeline.delete", actor=actor, entity_type="pipeline", entity_id=pipeline.id,
                                changes={"name": pipeline.name})
        await self.session.commit()

    async def add_stage(self, pipeline_id: int, data: StageIn, actor) -> StageOut:
        pipeline = await self._get_pipeline(pipeline_id)
        if not data.name:
            raise ValidationFailedError("A stage needs a name")
        self._check_stage_flags(data.is_won, data.is_lost)
        stage = await self.stages.add(PipelineStage(
            **data.model_dump(), pipeline_id=pipeline.id, position=await self.stages.max_position(pipeline.id) + 1))
        await self.audit.record("pipeline_stage.create", actor=actor, entity_type="pipeline", entity_id=pipeline.id,
                                changes={"stage": stage.name})
        await self.session.commit()
        return StageOut.model_validate(stage)

    async def update_stage(self, pipeline_id: int, stage_id: int, data: StageUpdate, actor) -> StageOut:
        pipeline = await self._get_pipeline(pipeline_id)
        stage = await self._stage(stage_id)
        if stage.pipeline_id != pipeline.id:
            raise NotFoundError("Stage not found")
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and not changes["name"]:
            raise ValidationFailedError("A stage needs a name")
        won, lost = changes.get("is_won", stage.is_won), changes.get("is_lost", stage.is_lost)
        self._check_stage_flags(won, lost)
        before = _stage_snapshot(stage)
        self.stages.apply(stage, changes)
        await self.audit.record("pipeline_stage.update", actor=actor, entity_type="pipeline", entity_id=pipeline.id,
                                changes=diff(before, _stage_snapshot(stage)) | {"stage_id": stage.id})
        await self.session.commit()
        return StageOut.model_validate(stage)

    async def delete_stage(self, pipeline_id: int, stage_id: int, actor) -> None:
        pipeline = await self._get_pipeline(pipeline_id)
        stage = await self._stage(stage_id)
        if stage.pipeline_id != pipeline.id:
            raise NotFoundError("Stage not found")
        if await self.repo.count_in_stage(stage.id, status="open"):
            raise ValidationFailedError("Move the deals on this stage to another stage first")
        await self.audit.record("pipeline_stage.delete", actor=actor, entity_type="pipeline", entity_id=pipeline.id,
                                changes={"stage": stage.name})
        await self.stages.hard_delete(stage)
        await self.session.commit()

    @staticmethod
    def _check_stage_flags(is_won: bool, is_lost: bool) -> None:
        if is_won and is_lost:
            raise ValidationFailedError("A stage can't be both the won and the lost column")
