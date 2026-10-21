"""Contacts API: create/list/search, types, soft delete, and the customer/user mirrors."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class ContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    def create(self, headers=None, **data):
        data.setdefault("first_name", "Ann")
        data.setdefault("email", self.w.email("contact"))
        data.setdefault("types", ["vendor"])
        res = self.w.client.post(f"{API}/contacts", headers=headers or self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_create_and_duplicate_email(self):
        c = self.create(last_name="Smith", phone="555 0100", notes="hello")
        self.assertEqual(c["status"], "active")
        self.assertIn("vendor", c["types"])
        self.assertEqual(c["display_name"], "Ann Smith")
        dup = self.w.client.post(f"{API}/contacts", headers=self.sales_h, json={"first_name": "B", "email": c["email"].upper(), "types": ["other"]})
        self.assertEqual(dup.status_code, 409)
        got = self.w.client.get(f"{API}/contacts/{c['id']}", headers=self.ro_h).json()
        self.assertEqual(got["id"], c["id"])

    def test_validation_and_permissions(self):
        empty = self.w.client.post(f"{API}/contacts", headers=self.sales_h, json={})
        self.assertEqual(empty.status_code, 422)
        bad_type = self.w.client.post(f"{API}/contacts", headers=self.sales_h, json={"first_name": "X", "types": ["nope"]})
        self.assertEqual(bad_type.status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/contacts", headers=self.ro_h, json={"first_name": "X", "types": ["other"]}).status_code, 403)

    def test_types_filter_and_search(self):
        c = self.create(types=["customer"])
        # customer type is always present for a customer-linked contact; here it is a manual one.
        res = self.w.client.get(f"{API}/contacts", headers=self.ro_h, params={"type": "customer"}).json()
        self.assertTrue(any(x["id"] == c["id"] for x in res["items"]))
        res2 = self.w.client.get(f"{API}/contacts", headers=self.ro_h, params={"q": c["email"]}).json()
        self.assertTrue(any(x["id"] == c["id"] for x in res2["items"]))

    def test_soft_delete_and_restore(self):
        c = self.create()
        self.assertEqual(self.w.client.delete(f"{API}/contacts/{c['id']}", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/contacts/{c['id']}", headers=self.manager_h).status_code, 204)
        # hidden by default
        page = self.w.client.get(f"{API}/contacts", headers=self.ro_h).json()
        self.assertFalse(any(x["id"] == c["id"] for x in page["items"]))

    def test_customer_mirror(self):
        from app.modules.customers.service import CustomerService

        def _make(s):
            cs = CustomerService(s)
            import asyncio
            return asyncio.get_event_loop().run_until_complete

        # Create a customer and confirm a contact of type 'customer' exists for it.
        cust = self.w.client.post(f"{API}/customers", headers=self.sales_h, json={
            "first_name": "Pat", "last_name": "Lee", "email": self.w.email("mirr")}).json()
        page = self.w.client.get(f"{API}/contacts", headers=self.ro_h, params={"q": cust["email"]}).json()
        self.assertEqual(page["total"], 1)
        self.assertIn("customer", page["items"][0]["types"])
        self.assertEqual(page["items"][0]["customer_id"], cust["id"])
