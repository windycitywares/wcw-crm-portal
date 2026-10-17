"""Sales (SPEC §3.3): pipelines and their stages, and the deals that move through them."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from .service import register

    register()


async def _seed(session) -> str:
    """Create the starter board once, when there is no pipeline yet; never touches an edited one."""
    from .models import Pipeline, PipelineStage
    from .repository import PipelineRepository, PipelineStageRepository
    from .service import DEFAULT_PIPELINE, STARTER_STAGES

    if await PipelineRepository(session).count():
        return "pipelines already set up"
    pipeline = await PipelineRepository(session).add(Pipeline(name=DEFAULT_PIPELINE, is_default=True))
    stages = PipelineStageRepository(session)
    for position, (name, probability, is_won, is_lost, color) in enumerate(STARTER_STAGES):
        await stages.add(PipelineStage(pipeline_id=pipeline.id, name=name, position=position,
                                       probability=probability, is_won=is_won, is_lost=is_lost, color=color))
    return f"pipeline '{DEFAULT_PIPELINE}' added with {len(STARTER_STAGES)} stages"


module = CrmModule(name="sales", router=router, models="app.modules.sales.models", on_startup=(_register,),
                   seed=_seed)
