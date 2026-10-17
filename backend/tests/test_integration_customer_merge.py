"""Merging duplicate customers: values, emails, consent, tags, notes, timeline and shop orders move to the survivor."""

import time
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class CustomerMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    def setUp(self):
        reset_limits()

    def create(self, **data):
        res = self.w.client.post(f"{API}/customers", headers=self.manager_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def get(self, cid, **params):
        return self.w.client.get(f"{API}/customers/{cid}", headers=self.manager_h, params=params)

    def test_merge_moves_everything(self):
        keep = self.create(first_name="Kate", last_name="Keep", email=self.w.email("keep"), marketing_consent=True)
        dup_email = self.w.email("dup")
        dup = self.create(first_name="K.", company="Keep Co", phone="312-555-0111", email=dup_email,
                          alt_emails=[self.w.email("dup-alt")], customer_type="vip", address={"city": "Chicago"})
        base = f"{API}/entities/customer"
        self.w.client.put(f"{base}/{keep['id']}/tags", headers=self.manager_h, json={"names": ["a", "b"]})
        self.w.client.put(f"{base}/{dup['id']}/tags", headers=self.manager_h, json={"names": ["b", "c"]})
        note = self.w.client.post(f"{base}/{dup['id']}/notes", headers=self.manager_h, json={"body": "Called about a refund"}).json()

        order_id = int(time.time() * 1000) % 10**9 * 10 + 3

        async def add_order(session):
            from app.integrations.shop.models import ShopOrder

            session.add(ShopOrder(id=order_id, customer_id=dup["id"], number=f"M-{order_id}", email=dup_email,
                                  status="paid", grand_total=Decimal("25.00"), placed_at=datetime.now(timezone.utc)))

        run(add_order)
        # the duplicate unsubscribed: that wins over the kept record's consent
        self.w.client.patch(f"{API}/customers/{dup['id']}", headers=self.manager_h, json={"marketing_consent": True})
        self.w.client.patch(f"{API}/customers/{dup['id']}", headers=self.manager_h, json={"marketing_consent": False})

        self.assertEqual(self.w.client.post(f"{API}/customers/{keep['id']}/merge", headers=self.sales_h,
                                            json={"other_id": dup["id"]}).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/customers/{keep['id']}/merge", headers=self.manager_h,
                                            json={"other_id": keep["id"]}).status_code, 422)

        res = self.w.client.post(f"{API}/customers/{keep['id']}/merge", headers=self.manager_h, json={"other_id": dup["id"]})
        self.assertEqual(res.status_code, 200, res.text)
        k = res.json()
        self.assertEqual((k["first_name"], k["company"], k["phone"], k["customer_type"]), ("Kate", "Keep Co", "312-555-0111", "vip"))
        self.assertEqual(k["address"], {"city": "Chicago"})
        self.assertIn(dup_email, k["alt_emails"])
        self.assertEqual(len(k["alt_emails"]), 2)
        self.assertFalse(k["marketing_consent"])
        self.assertIsNotNone(k["unsubscribed_at"])
        self.assertEqual(sorted(t["name"] for t in k["tags"]), ["a", "b", "c"])
        self.assertEqual((k["orders_count"], float(k["total_spent"])), (1, 25.0))

        notes = self.w.client.get(f"{base}/{keep['id']}/notes", headers=self.manager_h).json()
        self.assertIn(note["id"], [n["id"] for n in notes])
        orders = self.w.client.get(f"{API}/integrations/shop/customers/{keep['id']}/orders", headers=self.manager_h).json()
        self.assertEqual([o["id"] for o in orders], [order_id])
        timeline = self.w.client.get(f"{base}/{keep['id']}/timeline", headers=self.manager_h).json()["items"]
        self.assertTrue(any(a["kind"] == "customer.merged" for a in timeline))

        self.assertEqual(self.get(dup["id"]).status_code, 404)
        gone = self.get(dup["id"], deleted="true").json()
        self.assertIsNotNone(gone["deleted_at"])
        self.assertIsNone(gone["shop_user_id"])
        # the duplicate's email now only lives on the survivor
        self.assertEqual(self.w.client.get(f"{API}/customers/check-email", headers=self.manager_h,
                                           params={"email": dup_email}).json()["exists"], False)

    def test_survivor_without_email_takes_the_duplicates(self):
        keep = self.create(first_name="No", last_name="Email", phone="773-555-0100")
        email = self.w.email("only")
        dup = self.create(first_name="Has", email=email)
        k = self.w.client.post(f"{API}/customers/{keep['id']}/merge", headers=self.manager_h, json={"other_id": dup["id"]}).json()
        self.assertEqual((k["email"], k["alt_emails"], k["first_name"]), (email, [], "No"))


if __name__ == "__main__":
    unittest.main()
