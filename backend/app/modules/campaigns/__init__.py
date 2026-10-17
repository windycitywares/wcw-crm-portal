"""Campaigns (SPEC §3.6): what a campaign is written from and who it goes to — email templates, audiences
(target lists and segments) and the suppression list.

Built so far: templates (merge fields, preview, test send), the suppression list, static target lists and
dynamic segments. Next: the campaigns themselves with the sender, then tracking.
"""

from app.modules import CrmModule

from .router import router


def _subscribe() -> None:
    from app.core.entities import RecordsMerged
    from app.core.events import bus

    from .merge import move_to_survivor

    bus.subscribe(RecordsMerged, move_to_survivor)


module = CrmModule(name="campaigns", router=router, models="app.modules.campaigns.models",
                   on_startup=(_subscribe,))
