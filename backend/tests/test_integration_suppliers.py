"""Suppliers: directory CRUD, contacts, lookup validation and shared-record registration."""

import unittest
from pydantic import ValidationError

from app.modules.suppliers.schemas import SupplierIn
from tests.support import API, World, reset_limits, run, skip_unless_db


class SupplierSchemaTests(unittest.TestCase):
    def test_supplier_and_contact_fields_are_normalized(self):
        data = SupplierIn.model_validate({
            "name": "  North   Star  ",
            "supplier_type": " manufacturer ",
            "address": {"city": " Chicago ", "country": "US"},
            "contacts": [{"name": " Dana Reed ", "email": "dana@example.com", "is_primary": True}],
        })
        self.assertEqual(data.name, "North Star")
        self.assertEqual(data.supplier_type, "manufacturer")
        self.assertEqual(data.contacts[0].name, "Dana Reed")
        self.assertTrue(data.contacts[0].is_primary)

    def test_rating_currency_and_contact_email_are_validated(self):
        base = {"name": "North Star", "supplier_type": "manufacturer"}
        with self.assertRaises(ValidationError):
            SupplierIn.model_validate({**base, "rating": 6})
        with self.assertRaises(ValidationError):
            SupplierIn.model_validate({**base, "currency": "US"})
        with self.assertRaises(ValidationError):
            SupplierIn.model_validate({**base, "contacts": [{"name": "Dana", "email": "not-email"}]})


@skip_unless_db
class SupplierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda session: LookupService(session).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.read_only, cls.read_only_h = cls.w.user_with_token("read_only")
        values = run(lambda session: LookupService(session).values("supplier_type"))
        cls.supplier_type = values[0].key

    def setUp(self):
        reset_limits()

    def supplier(self, **data):
        payload = {"name": self.w.email("supplier"), "supplier_type": self.supplier_type, **data}
        response = self.w.client.post(f"{API}/suppliers", headers=self.manager_h, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_supplier_contacts_timeline_and_lifecycle(self):
        made = self.supplier(
            address={"city": "Chicago", "country": "US"},
            website="https://example.com",
            payment_terms="Net 30",
            lead_time_days=14,
            currency="usd",
            rating=4,
            contacts=[{"name": "Dana Reed", "email": self.w.email("dana"), "is_primary": True}],
        )
        self.assertEqual(made["currency"], "USD")
        self.assertEqual(made["address"]["city"], "Chicago")
        self.assertEqual(len(made["contacts"]), 1)
        self.assertTrue(made["contacts"][0]["is_primary"])

        timeline = self.w.client.get(f"{API}/entities/supplier/{made['id']}/timeline", headers=self.manager_h)
        self.assertEqual(timeline.status_code, 200, timeline.text)
        self.assertIn("Supplier added", [item["title"] for item in timeline.json()["items"]])

        second = self.w.client.post(
            f"{API}/suppliers/{made['id']}/contacts", headers=self.manager_h,
            json={"name": "Sam Patel", "title": "Purchasing", "is_primary": True},
        )
        self.assertEqual(second.status_code, 201, second.text)
        current = self.w.client.get(f"{API}/suppliers/{made['id']}", headers=self.manager_h).json()
        primary = next(contact for contact in current["contacts"] if contact["is_primary"])
        self.assertEqual(primary["name"], "Sam Patel")
        self.assertEqual(sum(contact["is_primary"] for contact in current["contacts"]), 1)

        updated_contact = self.w.client.patch(
            f"{API}/suppliers/{made['id']}/contacts/{primary['id']}", headers=self.manager_h,
            json={"title": "Operations"},
        )
        self.assertEqual((updated_contact.status_code, updated_contact.json()["title"]), (200, "Operations"))

        updated = self.w.client.patch(
            f"{API}/suppliers/{made['id']}", headers=self.manager_h,
            json={"status": "inactive", "rating": 5, "currency": "eur"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual((updated.json()["status"], updated.json()["rating"], updated.json()["currency"]),
                         ("inactive", 5, "EUR"))
        listed = self.w.client.get(f"{API}/suppliers", headers=self.sales_h,
                                   params={"q": made["name"], "status": "inactive"})
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["id"] for item in listed.json()["items"]], [made["id"]])

        removed = self.w.client.delete(
            f"{API}/suppliers/{made['id']}/contacts/{primary['id']}", headers=self.manager_h)
        self.assertEqual(removed.status_code, 204, removed.text)
        archived = self.w.client.delete(f"{API}/suppliers/{made['id']}", headers=self.manager_h)
        self.assertEqual(archived.status_code, 204, archived.text)
        self.assertEqual(self.w.client.get(f"{API}/suppliers/{made['id']}", headers=self.manager_h).status_code, 404)

    def test_lookup_validation_and_permissions(self):
        forbidden = self.w.client.post(
            f"{API}/suppliers", headers=self.sales_h,
            json={"name": "Blocked Supplier", "supplier_type": self.supplier_type},
        )
        self.assertEqual(forbidden.status_code, 403)
        invalid = self.w.client.post(
            f"{API}/suppliers", headers=self.manager_h,
            json={"name": "Invalid Supplier", "supplier_type": "not-a-real-type"},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(self.w.client.get(f"{API}/suppliers", headers=self.read_only_h).status_code, 200)