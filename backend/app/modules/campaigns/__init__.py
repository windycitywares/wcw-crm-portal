"""Campaigns (SPEC §3.6): what a campaign is written from, who it goes to, and the send itself — email
templates, audiences (target lists and segments), the suppression list, and the campaigns whose messages are
queued into the email outbox by the `campaigns` job.

The unsubscribe link a customer clicks is public and lives in `public.py`; everything else needs a session.
"""

from app.modules import CrmModule

from .public import router as public_router
from .router import router


def _subscribe() -> None:
    from app.core.entities import RecordsMerged
    from app.core.events import bus

    from .merge import move_to_survivor

    bus.subscribe(RecordsMerged, move_to_survivor)


async def _dispatch(session):
    from .service import CampaignService

    return await CampaignService(session).dispatch_due()


module = CrmModule(name="campaigns", router=router, public_router=public_router,
                   models="app.modules.campaigns.models", on_startup=(_subscribe,),
                   jobs=(("campaigns", _dispatch),))
