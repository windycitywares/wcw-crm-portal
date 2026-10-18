"""Shop → CRM webhooks: signatures, idempotency, customer matching, order totals, consent, admin views."""

import json
import time
import unittest
import uuid

from tests.support import API, World, reset_limits, run, skip_unless_db

SECRET = "x" * 48
HOOK = f"{API}/integrations/shop/webhook"


@skip_unless_db
class ShopWebhookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        res = cls.w.client.put(f"{API}/settings/shop", headers=cls.admin_h,
                               json={"enabled": True, "webhook_secret": SECRET})
        assert res.status_code == 200, res.text
        cls.shop_ids = iter(range(int(time.time() * 1000) % 10**9 * 10, 10**12))

    def setUp(self):
        reset_limits()

    def send(self, type_, data, *, event_id=None, secret=SECRET, ts=None):
        from app.integrations.shop.signing import sign

        body = json.dumps({"id": event_id or uuid.uuid4().hex, "type": type_,
                           "occurred_at": "2026-10-16T12:00:00Z", "data": data}).encode()
        ts = ts or int(time.time())
        return self.w.client.post(HOOK, content=body, headers={
            "content-type": "application/json", "x-wcw-timestamp": str(ts), "x-wcw-signature": sign(secret, ts, body)})

    def customer(self, customer_id):
        res = self.w.client.get(f"{API}/customers/{customer_id}", headers=self.admin_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def find(self, email):
        res = self.w.client.get(f"{API}/customers/check-email", headers=self.admin_h, params={"email": email}).json()
        return res["customer_id"]

    def test_signature_required(self):
        bad = self.send("customer.upserted", {"id": 1, "email": self.w.email("x")}, secret="y" * 48)
        self.assertEqual(bad.status_code, 401)
        old = self.send("customer.upserted", {"id": 1, "email": self.w.email("x")}, ts=int(time.time()) - 3600)
        self.assertEqual(old.status_code, 401)
        unsigned = self.w.client.post(HOOK, content=b"{}", headers={"content-type": "application/json"})
        self.assertEqual(unsigned.status_code, 401)

    def test_customer_created_then_linked_and_duplicate_ignored(self):
        shop_id, email = next(self.shop_ids), self.w.email("shopper")
        evt = uuid.uuid4().hex
        res = self.send("customer.upserted", {"id": shop_id, "email": email.upper(), "full_name": "Jane Q Doe"}, event_id=evt)
        self.assertEqual(res.json(), {"status": "accepted"})
        again = self.send("customer.upserted", {"id": shop_id, "email": email}, event_id=evt)
        self.assertEqual(again.json(), {"status": "duplicate"})
        c = self.customer(self.find(email))
        self.assertEqual((c["first_name"], c["last_name"], c["shop_user_id"], c["source"]), ("Jane", "Q Doe", shop_id, "shop"))

        # staff edits win; a changed shop email becomes the primary and the old one is kept
        self.w.client.patch(f"{API}/customers/{c['id']}", headers=self.admin_h, json={"first_name": "Janet"})
        new_email = self.w.email("shopper-new")
        self.send("customer.upserted", {"id": shop_id, "email": new_email, "full_name": "Someone Else", "phone": "312-555-0100"})
        c = self.customer(c["id"])
        self.assertEqual((c["first_name"], c["email"], c["phone"]), ("Janet", new_email, "312-555-0100"))
        self.assertIn(email, c["alt_emails"])

    def test_existing_customer_matched_by_email(self):
        email = self.w.email("known")
        made = self.w.client.post(f"{API}/customers", headers=self.sales_h, json={"first_name": "Kim", "email": email}).json()
        self.send("customer.upserted", {"id": next(self.shop_ids), "email": email, "full_name": "Kimberly Lee"})
        c = self.customer(made["id"])
        self.assertEqual(c["first_name"], "Kim")
        self.assertIsNotNone(c["shop_user_id"])

    def order(self, order_id, email, status, total="50.00", **extra):
        data = {"id": order_id, "number": f"WCW-{order_id}", "email": email, "customer_name": "Olive Order",
                "status": status, "payment_status": "paid" if status != "pending" else "unpaid",
                "grand_total": total, "placed_at": "2026-10-01T10:00:00Z", **extra}
        return self.send("order.updated", data)

    def test_orders_update_totals_timeline_and_consent(self):
        email = self.w.email("buyer")
        base = next(self.shop_ids)
        self.order(base, email, "pending", updated_at="2026-10-01T10:00:00Z")
        cid = self.find(email)
        self.assertEqual(self.customer(cid)["orders_count"], 0)  # pending orders don't count

        self.order(base, email, "paid", updated_at="2026-10-01T10:05:00Z", marketing_opt_in=True,
                   billing_address={"line1": "1 Main St", "city": "Chicago", "region": "IL", "postal_code": "60601", "country": "US"})
        self.order(base + 1, email, "shipped", total="20.50", placed_at="2026-10-05T10:00:00Z", updated_at="2026-10-05T10:00:00Z")
        # a late, older copy of the first order changes nothing
        self.order(base, email, "pending", updated_at="2026-10-01T09:00:00Z")
        c = self.customer(cid)
        self.assertEqual(c["orders_count"], 2)
        self.assertEqual(float(c["total_spent"]), 70.5)
        self.assertTrue(c["last_order_at"].startswith("2026-10-05"))
        self.assertTrue(c["marketing_consent"])
        self.assertEqual(c["consent_source"], "shop checkout")
        self.assertEqual(c["address"]["state"], "IL")

        self.order(base + 1, email, "refunded", total="20.50", refunded_total="20.50", updated_at="2026-10-06T10:00:00Z")
        self.assertEqual(float(self.customer(cid)["total_spent"]), 50.0)

        timeline = self.w.client.get(f"{API}/entities/customer/{cid}/timeline", headers=self.admin_h).json()["items"]
        titles = [a["title"] for a in timeline]
        self.assertIn(f"Order WCW-{base} paid — $50.00", titles)
        self.assertIn(f"Order WCW-{base + 1} refunded", titles)

    def test_newsletter(self):
        email = self.w.email("news")
        self.send("newsletter.unsubscribed", {"email": email})  # unknown address: nothing created
        self.assertIsNone(self.find(email))
        self.send("newsletter.subscribed", {"email": email, "source": "site"})
        c = self.customer(self.find(email))
        self.assertTrue(c["marketing_consent"])
        self.assertEqual(c["consent_source"], "shop newsletter, site")
        self.send("newsletter.unsubscribed", {"email": email})
        c = self.customer(c["id"])
        self.assertFalse(c["marketing_consent"])
        self.assertIsNotNone(c["unsubscribed_at"])

    def test_contact_message_opens_a_ticket(self):
        email = self.w.email("asker")
        base = next(self.shop_ids)
        self.order(base, email, "paid", updated_at="2026-10-10T10:00:00Z")
        res = self.send("contact_message.created", {
            "name": "Pan Da", "email": email, "phone": "312-555-0199",
            "subject": "Where is my order?", "message": "It has not arrived yet, please check.",
            "order_number": f"WCW-{base}"})
        self.assertEqual(res.json(), {"status": "accepted"})

        cid = self.find(email)
        self.assertIsNotNone(cid)  # a contact form from an unknown address creates the customer
        tickets = self.w.client.get(f"{API}/tickets", headers=self.admin_h, params={"customer_id": cid}).json()
        self.assertEqual(tickets["total"], 1)
        t = tickets["items"][0]
        self.assertEqual((t["subject"], t["status"], t["ticket_type"], t["priority"], t["channel"]),
                         ("Where is my order?", "new", "other", "normal", "shop_form"))
        self.assertIsNone(t["assignee_id"])  # the shop can't assign: it lands unassigned
        self.assertEqual(t["shop_order_id"], base)  # the order the customer quoted is linked
        self.assertIn("not arrived", t["description"])
        self.assertIsNotNone(t["first_response_due_at"])  # SLA taken from the seeded Normal policy
        timeline = self.w.client.get(f"{API}/entities/customer/{cid}/timeline", headers=self.admin_h).json()["items"]
        self.assertTrue(any(a["kind"] == "ticket.created" for a in timeline))

        # a message with no subject is named after its text; one that quotes no order links nothing
        email2 = self.w.email("asker2")
        self.send("contact_message.created", {"email": email2, "message": "Do you ship to Canada?"})
        t2 = self.w.client.get(f"{API}/tickets", headers=self.admin_h,
                               params={"customer_id": self.find(email2)}).json()["items"][0]
        self.assertTrue(t2["subject"].startswith("Shop contact: Do you ship to Canada?"))
        self.assertIsNone(t2["shop_order_id"])

        # with no email there is nobody to reply to: stored, marked failed and not retried
        self.send("contact_message.created", {"message": "hello"})
        failed = self.w.client.get(f"{API}/integrations/shop/events", headers=self.admin_h, params={"status": "failed"}).json()
        self.assertTrue(any(e["event_type"] == "contact_message.created" for e in failed["items"]))

    def test_bad_and_unknown_events_and_admin_views(self):
        unknown = self.send("review.created", {"id": 5})
        self.assertEqual(unknown.status_code, 200)
        bad = self.send("order.updated", {"id": "not-a-number"})
        self.assertEqual(bad.status_code, 200)  # stored; shown as failed in the admin list

        failed = self.w.client.get(f"{API}/integrations/shop/events", headers=self.admin_h, params={"status": "failed"}).json()
        self.assertTrue(any(e["event_type"] == "order.updated" for e in failed["items"]))
        ignored = self.w.client.get(f"{API}/integrations/shop/events", headers=self.admin_h, params={"status": "ignored"}).json()
        self.assertTrue(any(e["event_type"] == "review.created" for e in ignored["items"]))

        status = self.w.client.get(f"{API}/integrations/shop/status", headers=self.admin_h).json()
        self.assertTrue(status["enabled"] and status["secret_set"])
        self.assertTrue(status["webhook_url"].endswith("/api/v1/integrations/shop/webhook"))
        self.assertEqual(self.w.client.get(f"{API}/integrations/shop/status", headers=self.sales_h).status_code, 403)

        settings = self.w.client.get(f"{API}/settings/shop", headers=self.admin_h).json()
        self.assertNotIn("webhook_secret", settings["values"])
        self.assertTrue(settings["values"]["webhook_secret_set"])
        short = self.w.client.put(f"{API}/settings/shop", headers=self.admin_h, json={"webhook_secret": "short"})
        self.assertEqual(short.status_code, 422)


if __name__ == "__main__":
    unittest.main()


class FakeShop:
    """Stands in for the shop's read API: pages of items by id."""

    def __init__(self, data):
        self.data = data

    async def page(self, resource, after_id, limit=200):
        items = [i for i in self.data.get(resource, []) if i["_id"] > after_id][:limit]
        clean = [{k: v for k, v in i.items() if k != "_id"} for i in items]
        return {"items": clean, "next_after_id": items[-1]["_id"] if len(items) == limit else None}


@skip_unless_db
class ShopBackfillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    def tearDown(self):
        from app.integrations.shop.client import set_shop_client_factory

        set_shop_client_factory(None)

    def test_backfill_imports_in_chunks_and_orders_show_on_customer(self):
        from app.integrations.shop.backfill import ShopBackfillService
        from app.integrations.shop.client import set_shop_client_factory

        base = int(time.time() * 1000) % 10**9 * 10 + 7
        email, email2, news = self.w.email("old"), self.w.email("old2"), self.w.email("oldnews")
        shop = FakeShop({
            "customers": [{"_id": n, "id": base + n, "email": e, "full_name": f"Old Customer{n}"} for n, e in ((1, email), (2, email2))]
            + [{"_id": 3, "id": "broken", "email": "x"}],
            "orders": [
                {"_id": 1, "id": base + 1, "number": f"OLD-{base}-1", "user_id": base + 1, "email": email, "status": "delivered",
                 "payment_status": "paid", "grand_total": "30.00", "placed_at": "2025-05-01T10:00:00Z", "updated_at": "2025-05-03T10:00:00Z"},
                {"_id": 2, "id": base + 2, "number": f"OLD-{base}-2", "user_id": None, "email": email, "status": "paid",
                 "payment_status": "paid", "grand_total": "12.00", "placed_at": "2025-06-01T10:00:00Z", "updated_at": "2025-06-01T10:00:00Z"},
            ],
            "newsletter": [{"_id": 1, "type": "newsletter.subscribed", "email": news, "source": "site"}],
        })
        set_shop_client_factory(lambda settings: shop)

        start = self.w.client.post(f"{API}/integrations/shop/backfill", headers=self.admin_h)
        self.assertEqual(start.status_code, 200, start.text)
        self.assertEqual(start.json()["status"], "running")
        self.assertEqual(self.w.client.post(f"{API}/integrations/shop/backfill", headers=self.sales_h).status_code, 403)

        for _ in range(10):
            run(lambda s: ShopBackfillService(s).run_chunk())
            state = self.w.client.get(f"{API}/integrations/shop/backfill", headers=self.admin_h).json()
            if state["status"] != "running":
                break
        self.assertEqual(state["status"], "done", state)
        self.assertEqual(state["counts"], {"customers": 2, "orders": 2, "newsletter": 1, "errors": 1})

        cid = self.w.client.get(f"{API}/customers/check-email", headers=self.admin_h, params={"email": email}).json()["customer_id"]
        c = self.w.client.get(f"{API}/customers/{cid}", headers=self.admin_h).json()
        self.assertEqual((c["orders_count"], float(c["total_spent"]), c["shop_user_id"]), (2, 42.0, base + 1))
        orders = self.w.client.get(f"{API}/integrations/shop/customers/{cid}/orders", headers=self.sales_h).json()
        self.assertEqual([o["number"] for o in orders], [f"OLD-{base}-2", f"OLD-{base}-1"])
        timeline = self.w.client.get(f"{API}/entities/customer/{cid}/timeline", headers=self.admin_h).json()["items"]
        self.assertFalse(any(a["kind"] == "shop.order" for a in timeline))  # history isn't replayed as news
        self.assertIsNotNone(self.w.client.get(f"{API}/customers/check-email", headers=self.admin_h,
                                               params={"email": news}).json()["customer_id"])

        # running it again changes nothing
        self.w.client.post(f"{API}/integrations/shop/backfill", headers=self.admin_h)
        for _ in range(10):
            run(lambda s: ShopBackfillService(s).run_chunk())
        c2 = self.w.client.get(f"{API}/customers/{cid}", headers=self.admin_h).json()
        self.assertEqual((c2["orders_count"], float(c2["total_spent"])), (2, 42.0))

    def test_unreachable_shop(self):
        from app.integrations.shop.client import ShopApiError, set_shop_client_factory

        class Down:
            async def page(self, *a, **k):
                raise ShopApiError("HTTP 401: the shop refused the API token")

        set_shop_client_factory(lambda settings: Down())
        res = self.w.client.post(f"{API}/integrations/shop/backfill", headers=self.admin_h)
        self.assertEqual(res.status_code, 422)
        self.assertIn("refused the API token", res.text)
        test = self.w.client.get(f"{API}/integrations/shop/test", headers=self.admin_h).json()
        self.assertFalse(test["ok"])
