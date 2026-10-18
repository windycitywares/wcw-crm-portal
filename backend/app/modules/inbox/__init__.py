"""The mailboxes the CRM reads, and the mail that arrives on them (SPEC §3.9, the unified inbox)."""

from app.modules import CrmModule

from .poller import InboxPoller
from .router import router


async def poll(session) -> str | None:
    """The `inbox` job (once a minute): read every switched-on mailbox into tickets."""
    return await InboxPoller(session).poll()


module = CrmModule(name="inbox", router=router, models="app.modules.inbox.models",
                   jobs=(("inbox", poll),))
