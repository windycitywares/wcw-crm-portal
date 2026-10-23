"""The shop numbers its events "shop-<outbox id>", so early ones are short ("shop-5") and must still be accepted."""

import unittest

from pydantic import ValidationError

from app.integrations.shop.schemas import Envelope


class EnvelopeTests(unittest.TestCase):
    def test_short_event_ids_are_valid(self):
        for event_id in ("shop-5", "shop-42", "shop-123456"):
            self.assertEqual(Envelope.model_validate({"id": event_id, "type": "newsletter.subscribed", "data": {}}).id, event_id)

    def test_empty_or_oversized_ids_are_not(self):
        for event_id in ("", "x" * 65):
            with self.assertRaises(ValidationError):
                Envelope.model_validate({"id": event_id, "type": "newsletter.subscribed", "data": {}})


if __name__ == "__main__":
    unittest.main()
