"""Role-based access control: roles map to a fixed set of permissions.

Routes depend on *permissions*, never on role names (`Depends(require(Permission.X))`), so adding a
role or changing what a role may do is a change in this file only.

Naming: `<area>:<action>`. `*_own` vs `*_any` separates "records I own" from "everyone's records".
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    MARKETING = "marketing"
    READ_ONLY = "read_only"


class Permission(StrEnum):
    # Platform
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"  # email/SMTP, business hours, integrations
    LOOKUPS_MANAGE = "lookups:manage"  # customer/supplier/ticket/task types, pipelines, SLA
    AUDIT_VIEW = "audit:view"
    DATA_EXPORT = "data:export"
    DATA_DELETE = "data:delete"  # GDPR erase, hard delete
    REPORTS_VIEW = "reports:view"

    # Customers
    CUSTOMERS_VIEW = "customers:view"
    CUSTOMERS_EDIT_OWN = "customers:edit_own"
    CUSTOMERS_EDIT_ANY = "customers:edit_any"
    CUSTOMERS_MERGE = "customers:merge"

    # Sales
    SALES_VIEW = "sales:view"
    SALES_EDIT_OWN = "sales:edit_own"
    SALES_EDIT_ANY = "sales:edit_any"

    # Tasks
    TASKS_VIEW = "tasks:view"
    TASKS_EDIT_OWN = "tasks:edit_own"
    TASKS_EDIT_ANY = "tasks:edit_any"
    TASKS_ASSIGN = "tasks:assign"

    # Support tickets
    TICKETS_VIEW = "tickets:view"
    TICKETS_EDIT = "tickets:edit"
    TICKETS_ASSIGN = "tickets:assign"

    # Campaigns
    CAMPAIGNS_VIEW = "campaigns:view"
    CAMPAIGNS_EDIT = "campaigns:edit"  # templates, lists, segments, drafts
    CAMPAIGNS_SEND = "campaigns:send"

    # Suppliers
    SUPPLIERS_VIEW = "suppliers:view"
    SUPPLIERS_EDIT = "suppliers:edit"


P = Permission

_READ = frozenset({
    P.CUSTOMERS_VIEW, P.SALES_VIEW, P.TASKS_VIEW, P.TICKETS_VIEW, P.CAMPAIGNS_VIEW, P.SUPPLIERS_VIEW, P.REPORTS_VIEW,
})

_SALES = frozenset({
    P.CUSTOMERS_VIEW, P.CUSTOMERS_EDIT_OWN,
    P.SALES_VIEW, P.SALES_EDIT_OWN,
    P.TASKS_VIEW, P.TASKS_EDIT_OWN,
    P.TICKETS_VIEW,
    P.SUPPLIERS_VIEW,
})

_SUPPORT = frozenset({
    P.CUSTOMERS_VIEW, P.CUSTOMERS_EDIT_ANY,
    P.TASKS_VIEW, P.TASKS_EDIT_OWN,
    P.TICKETS_VIEW, P.TICKETS_EDIT,
    P.SALES_VIEW,
})

_MARKETING = frozenset({
    P.CUSTOMERS_VIEW,
    P.TASKS_VIEW, P.TASKS_EDIT_OWN,
    P.CAMPAIGNS_VIEW, P.CAMPAIGNS_EDIT, P.CAMPAIGNS_SEND,
    P.REPORTS_VIEW,
})

_MANAGER = _READ | _SALES | _SUPPORT | _MARKETING | frozenset({
    P.CUSTOMERS_EDIT_ANY, P.CUSTOMERS_MERGE,
    P.SALES_EDIT_ANY,
    P.TASKS_EDIT_ANY, P.TASKS_ASSIGN,
    P.TICKETS_ASSIGN,
    P.SUPPLIERS_EDIT,
    P.LOOKUPS_MANAGE,
    P.DATA_EXPORT,
    P.AUDIT_VIEW,
})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.MANAGER: _MANAGER,
    Role.SALES: _SALES,
    Role.SUPPORT: _SUPPORT,
    Role.MARKETING: _MARKETING,
    Role.READ_ONLY: _READ,
}

ROLE_LABELS: dict[Role, str] = {
    Role.ADMIN: "Admin",
    Role.MANAGER: "Manager",
    Role.SALES: "Sales",
    Role.SUPPORT: "Support",
    Role.MARKETING: "Marketing",
    Role.READ_ONLY: "Read-only",
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
