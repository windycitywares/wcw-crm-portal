"""Contacts: every person the business deals with (staff, customers, vendors, leads)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="contacts", router=router, models="app.modules.contacts.models")
