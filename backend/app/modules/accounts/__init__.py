"""Accounts: the organisations the business deals with — customers' companies, suppliers, partners.

The industry-standard spine: an Account is an organisation, a Contact is a person (optionally at an
account), a Lead converts into a contact + account + deal. `account_type` is a lookup (Settings → Types),
so "Supplier", "Customer", "Partner"… are values an admin can rename or add to.
"""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from .service import register

    register()


module = CrmModule(name="accounts", router=router, models="app.modules.accounts.models", on_startup=(_register,))
