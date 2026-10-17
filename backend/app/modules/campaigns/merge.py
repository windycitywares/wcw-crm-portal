"""A merged customer keeps their audiences (SPEC §3.6).

When two customers are merged, the memberships of the record that went away move to the one that stayed;
a list they were both on is not listed twice (the unique (list, customer) pair sees to that).
"""

from sqlalchemy import delete, select, update

from app.core.entities import RecordsMerged

from .models import TargetListMember


async def move_to_survivor(event: RecordsMerged, session) -> None:
    """Merge handler: only customer merges matter here."""
    if event.entity_type != "customer":
        return
    has = select(TargetListMember.list_id).where(TargetListMember.customer_id == event.into_id)
    await session.execute(update(TargetListMember)
                          .where(TargetListMember.customer_id == event.from_id,
                                 TargetListMember.list_id.not_in(has))
                          .values(customer_id=event.into_id))
    await session.execute(delete(TargetListMember).where(TargetListMember.customer_id == event.from_id))
