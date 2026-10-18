"""The mailboxes the CRM reads, and the mail that arrives on them (SPEC §3.9, the unified inbox)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="inbox", router=router, models="app.modules.inbox.models")
