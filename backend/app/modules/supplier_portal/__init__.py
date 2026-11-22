"""The supplier portal: an outside supplier signs in (role "supplier") and sees only the marketplace orders whose
supplier is their Supplier account, on the channels they are allowed — what to make and ship, where to, by when,
and what they are owed. Never revenue, profit, other suppliers or the buyer's email and phone."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="supplier_portal", router=router, models="app.modules.supplier_portal.models")
