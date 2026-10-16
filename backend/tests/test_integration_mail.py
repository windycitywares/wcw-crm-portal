"""Email outbox: off/on, send now, limits, retry with back-off, giving up, the background job."""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from tests.support import World, reset_limits, run, skip_unless_db


class FakeTransport:
    def __init__(self, fail: int = 0):
        self.fail, self.sent = fail, []

    def __call__(self, _settings):
        return self

    async def send(self, mail):
        if self.fail:
            self.fail -= 1
            raise OSError("smtp down")
        self.sent.append(mail)


async def no_sleep(_seconds):
    return None


@skip_unless_db
class MailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.h = cls.w.user_with_token("admin")

    def setUp(self):
        from sqlalchemy import update

        from app.modules.mail.models import EmailOutbox

        async def clear(s):  # a clean slate: older rows from other tests don't count against the limits
            await s.execute(update(EmailOutbox).values(status="failed", sent_at=None))

        run(clear)
        self.email(enabled=True, daily_limit=300, per_minute=600)

    def email(self, **values):
        base = {"smtp_host": "mail.example.com", "from_address": "crm@example.com"}
        res = self.w.client.put("/api/v1/settings/email", headers=self.h, json={**base, **values})
        self.assertEqual(res.status_code, 200, res.text)

    def queue(self, n=1, prefix="S", **kw):
        from app.integrations.email import Mail
        from app.modules.mail.service import MailService

        async def go(s):
            ids = [(await MailService(s).queue(Mail(to=f"c{i}@example.com", subject=f"{prefix}{i}", text="hi"), **kw)).id for i in range(n)]
            return ids

        return run(go)

    def deliver(self, transport):
        from app.modules.mail.service import MailService

        return run(lambda s: MailService(s, transport, sleep=no_sleep).deliver_due())

    def test_outbox_sender_sends_now_when_on(self):
        from app.integrations.email import Mail
        from app.modules.mail.service import OutboxEmailSender

        t = FakeTransport()
        run(lambda s: OutboxEmailSender(s, t).send(Mail(to="now@example.com", subject="Hi", text="x")))
        self.assertEqual([m.to for m in t.sent], ["now@example.com"])

    def test_off_keeps_mail_queued_with_reason(self):
        from app.integrations.email import Mail
        from app.modules.mail.service import OFF, OutboxEmailSender

        self.email(enabled=False)
        t = FakeTransport()
        run(lambda s: OutboxEmailSender(s, t).send(Mail(to="later@example.com", subject="Hi", text="x")))
        self.assertEqual(t.sent, [])
        from sqlalchemy import select

        from app.modules.mail.models import EmailOutbox

        row = run(lambda s: s.scalar(select(EmailOutbox).where(EmailOutbox.to_email == "later@example.com").order_by(EmailOutbox.id.desc())))
        self.assertEqual((row.status, row.last_error), ("queued", OFF))
        self.assertIsNone(self.deliver(t))  # job does nothing while off
        self.email(enabled=True)
        self.assertIn("sent 1", self.deliver(t))
        self.assertEqual([m.to for m in t.sent], ["later@example.com"])

    def test_daily_limit_and_system_first(self):
        self.email(enabled=True, daily_limit=2, per_minute=600)
        campaign = self.queue(2, prefix="CAMP", category="campaign")
        system = self.queue(1, prefix="SYS")
        t = FakeTransport()
        result = self.deliver(t)
        self.assertIn("sent 2", result)
        self.assertEqual(t.sent[0].subject, "SYS0")  # the system message went first …
        statuses = {r.id: r.status for r in _all(campaign + system)}
        self.assertEqual(statuses[system[0]], "sent")
        self.assertEqual(sorted(statuses.values()), ["queued", "sent", "sent"])  # … and one campaign mail waits

    def test_retry_with_backoff_then_fail(self):
        from app.modules.mail.service import MAX_ATTEMPTS

        ids = self.queue(1)
        t = FakeTransport(fail=MAX_ATTEMPTS)
        self.deliver(t)
        row = _all(ids)[0]
        self.assertEqual((row.status, row.attempts), ("queued", 1))
        self.assertIn("smtp down", row.last_error)
        self.assertGreater(row.send_after, datetime.now(timezone.utc) + timedelta(minutes=4))
        for _ in range(MAX_ATTEMPTS - 1):  # make it due again each time
            _make_due(ids)
            self.deliver(t)
        self.assertEqual(_all(ids)[0].status, "failed")

    def test_old_unsent_mail_expires(self):
        ids = self.queue(1)

        async def age(s):
            from sqlalchemy import update

            from app.modules.mail.models import EmailOutbox

            await s.execute(update(EmailOutbox).where(EmailOutbox.id.in_(ids))
                            .values(created_at=datetime.now(timezone.utc) - timedelta(days=4)))

        run(age)
        self.assertIn("expired 1", self.deliver(FakeTransport()))
        self.assertEqual(_all(ids)[0].status, "failed")

    def test_job_runner(self):
        from app.workers.run_jobs import run as run_jobs

        self.email(enabled=False)
        self.assertEqual(asyncio.run(run_jobs({"outbox"})), 0)


def _rows(s, ids):
    from sqlalchemy import select

    from app.modules.mail.models import EmailOutbox

    return s.execute(select(EmailOutbox).where(EmailOutbox.id.in_(ids)).order_by(EmailOutbox.id))


def _all(ids):
    async def go(s):
        return (await _rows(s, ids)).scalars().all()

    return run(go)


def _make_due(ids):
    async def go(s):
        from sqlalchemy import update

        from app.modules.mail.models import EmailOutbox

        await s.execute(update(EmailOutbox).where(EmailOutbox.id.in_(ids)).values(send_after=datetime.now(timezone.utc)))

    run(go)


if __name__ == "__main__":
    unittest.main()
