"""When the server looks for updates — pure policy, no DB."""

import unittest
from datetime import datetime, timedelta, timezone

from app.modules.deploy.policy import decide

UTC = timezone.utc
CHI = "America/Chicago"  # UTC-5 in October (CDT)


def d(**kw):
    base = dict(mode="auto", interval_minutes=10, schedule_times=[], tz=CHI, requested=False, last_check=None)
    base.update(kw)
    return decide(**base)


class PolicyTests(unittest.TestCase):
    now = datetime(2026, 10, 16, 21, 0, tzinfo=UTC)  # 16:00 in Chicago

    def test_manual_request_always_wins(self):
        self.assertEqual(d(now=self.now, mode="paused", requested=True).reason, "manual")
        self.assertTrue(d(now=self.now, mode="schedule", schedule_times=["02:00"], requested=True, last_check=self.now).go)

    def test_paused_never_goes(self):
        self.assertFalse(d(now=self.now, mode="paused").go)

    def test_auto_interval(self):
        self.assertTrue(d(now=self.now).go)  # never checked
        self.assertFalse(d(now=self.now, last_check=self.now - timedelta(minutes=4)).go)
        self.assertTrue(d(now=self.now, last_check=self.now - timedelta(minutes=10)).go)
        self.assertTrue(d(now=self.now, last_check=self.now - timedelta(minutes=9, seconds=45)).go)  # cron jitter
        self.assertTrue(d(now=self.now, interval_minutes=1, last_check=self.now - timedelta(minutes=1)).go)

    def test_schedule_fires_once_per_slot(self):
        sched = dict(mode="schedule", schedule_times=["02:00", "16:00"])
        # 15:59 Chicago last check, now 16:00 → the 16:00 slot fires
        self.assertEqual(d(now=self.now, last_check=self.now - timedelta(minutes=1), **sched).reason, "scheduled 16:00")
        # already checked at 16:00 → nothing more until 02:00
        self.assertFalse(d(now=self.now + timedelta(minutes=5), last_check=self.now, **sched).go)
        # cron was down overnight: the 02:00 slot is caught up the next time it runs
        later = datetime(2026, 10, 17, 8, 30, tzinfo=UTC)  # 03:30 Chicago
        self.assertEqual(d(now=later, last_check=self.now, **sched).reason, "scheduled 02:00")

    def test_schedule_without_previous_check_catches_up_last_day(self):
        self.assertTrue(d(now=self.now, mode="schedule", schedule_times=["09:00"]).go)


if __name__ == "__main__":
    unittest.main()
