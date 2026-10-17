"""Tasks: own vs any vs assign, record links + timeline, filters, recurrence, reminders, summary."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.support import API, World, reset_limits, run, skip_unless_db


def iso(dt: datetime) -> str:
    return dt.isoformat()


@skip_unless_db
class TaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.sales2, cls.sales2_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    def create(self, headers=None, **data):
        data.setdefault("title", f"Call back {self.w.sfx}")
        res = self.w.client.post(f"{API}/tasks", headers=headers or self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def patch(self, task_id, headers=None, **data):
        return self.w.client.patch(f"{API}/tasks/{task_id}", headers=headers or self.sales_h, json=data)

    def ids(self, headers=None, **params):
        res = self.w.client.get(f"{API}/tasks", headers=headers or self.sales_h, params={"page_size": 200, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return [t["id"] for t in res.json()["items"]]

    def test_permissions_and_assignment(self):
        t = self.create(task_type="call", priority="high")
        self.assertEqual((t["owner_id"], t["status"], t["task_type"]), (self.sales["id"], "open", "call"))
        # sales can't give tasks to others; managers can
        res = self.w.client.post(f"{API}/tasks", headers=self.sales_h, json={"title": "x", "owner_id": self.sales2["id"]})
        self.assertEqual(res.status_code, 403)
        given = self.create(self.manager_h, owner_id=self.sales2["id"], title="For sales2")
        self.assertEqual(given["owner_id"], self.sales2["id"])
        # the assignee and the creator may change it; another salesperson may not
        self.assertEqual(self.patch(given["id"], self.sales2_h, priority="low").status_code, 200)
        self.assertEqual(self.patch(given["id"], self.sales_h, priority="low").status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/tasks", headers=self.ro_h, json={"title": "x"}).status_code, 403)
        self.assertEqual(self.patch(t["id"], task_type="nonsense").status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/tasks", headers=self.sales_h, json={"title": "  "}).status_code, 422)

    def test_related_record_timeline_and_label(self):
        customer = self.w.client.post(f"{API}/customers", headers=self.sales_h,
                                      json={"first_name": "Tia", "last_name": "Task", "email": self.w.email("tia")}).json()
        t = self.create(title="Send samples", related_type="customer", related_id=customer["id"])
        self.assertEqual(t["related_label"], "Tia Task")
        listed = self.ids(self.ro_h, view="team", related_type="customer", related_id=customer["id"])
        self.assertEqual(listed, [t["id"]])
        done = self.patch(t["id"], status="done").json()
        self.assertEqual(done["status"], "done")
        self.assertIsNotNone(done["completed_at"])
        timeline = self.w.client.get(f"{API}/entities/customer/{customer['id']}/timeline", headers=self.sales_h).json()["items"]
        titles = [a["title"] for a in timeline]
        self.assertIn("Task added: Send samples", titles)
        self.assertIn("Task done: Send samples", titles)
        missing = self.w.client.post(f"{API}/tasks", headers=self.sales_h,
                                     json={"title": "x", "related_type": "customer", "related_id": 999999999})
        self.assertEqual(missing.status_code, 404)
        half = self.w.client.post(f"{API}/tasks", headers=self.sales_h, json={"title": "x", "related_type": "customer"})
        self.assertEqual(half.status_code, 422)

    def test_views_and_due_filters(self):
        now = datetime.now(timezone.utc)
        overdue = self.create(self.sales2_h, title="Late", due_at=iso(now - timedelta(days=2)))
        later = self.create(self.sales2_h, title="Later", due_at=iso(now + timedelta(days=20)))
        undated = self.create(self.sales2_h, title="Someday")
        mine = self.ids(self.sales2_h)
        self.assertEqual(mine[:2], [overdue["id"], later["id"]])  # by due date, undated last
        self.assertEqual(mine[-1], undated["id"])
        self.assertEqual(self.ids(self.sales2_h, due="overdue"), [overdue["id"]])
        self.assertIn(undated["id"], self.ids(self.sales2_h, due="none"))
        self.assertNotIn(later["id"], self.ids(self.sales2_h, due="week"))
        self.assertNotIn(overdue["id"], self.ids(self.sales_h))  # not mine
        self.assertIn(overdue["id"], self.ids(self.sales_h, view="team"))
        self.assertTrue(next(t for t in self.w.client.get(f"{API}/tasks", headers=self.sales2_h).json()["items"]
                             if t["id"] == overdue["id"])["is_overdue"])
        summary = self.w.client.get(f"{API}/tasks/summary", headers=self.sales2_h).json()
        self.assertGreaterEqual(summary["open"], 3)
        self.assertGreaterEqual(summary["overdue"], 1)

        self.patch(later["id"], self.sales2_h, status="cancelled")
        self.assertNotIn(later["id"], self.ids(self.sales2_h))
        self.assertIn(later["id"], self.ids(self.sales2_h, status="all"))
        self.assertEqual(self.w.client.delete(f"{API}/tasks/{undated['id']}", headers=self.sales2_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/tasks/{undated['id']}", headers=self.sales2_h).status_code, 404)

    def test_recurring_task_makes_the_next_one(self):
        due = datetime.now(timezone.utc) + timedelta(days=1)
        t = self.create(title=f"Weekly stock check {self.w.sfx}", recurrence="weekly", due_at=iso(due),
                        reminder_at=iso(due - timedelta(hours=1)))
        self.patch(t["id"], status="done")
        nxt = [x for x in self.w.client.get(f"{API}/tasks", headers=self.sales_h, params={"q": f"stock check {self.w.sfx}"}).json()["items"]]
        self.assertEqual(len(nxt), 1)
        self.assertNotEqual(nxt[0]["id"], t["id"])
        got = datetime.fromisoformat(nxt[0]["due_at"])
        self.assertAlmostEqual((got - due).total_seconds(), 7 * 86400, delta=5)
        self.assertAlmostEqual((got - datetime.fromisoformat(nxt[0]["reminder_at"])).total_seconds(), 3600, delta=5)
        self.assertEqual(nxt[0]["recurrence"], "weekly")

    def test_reminders_are_emailed_once(self):
        from app.modules.tasks.service import TaskService

        t = self.create(title=f"Remind me {self.w.sfx}", reminder_at=iso(datetime.now(timezone.utc) - timedelta(minutes=1)))
        before = len(self.w.mail.sent)
        run(lambda s: TaskService(s).send_reminders(self.w.mail))
        mails = [m for m in self.w.mail.sent[before:] if t["title"] in m.subject]
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails[0].to, self.sales["email"])
        run(lambda s: TaskService(s).send_reminders(self.w.mail))
        self.assertEqual(len([m for m in self.w.mail.sent[before:] if t["title"] in m.subject]), 1)


if __name__ == "__main__":
    unittest.main()
