"""Urns: what the business buys from suppliers and sells on Etsy — sizes, SKUs, supplier prices and extra costs."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from app.modules.settings.groups import register_group

    from .service import SkuSettings

    register_group("sku", "SKU format", SkuSettings)


module = CrmModule(name="urns", router=router, models="app.modules.urns.models", on_startup=(_register,))
