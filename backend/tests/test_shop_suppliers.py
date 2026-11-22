"""What the shop gets for a CRM supplier (pure rule, no database)."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from app.integrations.shop.suppliers import supplier_payload


class SupplierPayloadTests(unittest.TestCase):
    def test_active_supplier_with_a_contact(self):
        s = NS(id=7, name="Acme", status="active", deleted_at=None)
        c = NS(name="Ann", email="ann@acme.test", phone="555")
        self.assertEqual(supplier_payload(s, c), {"crm_id": 7, "name": "Acme", "is_active": True, "contact_name": "Ann",
                                                  "email": "ann@acme.test", "phone": "555"})

    def test_inactive_or_archived_switches_off_in_the_shop(self):
        self.assertFalse(supplier_payload(NS(id=1, name="A", status="inactive", deleted_at=None), None)["is_active"])
        self.assertFalse(supplier_payload(NS(id=1, name="A", status="active", deleted_at=datetime.now(timezone.utc)), None)["is_active"])
        self.assertIsNone(supplier_payload(NS(id=1, name="A", status="active", deleted_at=None), None)["email"])


if __name__ == "__main__":
    unittest.main()
