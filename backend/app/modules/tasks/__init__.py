"""Tasks (SPEC §3.4): the team's to-dos, about any record, with reminders and repeats."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from .service import register

    register()


async def _reminders(session):
    from .service import TaskService

    return await TaskService(session).send_reminders()


module = CrmModule(name="tasks", router=router, models="app.modules.tasks.models", on_startup=(_register,),
                   jobs=(("task-reminders", _reminders),))
