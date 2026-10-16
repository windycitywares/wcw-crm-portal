"""In-process domain event bus.

Modules talk to each other through events instead of importing each other's internals
(e.g. tickets publishes `TicketResolved`; the timeline module subscribes and records it).

    @dataclass(frozen=True)
    class CustomerCreated(DomainEvent):
        customer_id: int

    bus.subscribe(CustomerCreated, handler)      # handler: async (event, session) -> None
    await bus.publish(CustomerCreated(42), session)

Handlers run in the publisher's transaction (same session), in subscription order, so a failing
handler rolls the whole change back. Anything slow or external (emails, webhooks) belongs in an
outbox table processed by a worker, not in a handler.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar

E = TypeVar("E", bound="DomainEvent")
Handler = Callable[[Any, Any], Awaitable[None]]


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: int | None = None

    @property
    def name(self) -> str:
        return type(self).__name__


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Handler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def handler(self, event_type: type[E]) -> Callable[[Handler], Handler]:
        """Decorator form of `subscribe`."""

        def _register(fn: Handler) -> Handler:
            self.subscribe(event_type, fn)
            return fn

        return _register

    async def publish(self, event: DomainEvent, session: Any = None) -> None:
        for event_type, handlers in list(self._handlers.items()):
            if isinstance(event, event_type):
                for fn in list(handlers):
                    await fn(event, session)

    def clear(self) -> None:
        self._handlers.clear()


bus = EventBus()
