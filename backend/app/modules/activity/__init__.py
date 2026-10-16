"""Notes and the activity timeline for every record type (SPEC §3.1)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="activity", router=router, models="app.modules.activity.models")
