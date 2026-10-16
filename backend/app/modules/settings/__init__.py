"""Admin → Settings: typed groups (email/SMTP, business hours …) with encrypted secrets (SPEC §9)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="settings", router=router, models="app.modules.settings.models")
