"""Domain event bus: subscription, subclass dispatch, ordering, no duplicate handlers."""

import asyncio
import unittest
from dataclasses import dataclass

from app.core.events import DomainEvent, EventBus


@dataclass(frozen=True, kw_only=True)
class Thing(DomainEvent):
    thing_id: int


@dataclass(frozen=True, kw_only=True)
class SpecialThing(Thing):
    pass


class EventBusTests(unittest.TestCase):
    def test_publish_calls_handlers_in_order_with_session(self):
        bus, calls = EventBus(), []

        async def first(event, session):
            calls.append(("first", event.thing_id, session))

        @bus.handler(Thing)
        async def second(event, session):
            calls.append(("second", event.thing_id, session))

        bus.subscribe(Thing, first)
        bus.subscribe(Thing, first)  # ignored: already subscribed
        asyncio.run(bus.publish(Thing(thing_id=7), "S"))
        self.assertEqual(calls, [("second", 7, "S"), ("first", 7, "S")])

    def test_subclass_events_reach_parent_handlers(self):
        bus, seen = EventBus(), []

        async def on_thing(event, _):
            seen.append(event.name)

        bus.subscribe(Thing, on_thing)
        asyncio.run(bus.publish(SpecialThing(thing_id=1)))
        self.assertEqual(seen, ["SpecialThing"])

    def test_unrelated_events_are_ignored(self):
        bus, seen = EventBus(), []

        async def on_special(event, _):
            seen.append(event)

        bus.subscribe(SpecialThing, on_special)
        asyncio.run(bus.publish(Thing(thing_id=1)))
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
