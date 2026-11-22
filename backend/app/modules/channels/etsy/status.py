"""Etsy order statuses and who may move an order between them (pure rules, no database).

Etsy drives new / cancelled / shipped / delivered and only ever moves an order *forward* along the main path, so a team
member who has already marked something further on is never rolled back by a sync. Everything else is set by the team.
"""

NEW, PURCHASED, SHIPPED, DELIVERED, CLOSED = "new", "purchased", "shipped", "delivered", "closed"
CANCELLED, ISSUE, REPLACEMENT, RETURN_REQUESTED, RETURNED, REFUNDED = (
    "cancelled", "issue", "replacement", "return_requested", "returned", "refunded",
)

MAIN_PATH = (NEW, PURCHASED, SHIPPED, DELIVERED, CLOSED)
EXCEPTIONS = (CANCELLED, ISSUE, REPLACEMENT, RETURN_REQUESTED, RETURNED, REFUNDED)
ALL_STATUSES = MAIN_PATH + EXCEPTIONS
OPEN_STATUSES = (NEW, PURCHASED, SHIPPED, ISSUE, REPLACEMENT, RETURN_REQUESTED)

LABELS = {
    NEW: "New (paid)", PURCHASED: "Purchased", SHIPPED: "Shipped", DELIVERED: "Delivered", CLOSED: "Closed",
    CANCELLED: "Cancelled", ISSUE: "Issue reported", REPLACEMENT: "Replacement sent",
    RETURN_REQUESTED: "Return requested", RETURNED: "Returned", REFUNDED: "Refunded",
}

# What Etsy may set, by the facts it reports.
ETSY_DRIVEN = frozenset({NEW, CANCELLED, SHIPPED, DELIVERED})


def is_valid(status: str) -> bool:
    return status in ALL_STATUSES


def etsy_status(*, canceled: bool, shipped: bool, delivered: bool) -> str:
    """The status Etsy's own facts imply."""
    if canceled:
        return CANCELLED
    if delivered:
        return DELIVERED
    if shipped:
        return SHIPPED
    return NEW


def sync_target(current: str, implied: str) -> str:
    """The status after a sync: Etsy may cancel, and may move an order forward on the main path, never back."""
    if current == implied:
        return current
    if implied == CANCELLED:
        return CANCELLED if current not in (CLOSED, REFUNDED, RETURNED) else current
    if current in MAIN_PATH and implied in MAIN_PATH:
        return implied if MAIN_PATH.index(implied) > MAIN_PATH.index(current) else current
    return current  # the team parked it on an exception status: leave it


def can_set_by_team(current: str, target: str) -> bool:
    """The team may set any known status other than the one it is already in. History keeps the trail."""
    return is_valid(target) and target != current
