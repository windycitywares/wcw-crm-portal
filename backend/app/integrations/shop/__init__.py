"""Shop integration (SPEC §6): signed webhooks in from shop.windycitywares.com, settings in
Admin → Settings → Integrations. Event contract: docs/SHOP_EVENTS.md."""

from app.modules import CrmModule

from .router import router


def _register_settings() -> None:
    from app.modules.settings.groups import register_group

    from .settings import SECRETS, ShopSettings

    register_group("shop", "Shop connection", ShopSettings, SECRETS)


async def _retry(session):
    from .service import ShopEventService

    return await ShopEventService(session).retry_due()


async def _backfill(session):
    from .backfill import ShopBackfillService

    return await ShopBackfillService(session).run_chunk()


module = CrmModule(name="shop", router=router, models="app.integrations.shop.models",
                   on_startup=(_register_settings,), jobs=(("shop-events", _retry), ("shop-backfill", _backfill)))
