"""Customers (SPEC §3.2): people Windy City Wares sells to, fed later by the shop integration."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from .service import register

    register()


module = CrmModule(name="customers", router=router, models="app.modules.customers.models", on_startup=(_register,))
