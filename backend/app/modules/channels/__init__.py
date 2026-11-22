"""Sales channels — the external shops the business sells on (Etsy; Amazon and Walmart later).

The marketplace's listings and orders live here, worked by the team (costs, supplier, fulfilment), with the
supplier a Supplier account. Only official marketplace APIs are used. Buyer details are kept for fulfilment only.
"""

from app.modules import CrmModule

from .public import router as public_router
from .router import router

module = CrmModule(name="channels", router=router, public_router=public_router, models="app.modules.channels.models")
