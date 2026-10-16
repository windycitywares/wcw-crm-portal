"""Staff users, sign-in and roles (SPEC §2, §3.1). `deps.py` provides CurrentUser / require() to every module."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="users", router=router, models="app.modules.users.models")
