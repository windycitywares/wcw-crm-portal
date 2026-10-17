"""Read-only cross-module reports (SPEC §3.8)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="reports", router=router)