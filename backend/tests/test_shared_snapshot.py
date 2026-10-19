"""The shared audit snapshot: what it keeps, and that it stays storable as JSON."""

import json
import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.shared.snapshot import snapshot


class SnapshotTests(unittest.TestCase):
    def test_takes_the_named_fields(self):
        row = SimpleNamespace(title="A deal", value=Decimal("12.50"), owner_id=7)
        self.assertEqual(snapshot(row, ("title", "value")), {"title": "A deal", "value": "12.50"})

    def test_money_and_dates_become_text_the_audit_log_can_store(self):
        """The `changes` column is JSONB: a Decimal or a date would make `json.dumps` raise."""
        row = SimpleNamespace(value=Decimal("100.00"), due_at=datetime(2026, 10, 14, 9, 30),
                              expected_close_on=date(2026, 11, 1), status="open")
        snap = snapshot(row, ("value", "due_at", "expected_close_on", "status"))
        self.assertEqual(snap, {"value": "100.00", "due_at": "2026-10-14T09:30:00",
                                "expected_close_on": "2026-11-01", "status": "open"})
        json.dumps(snap)  # what SQLAlchemy does when it saves it


if __name__ == "__main__":
    unittest.main()
