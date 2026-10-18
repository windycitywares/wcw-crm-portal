"""Files kept against any record type — what a customer sent with their message (SPEC §4.2)."""

from app.modules import CrmModule

from .router import router


def _subscribe() -> None:
    from app.core.entities import RecordsMerged
    from app.core.events import bus

    from .merge import move_to_survivor

    bus.subscribe(RecordsMerged, move_to_survivor)


module = CrmModule(name="attachments", router=router, models="app.modules.attachments.models",
                   on_startup=(_subscribe,))
