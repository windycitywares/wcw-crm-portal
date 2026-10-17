"""Supplier directory and its business records (SPEC §3.7)."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
	from .service import register

	register()


module = CrmModule(name="suppliers", router=router, models="app.modules.suppliers.models", on_startup=(_register,))