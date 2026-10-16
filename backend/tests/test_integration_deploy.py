"""Admin → Deployments API and the cron gate."""

import asyncio
import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class DeployTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.h = cls.w.user_with_token("admin")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")

    def setUp(self):
        reset_limits()
        self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "auto", "interval_minutes": 10})
        self.w.client.delete(f"{API}/deploy/now", headers=self.h)

    def gate(self):
        from app.modules.deploy.service import DeployService

        return run(lambda s: DeployService(s).gate_begin())

    def test_admin_only(self):
        self.assertEqual(self.w.client.get(f"{API}/deploy", headers=self.manager_h).status_code, 403)
        body = self.w.client.get(f"{API}/deploy", headers=self.h).json()
        self.assertEqual(body["mode"], "auto")
        self.assertIn("commit", body["api"])

    def test_pause_then_deploy_now_then_resume(self):
        res = self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "paused", "interval_minutes": 10})
        self.assertEqual(res.json()["mode"], "paused")
        self.assertFalse(self.gate().go)
        status = self.w.client.get(f"{API}/deploy", headers=self.h).json()
        self.assertTrue(status["cron_seen"])  # the gate call counts as a heartbeat

        queued = self.w.client.post(f"{API}/deploy/now", headers=self.h)
        self.assertEqual(queued.status_code, 202)
        self.assertIsNotNone(queued.json()["requested_at"])
        self.assertEqual(queued.json()["requested_by"], self.admin_name())
        decision = self.gate()
        self.assertEqual((decision.go, decision.reason), (True, "manual"))
        self.assertFalse(self.gate().go)  # request consumed; still paused

        from app.modules.deploy.service import DeployService

        run(lambda s: DeployService(s).gate_end(True, "API updated to abc123"))
        status = self.w.client.get(f"{API}/deploy", headers=self.h).json()
        self.assertEqual(status["last_result"], "✓ API updated to abc123")
        self.assertFalse(status["running"])

    def test_schedule_needs_times_and_validates(self):
        bad = self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "schedule", "schedule_times": []})
        self.assertEqual(bad.status_code, 422)
        bad = self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "schedule", "schedule_times": ["25:00"]})
        self.assertEqual(bad.status_code, 422)
        ok = self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "schedule", "schedule_times": ["16:00", "02:00", "02:00"]})
        self.assertEqual(ok.json()["schedule_times"], ["02:00", "16:00"])

    def test_cancel_request(self):
        self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "paused"})
        self.w.client.post(f"{API}/deploy/now", headers=self.h)
        self.assertIsNone(self.w.client.delete(f"{API}/deploy/now", headers=self.h).json()["requested_at"])
        self.assertFalse(self.gate().go)

    def test_log_endpoint(self):
        res = self.w.client.get(f"{API}/deploy/log", headers=self.h)
        self.assertEqual(res.status_code, 200)
        self.assertIn("log", res.json())

    def test_gate_cli(self):
        from app.workers.deploy_gate import _main

        self.w.client.put(f"{API}/deploy/config", headers=self.h, json={"mode": "paused"})
        self.assertEqual(asyncio.run(_main(["begin"])), "skip paused")
        self.assertEqual(asyncio.run(_main(["end", "ok", "no", "changes"])), "recorded")

    def admin_name(self):
        return next(e["full_name"] for e in self.w.client.get(f"{API}/users/directory", headers=self.h).json() if e["id"] == self.admin["id"])


if __name__ == "__main__":
    unittest.main()
