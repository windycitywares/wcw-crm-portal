"""The Subscribers view of contacts: status tabs, counts, pause / unsubscribe / remove, add by hand, CSV."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


class SubscriberPureTests(unittest.TestCase):
    def test_csv_cells_cannot_run_as_formulas(self):
        from app.modules.contacts.subscribers import _cell

        self.assertEqual(_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(_cell("+1"), "'+1")
        self.assertEqual(_cell(None), "")
        self.assertEqual(_cell("plain"), "plain")

    def test_status_precedence(self):
        from datetime import datetime, timezone

        from app.modules.contacts.models import Contact

        now = datetime.now(timezone.utc)
        c = Contact(email="a@example.com")
        self.assertIsNone(c.subscription_status)
        c.subscribed_at = now
        self.assertEqual(c.subscription_status, "subscribed")
        c.paused_at = now
        self.assertEqual(c.subscription_status, "paused")
        c.unsubscribed_at = now  # leaving wins over a pause
        self.assertEqual(c.subscription_status, "unsubscribed")


@skip_unless_db
class SubscriberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")

    def setUp(self):
        reset_limits()

    def add(self, **data):
        data.setdefault("email", self.w.email("sub"))
        res = self.w.client.post(f"{API}/contacts/subscribers", headers=self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def act(self, sid, action, headers=None):
        return self.w.client.post(f"{API}/contacts/subscribers/{sid}/{action}", headers=headers or self.sales_h)

    def listing(self, **params):
        res = self.w.client.get(f"{API}/contacts/subscribers", headers=self.marketing_h, params={"page_size": 100, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def test_add_pause_resume_unsubscribe_resubscribe_remove(self):
        s = self.add(first_name="Pat", language="en")
        self.assertEqual((s["subscription_status"], s["subscribe_source"], s["types"]), ("subscribed", "manual", ["subscriber"]))
        self.assertEqual(s["first_name"], "Pat")
        sid = s["id"]

        self.assertEqual(self.act(sid, "resume").status_code, 422)  # not paused yet
        paused = self.act(sid, "pause")
        self.assertEqual(paused.status_code, 200, paused.text)
        self.assertEqual(paused.json()["subscription_status"], "paused")
        self.assertEqual(self.act(sid, "pause").status_code, 422)
        # paused people are not "subscribed" in the plain contact filter either
        plain = self.w.client.get(f"{API}/contacts", headers=self.sales_h, params={"subscription": "subscribed", "q": s["email"]}).json()
        self.assertEqual(plain["items"], [])

        self.assertEqual(self.act(sid, "resume").json()["subscription_status"], "subscribed")
        gone = self.act(sid, "unsubscribe").json()
        self.assertEqual(gone["subscription_status"], "unsubscribed")
        self.assertIsNone(gone["paused_at"])
        self.assertEqual(self.act(sid, "resubscribe").json()["subscription_status"], "subscribed")

        res = self.w.client.delete(f"{API}/contacts/subscribers/{sid}", headers=self.sales_h)
        self.assertEqual(res.status_code, 204)
        contact = self.w.client.get(f"{API}/contacts/{sid}", headers=self.sales_h).json()
        self.assertEqual(contact["types"], ["other"])  # the person stays, off the list
        self.assertIsNone(contact["subscription_status"])
        self.assertEqual(self.act(sid, "pause").status_code, 404)  # no longer a subscriber

    def test_tabs_counts_search_and_source(self):
        a, b, c = (self.add(email=self.w.email("tabs")) for _ in range(3))
        term = f"tabs-{self.w.sfx}"
        self.act(b["id"], "pause")
        self.act(c["id"], "unsubscribe")
        everyone = self.listing(q=term)
        self.assertEqual(everyone["counts"], {"subscribed": 1, "paused": 1, "unsubscribed": 1, "all": 3})
        self.assertEqual([i["id"] for i in self.listing(q=term, status="paused")["items"]], [b["id"]])
        self.assertEqual([i["id"] for i in self.listing(q=term, status="unsubscribed")["items"]], [c["id"]])
        self.assertIn("manual", everyone["sources"])
        self.assertEqual(len(self.listing(q=term, source="manual")["items"]), 3)
        self.assertEqual(self.listing(q=term, source="checkout")["items"], [])
        self.assertTrue(a["id"])

    def test_existing_contact_is_added_once_and_shop_signups_appear(self):
        made = self.w.client.post(f"{API}/contacts", headers=self.sales_h,
                                  json={"first_name": "Vic", "email": self.w.email("vendor"), "types": ["vendor"]}).json()
        s = self.add(email=made["email"])
        self.assertEqual(s["id"], made["id"])
        self.assertEqual(sorted(s["types"]), ["subscriber", "vendor"])

        email = self.w.email("shopsub")

        async def signup(session):
            from app.modules.contacts.service import ContactService

            await ContactService(session).sync_subscriber(email, subscribed=True, source="checkout", language="es")

        run(signup)
        hit = [i for i in self.listing(q=email)["items"] if i["email"] == email]
        self.assertEqual((hit[0]["subscribe_source"], hit[0]["language"], hit[0]["source"]), ("checkout", "es", "shop"))

    def test_permissions_and_csv(self):
        email = self.w.email("csv")
        self.add(email=email, first_name="=cmd")
        # marketing may look but not change
        denied = self.w.client.post(f"{API}/contacts/subscribers", headers=self.marketing_h, json={"email": self.w.email("no")})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/contacts/subscribers").status_code, 401)
        res = self.w.client.get(f"{API}/contacts/subscribers/export.csv", headers=self.marketing_h, params={"q": email})
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers["content-type"])
        self.assertIn(email, res.text)
        self.assertIn("'=cmd", res.text)
        self.assertNotIn(",=cmd", res.text)


if __name__ == "__main__":
    unittest.main()
