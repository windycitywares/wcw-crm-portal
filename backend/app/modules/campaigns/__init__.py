"""Campaigns (SPEC §3.6): the email templates campaigns are written from, and the suppression list.

This batch is the module's foundation — templates (with merge fields, preview and test send) and the
suppression list. Target lists, the campaigns themselves, sending and tracking come next.
"""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="campaigns", router=router, models="app.modules.campaigns.models")
