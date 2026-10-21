"""Admin → Settings: typed groups (email/SMTP, business hours …) with encrypted secrets (SPEC §9)."""

from app.modules import CrmModule

from .public import router as public_router
from .router import router

module = CrmModule(name="settings", router=router, public_router=public_router, models="app.modules.settings.models")
