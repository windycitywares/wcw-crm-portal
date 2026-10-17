"""Who a campaign may email (SPEC §3.6): has an address, agreed to marketing email, has not unsubscribed, and
is not on the suppression list.

The rule lives in one place on purpose. The audience counts, a segment's query and (next batch) the sender
all have to agree on it, and a customer who said no must never be counted, listed as reachable, or sent to.

The conditions are written against `Customer`, so they only work in a query whose FROM includes the customers
table (or a join to it).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from app.modules.customers.models import Customer

from .models import Suppression


def conditions() -> list[ColumnElement[bool]]:
    """`*consent.conditions()` in a `.where(...)` narrows a customer query to the ones we may email."""
    suppressed = (select(Suppression.id)
                  .where(Suppression.deleted_at.is_(None),
                         func.lower(Suppression.email) == func.lower(Customer.email)).exists())
    return [
        Customer.email.is_not(None),
        Customer.marketing_consent.is_(True),
        Customer.unsubscribed_at.is_(None),
        ~suppressed,
    ]
