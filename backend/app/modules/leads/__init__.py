"""Leads (SPEC §3.3): the funnel before a customer, and converting one into a customer + deal."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from .service import register

    register()


module = CrmModule(name="leads", router=router, models="app.modules.leads.models", on_startup=(_register,))
