"""Tags shared by every record type (SPEC §3.1)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="tags", router=router, models="app.modules.tags.models")
