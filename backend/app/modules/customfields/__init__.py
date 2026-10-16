"""Admin-defined custom fields per record type; values are validated into each record's `custom_fields` JSONB."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="customfields", router=router, models="app.modules.customfields.models")
