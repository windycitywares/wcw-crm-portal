"""The Trash: everything deleted in the CRM, restorable until it is emptied automatically after N days."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from app.modules.settings.groups import register_group

    from .catalog import register
    from .service import TrashSettings

    register_group("trash", "Trash", TrashSettings)
    register()


async def _empty(session):
    from .service import TrashService

    return await TrashService(session).empty_expired()


module = CrmModule(name="trash", router=router, on_startup=(_register,), jobs=(("trash", _empty),))
