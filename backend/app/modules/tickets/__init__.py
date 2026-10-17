"""Support tickets (SPEC §3.5): the customer conversation queue, with SLAs and email replies."""

from app.modules import CrmModule

from .router import router


def _register() -> None:
    from .service import register

    register()


async def _seed(session) -> str:
    """Insert the starter SLA policies (SPEC §9) when the table is empty; never touches edited rows."""
    from .models import SlaPolicy
    from .repository import SlaPolicyRepository
    from .service import SLA_SEED

    if await SlaPolicyRepository(session).count():
        return "SLA policies already set up"
    for name, priority, first_response, resolve in SLA_SEED:
        session.add(SlaPolicy(name=name, priority=priority, ticket_type=None,
                              first_response_minutes=first_response, resolve_minutes=resolve))
    await session.flush()
    return f"{len(SLA_SEED)} SLA policies added"


async def _sla_check(session):
    from .service import TicketService

    return await TicketService(session).check_sla()


module = CrmModule(name="tickets", router=router, models="app.modules.tickets.models",
                   on_startup=(_register,), seed=_seed, jobs=(("ticket-sla", _sla_check),))
