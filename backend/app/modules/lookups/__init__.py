"""Admin-editable type lists: customer/supplier/ticket/task types, priorities, lead sources … (SPEC §3.1, §9)."""

from app.modules import CrmModule

from .router import router


async def _seed(session) -> str:
    from .service import LookupService

    return await LookupService(session).seed()


module = CrmModule(name="lookups", router=router, models="app.modules.lookups.models", seed=_seed)
