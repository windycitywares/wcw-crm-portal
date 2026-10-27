"""The bell (per-role feed, unread count, mark seen) and live updates (changes since an audit id, by permission)."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class NotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")

    def setUp(self):
        reset_limits()

    def feed(self, headers, **params):
        res = self.w.client.get(f"{API}/notifications", headers=headers, params={"limit": 100, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def test_bell_feed_unread_and_seen(self):
        email = self.w.email("bell-sub")

        async def subscribe(session):
            from app.modules.contacts.service import ContactService

            await ContactService(session).sync_subscriber(email, subscribed=True, source="site")

        run(subscribe)
        task = self.w.client.post(f"{API}/tasks", headers=self.manager_h,
                                  json={"title": f"Call the supplier {self.w.sfx}", "owner_id": self.sales["id"]}).json()
        own = self.w.client.post(f"{API}/tasks", headers=self.sales_h, json={"title": f"My own {self.w.sfx}"}).json()

        f = self.feed(self.sales_h)
        ids = {i["id"]: i for i in f["items"]}
        self.assertIn(f"task:{task['id']}", ids)
        self.assertNotIn(f"task:{own['id']}", ids)  # what you gave yourself isn't news
        item = ids[f"task:{task['id']}"]
        self.assertEqual(item["title"], f"Task for you: Call the supplier {self.w.sfx}")
        self.assertEqual(item["href"], f"/tasks?task={task['id']}")
        self.assertTrue(any(i["type"] == "subscriber" and email in i["detail"] for i in f["items"]))
        self.assertGreater(f["unread"], 0)
        self.assertIn("task", f["kinds"])

        # marketing can't see sales or tickets, so those kinds aren't theirs
        self.assertNotIn("lead", self.feed(self.marketing_h)["kinds"])
        only = self.feed(self.sales_h, kind="subscriber")
        self.assertTrue(all(i["type"] == "subscriber" for i in only["items"]))

        self.assertEqual(self.w.client.post(f"{API}/notifications/seen", headers=self.sales_h).status_code, 204)
        after = self.feed(self.sales_h)
        self.assertEqual(after["unread"], 0)
        self.assertFalse(any(i["unread"] for i in after["items"]))
        self.assertIsNotNone(after["seen_at"])

    def test_live_events_since_and_by_permission(self):
        start = self.w.client.get(f"{API}/live/events", headers=self.sales_h).json()
        self.assertEqual(start["events"], [])
        mark = start["last_id"]
        lead = self.w.client.post(f"{API}/leads", headers=self.sales_h, json={"first_name": f"Live {self.w.sfx}"})
        self.assertEqual(lead.status_code, 201, lead.text)
        lead_id = lead.json()["id"]

        seen = self.w.client.get(f"{API}/live/events", headers=self.manager_h, params={"after_id": mark}).json()
        mine = [e for e in seen["events"] if e["entity_type"] == "lead" and e["ref_id"] == lead_id]
        self.assertEqual([e["kind"] for e in mine], ["lead.create"])
        self.assertEqual(mine[0]["actor_id"], self.sales["id"])
        self.assertGreater(seen["last_id"], mark)

        # marketing has no access to sales: the lead isn't in their stream
        theirs = self.w.client.get(f"{API}/live/events", headers=self.marketing_h, params={"after_id": mark}).json()
        self.assertFalse(any(e["entity_type"] == "lead" for e in theirs["events"]))
        self.assertEqual(self.w.client.get(f"{API}/live/events").status_code, 401)


if __name__ == "__main__":
    unittest.main()
