"""Tags shared by every record type (SPEC §3.1)."""

from app.modules import CrmModule

from .router import router


def _subscribe() -> None:
    from app.core.entities import RecordsMerged
    from app.core.events import bus

    from .merge import move_to_survivor

    bus.subscribe(RecordsMerged, move_to_survivor)


module = CrmModule(name="tags", router=router, models="app.modules.tags.models", on_startup=(_subscribe,))
