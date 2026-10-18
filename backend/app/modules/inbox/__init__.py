"""The mailboxes the CRM reads, and the mail that arrives on them (SPEC §3.9, the unified inbox).

Mailboxes are set up and read here; the channels that aren't mailboxes — live chat, Etsy, SMS — post
their messages to the public route in `public.py`, and both kinds of message are filed by `filing.py`.
"""

from app.modules import CrmModule

from .poller import InboxPoller
from .public import router as public_router
from .router import router


def _register_settings() -> None:
    from app.modules.settings.groups import register_group

    from .settings import SECRETS, InboxSettings

    register_group("inbox", "Inbox channels", InboxSettings, SECRETS)


async def poll(session) -> str | None:
    """The `inbox` job (once a minute): read every switched-on mailbox into tickets."""
    return await InboxPoller(session).poll()


module = CrmModule(name="inbox", router=router, public_router=public_router,
                   models="app.modules.inbox.models", on_startup=(_register_settings,),
                   jobs=(("inbox", poll),))
