"""The bell and live updates (no tables of their own: they read what the other modules already record)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="notifications", router=router)
