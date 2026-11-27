"""Help feedback: anyone signed in can answer "Was this helpful?"; only admins read the answers."""

import unittest

from tests.support import API, World, reset_limits, skip_unless_db


@skip_unless_db
class HelpFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    def setUp(self):
        reset_limits()

    def _topic(self, name: str) -> str:
        return f"{name}-{self.w.sfx}".lower()

    def test_anyone_can_answer_and_only_admin_can_read(self):
        topic = self._topic("etsy-orders")
        res = self.w.client.post(f"{API}/help/feedback", headers=self.sales_h,
                                 json={"topic_id": topic, "page": "/channels/etsy/orders", "helpful": False,
                                       "comment": "  What does  Cost missing   mean? "})
        self.assertEqual(res.status_code, 204, res.text)
        self.w.client.post(f"{API}/help/feedback", headers=self.sales_h,
                           json={"topic_id": topic, "page": "/channels/etsy/orders", "helpful": True})

        self.assertEqual(self.w.client.get(f"{API}/help/feedback/summary", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/help/feedback", headers=self.sales_h).status_code, 403)

        summary = {r["topic_id"]: r for r in self.w.client.get(f"{API}/help/feedback/summary", headers=self.admin_h).json()}
        self.assertEqual((summary[topic]["helpful"], summary[topic]["not_helpful"]), (1, 1))

        rows = self.w.client.get(f"{API}/help/feedback", headers=self.admin_h,
                                 params={"topic_id": topic, "helpful": "false"}).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["comment"], "What does Cost missing mean?")
        self.assertEqual(rows[0]["user_name"], "Sales")

    def test_bad_input_is_refused(self):
        h = self.sales_h
        for body in (
            {"topic_id": "Not A Topic", "helpful": True},
            {"topic_id": "", "helpful": True},
            {"topic_id": "ok", "helpful": True, "comment": "x" * 1001},
            {"topic_id": "ok"},
        ):
            self.assertEqual(self.w.client.post(f"{API}/help/feedback", headers=h, json=body).status_code, 422, body)

    def test_needs_a_session(self):
        self.assertEqual(self.w.client.post(f"{API}/help/feedback", json={"topic_id": "ok", "helpful": True}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
