"""Tickets: business-hours maths, numbering + SLA, status flow, notes vs replies, assign, breach job, canned responses."""

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from tests.support import API, World, reset_limits, run, skip_unless_db

CHI = ZoneInfo("America/Chicago")


class BusinessHoursTests(unittest.TestCase):
    """`add_business_minutes` needs no database — the targets only stop the clock outside business hours."""

    def setUp(self):
        from app.modules.settings.groups import BusinessHours

        self.hours = BusinessHours()  # Mon–Fri 09:00–17:00, America/Chicago, no holidays

    def chi(self, value: datetime) -> datetime:
        return value.astimezone(CHI)

    def test_inside_the_same_day(self):
        from app.modules.tickets.business_hours import add_business_minutes

        start = datetime(2026, 10, 16, 10, 0, tzinfo=CHI)  # Friday 10:00
        out = add_business_minutes(start, 120, self.hours)
        self.assertEqual(out.tzinfo, timezone.utc)
        self.assertEqual(self.chi(out), datetime(2026, 10, 16, 12, 0, tzinfo=CHI))

    def test_spills_over_the_weekend(self):
        from app.modules.tickets.business_hours import add_business_minutes

        start = datetime(2026, 10, 16, 16, 0, tzinfo=CHI)  # Friday 16:00 → 60 min left today
        out = add_business_minutes(start, 120, self.hours)
        self.assertEqual(self.chi(out), datetime(2026, 10, 19, 10, 0, tzinfo=CHI))  # Monday 10:00

    def test_starts_outside_hours(self):
        from app.modules.tickets.business_hours import add_business_minutes

        start = datetime(2026, 10, 17, 12, 0, tzinfo=CHI)  # Saturday
        out = add_business_minutes(start, 480, self.hours)  # one business day
        self.assertEqual(self.chi(out), datetime(2026, 10, 19, 17, 0, tzinfo=CHI))  # Monday close

    def test_holidays_are_skipped(self):
        from app.modules.settings.groups import BusinessHours
        from app.modules.tickets.business_hours import add_business_minutes

        hours = BusinessHours(holidays=[datetime(2026, 10, 19).date()])  # Monday off
        start = datetime(2026, 10, 16, 16, 0, tzinfo=CHI)
        out = add_business_minutes(start, 120, hours)
        self.assertEqual(self.chi(out), datetime(2026, 10, 20, 10, 0, tzinfo=CHI))  # Tuesday 10:00

    def test_zero_minutes_is_unchanged(self):
        from app.modules.tickets.business_hours import add_business_minutes

        start = datetime(2026, 10, 17, 12, 0, tzinfo=CHI)
        self.assertEqual(add_business_minutes(start, 0, self.hours), start)


@skip_unless_db
class TicketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.support2, cls.support2_h = cls.w.user_with_token("support")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")
        cls.customer = cls.w.client.post(f"{API}/customers", headers=cls.manager_h, json={
            "first_name": "Casey", "last_name": "Client", "email": cls.w.email("casey")}).json()
        policy = cls.w.client.post(f"{API}/tickets/sla-policies", headers=cls.manager_h, json={
            "name": f"Urgent {cls.w.sfx}", "priority": "urgent", "first_response_minutes": 120,
            "resolve_minutes": 480})
        assert policy.status_code == 201, policy.text

    def setUp(self):
        reset_limits()

    def create(self, headers=None, **data):
        data.setdefault("subject", f"Order question {self.w.sfx}")
        res = self.w.client.post(f"{API}/tickets", headers=headers or self.support_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def reply(self, ticket_id, headers=None, **data):
        data.setdefault("body", "Thanks for reaching out.")
        return self.w.client.post(f"{API}/tickets/{ticket_id}/messages", headers=headers or self.support_h, json=data)

    def test_permissions(self):
        t = self.create(priority="urgent")
        self.assertEqual(t["status"], "new")
        self.assertEqual(t["assignee_id"], self.support["id"])
        # sales can read the queue but not change tickets
        self.assertEqual(self.w.client.get(f"{API}/tickets", headers=self.sales_h).status_code, 200)
        self.assertEqual(self.w.client.post(f"{API}/tickets", headers=self.sales_h, json={"subject": "x"}).status_code, 403)
        self.assertEqual(self.w.client.patch(f"{API}/tickets/{t['id']}", headers=self.sales_h, json={"priority": "low"}).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/tickets", headers=self.ro_h, json={"subject": "x"}).status_code, 403)
        # support may only assign to themselves; managers may assign to anyone
        self.assertEqual(self.w.client.patch(f"{API}/tickets/{t['id']}", headers=self.support_h,
                                             json={"assignee_id": self.support2["id"]}).status_code, 403)
        given = self.w.client.patch(f"{API}/tickets/{t['id']}", headers=self.manager_h,
                                    json={"assignee_id": self.support2["id"]})
        self.assertEqual(given.status_code, 200, given.text)
        self.assertEqual(given.json()["assignee_id"], self.support2["id"])

    def test_numbering_and_sla(self):
        t = self.create(priority="urgent", ticket_type="order_question", customer_id=self.customer["id"],
                        description="Where is my parcel?")
        self.assertTrue((t["number"] or "").startswith("T-"))
        self.assertIsNotNone(t["sla_policy_id"])
        self.assertIsNotNone(t["first_response_due_at"])
        self.assertIsNotNone(t["resolve_due_at"])
        self.assertEqual(t["customer_name"], "Casey Client")
        self.assertEqual(self.w.client.post(f"{API}/tickets", headers=self.support_h, json={"subject": "  "}).status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/tickets", headers=self.support_h,
                                            json={"subject": "x", "priority": "nonsense"}).status_code, 422)

    def test_status_flow_and_timeline(self):
        t = self.create()
        self.assertEqual(self.w.client.patch(f"{API}/tickets/{t['id']}", headers=self.support_h,
                                             json={"status": "closed"}).status_code, 200)
        closed = self.w.client.get(f"{API}/tickets/{t['id']}", headers=self.support_h).json()
        self.assertEqual(closed["status"], "closed")
        self.assertIsNotNone(closed["resolved_at"])
        self.assertIsNotNone(closed["closed_at"])
        # a closed ticket may be reopened, but not moved straight to pending
        self.assertEqual(self.w.client.patch(f"{API}/tickets/{t['id']}", headers=self.support_h,
                                             json={"status": "pending"}).status_code, 422)
        reopened = self.w.client.patch(f"{API}/tickets/{t['id']}", headers=self.support_h, json={"status": "open"}).json()
        self.assertEqual(reopened["status"], "open")
        self.assertIsNone(reopened["resolved_at"])
        # the ticket's own timeline is served through the shared record API
        timeline = self.w.client.get(f"{API}/entities/ticket/{t['id']}/timeline", headers=self.support_h)
        self.assertEqual(timeline.status_code, 200, timeline.text)
        titles = [a["title"] for a in timeline.json()["items"]]
        self.assertTrue(any("opened" in title for title in titles))

    def test_note_and_reply(self):
        t = self.create(customer_id=self.customer["id"])
        before = len(self.w.mail.sent)
        note = self.reply(t["id"], body="Checking with the warehouse.", kind="note")
        self.assertEqual(note.status_code, 201, note.text)
        self.assertEqual(note.json()["direction"], "internal")
        self.assertEqual(len(self.w.mail.sent), before)  # a note never emails the customer
        sent = self.reply(t["id"], body="On its way — sorry for the wait!", kind="reply")
        self.assertEqual(sent.status_code, 201, sent.text)
        self.assertEqual(sent.json()["direction"], "outbound")
        self.assertEqual(len(self.w.mail.sent), before + 1)
        self.assertEqual(self.w.mail.sent[-1].to, self.customer["email"])
        updated = self.w.client.get(f"{API}/tickets/{t['id']}", headers=self.support_h).json()
        self.assertIsNotNone(updated["first_responded_at"])
        self.assertEqual(updated["status"], "open")  # first activity moves it out of "new"
        # a reply needs a customer with an email address
        lonely = self.create()
        self.assertEqual(self.reply(lonely["id"], kind="reply").status_code, 422)
        messages = self.w.client.get(f"{API}/tickets/{t['id']}/messages", headers=self.support_h).json()
        self.assertEqual([m["direction"] for m in messages], ["internal", "outbound"])

    def test_summary_and_filters(self):
        mine = self.create(subject=f"Mine {self.w.sfx}")
        unassigned = self.create(self.manager_h, subject=f"Nobody {self.w.sfx}", assignee_id=None)
        summary = self.w.client.get(f"{API}/tickets/summary", headers=self.support_h).json()
        self.assertGreaterEqual(summary["open"], 2)
        self.assertGreaterEqual(summary["unassigned"], 1)
        listing = self.w.client.get(f"{API}/tickets", headers=self.support_h,
                                    params={"view": "mine", "q": f"Mine {self.w.sfx}"}).json()
        self.assertEqual([t["id"] for t in listing["items"]], [mine["id"]])
        nobody = self.w.client.get(f"{API}/tickets", headers=self.manager_h,
                                   params={"view": "unassigned", "q": f"Nobody {self.w.sfx}"}).json()
        self.assertEqual([t["id"] for t in nobody["items"]], [unassigned["id"]])

    def test_channels(self):
        """Every ticket says how the conversation reached the CRM (SPEC §3.9, the unified inbox)."""
        by_hand = self.create(subject=f"Walk-in {self.w.sfx}")
        self.assertEqual(by_hand["channel"], "manual")  # nothing said: staff typed it in
        phoned = self.create(subject=f"Phone {self.w.sfx}", channel="phone")
        self.assertEqual(phoned["channel"], "phone")

        # a queue can be one channel, like the inbox's tabs will be
        listing = self.w.client.get(f"{API}/tickets", headers=self.support_h,
                                    params={"channel": "phone", "q": f"Phone {self.w.sfx}"}).json()
        self.assertEqual([t["id"] for t in listing["items"]], [phoned["id"]])

        # staff can re-file a ticket, and a channel that isn't one is refused both ways
        moved = self.w.client.patch(f"{API}/tickets/{by_hand['id']}", headers=self.support_h,
                                    json={"channel": "live_chat"})
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()["channel"], "live_chat")
        self.assertEqual(self.w.client.patch(f"{API}/tickets/{by_hand['id']}", headers=self.support_h,
                                             json={"channel": "carrier_pigeon"}).status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/tickets", headers=self.support_h,
                                            json={"subject": "x", "channel": "nope"}).status_code, 422)
        # the values are the admin-editable kind the API hands the web
        kinds = {k["key"]: k for k in self.w.client.get(f"{API}/lookups", headers=self.support_h).json()}
        self.assertIn("ticket_channel", kinds)
        self.assertIn("shop_form", [v["key"] for v in kinds["ticket_channel"]["values"]])

    def test_waiting_on_us_is_the_customer_s_last_word(self):
        """The inbox's own question (SPEC §3.9): whose message is the newest, so nobody has answered yet?"""
        from app.modules.tickets.service import TicketService

        asked = f"Backorder {self.w.sfx}"  # a phrase of its own, so the query sees only these two
        answered = self.create(subject=f"{asked} answered", customer_id=self.customer["id"])
        self.assertEqual(self.reply(answered["id"], body="On its way.", kind="reply").status_code, 201)
        waiting = self.create(subject=f"{asked} waiting", customer_id=self.customer["id"])
        run(lambda s: TicketService(s).add_inbound(waiting["id"], body="Any news?",
                                                   external_id=f"backorder-{self.w.sfx}@example.com",
                                                   from_email=self.customer["email"]))

        def listed(**params):
            res = self.w.client.get(f"{API}/tickets", headers=self.support_h, params={"q": asked, **params})
            self.assertEqual(res.status_code, 200, res.text)
            return [t["id"] for t in res.json()["items"]]

        self.assertEqual(listed(needs_reply="true"), [waiting["id"]])    # they wrote last: ours to answer
        self.assertEqual(listed(needs_reply="false"), [answered["id"]])  # our reply settled that one
        self.assertEqual(sorted(listed()), sorted([answered["id"], waiting["id"]]))  # not asked: both

    def test_the_longest_wait_comes_first(self):
        """The waiting list is worked from the top: whoever has been waiting longest is first."""
        from app.modules.tickets.service import TicketService

        asked = f"Return {self.w.sfx}"
        first = self.create(subject=f"{asked} one", customer_id=self.customer["id"])
        second = self.create(subject=f"{asked} two", customer_id=self.customer["id"])
        run(lambda s: TicketService(s).add_inbound(first["id"], body="Still waiting.",
                                                   external_id=f"return-1-{self.w.sfx}@example.com",
                                                   from_email=self.customer["email"]))
        run(lambda s: TicketService(s).add_inbound(second["id"], body="Still waiting.",
                                                   external_id=f"return-2-{self.w.sfx}@example.com",
                                                   from_email=self.customer["email"]))

        rows = self.w.client.get(f"{API}/tickets", headers=self.support_h,
                                 params={"needs_reply": "true", "q": asked}).json()["items"]
        self.assertEqual([t["id"] for t in rows], [first["id"], second["id"]])

    def test_sla_breach_job(self):
        from app.modules.tickets.service import TicketService

        t = self.create(priority="urgent")

        async def make_late(session):
            from app.modules.tickets.repository import TicketRepository

            ticket = await TicketRepository(session).get(t["id"])
            past = datetime.now(timezone.utc) - timedelta(minutes=1)
            ticket.first_response_due_at = ticket.resolve_due_at = past

        run(make_late)
        line = run(lambda s: TicketService(s).check_sla())
        self.assertIn("breaches", line)
        got = self.w.client.get(f"{API}/tickets/{t['id']}", headers=self.support_h).json()
        self.assertTrue(got["first_response_breached"])
        self.assertTrue(got["resolve_breached"])
        self.assertIsNone(run(lambda s: TicketService(s).check_sla()))  # already flagged, nothing more

    def test_sla_policy_admin(self):
        self.assertEqual(self.w.client.get(f"{API}/tickets/sla-policies", headers=self.support_h).status_code, 200)
        self.assertEqual(self.w.client.post(f"{API}/tickets/sla-policies", headers=self.sales_h, json={
            "name": "Nope", "priority": "low", "first_response_minutes": 60, "resolve_minutes": 120}).status_code, 403)
        bad = self.w.client.post(f"{API}/tickets/sla-policies", headers=self.manager_h, json={
            "name": "Bad", "priority": "invented", "first_response_minutes": 60, "resolve_minutes": 120})
        self.assertEqual(bad.status_code, 422)
        created = self.w.client.post(f"{API}/tickets/sla-policies", headers=self.manager_h, json={
            "name": f"Low {self.w.sfx}", "priority": "low", "first_response_minutes": 960, "resolve_minutes": 2400}).json()
        off = self.w.client.patch(f"{API}/tickets/sla-policies/{created['id']}", headers=self.manager_h,
                                  json={"is_active": False})
        self.assertEqual(off.status_code, 200, off.text)
        self.assertFalse(off.json()["is_active"])

    def test_canned_responses(self):
        # anyone who can see tickets may read saved replies; only admins/managers may change them
        url = f"{API}/tickets/canned-responses"
        self.assertEqual(self.w.client.get(url, headers=self.support_h).status_code, 200)
        self.assertEqual(self.w.client.post(url, headers=self.support_h,
                                            json={"title": "Nope", "body": "x"}).status_code, 403)
        blank = self.w.client.post(url, headers=self.manager_h, json={"title": "   ", "body": "x"})
        self.assertEqual(blank.status_code, 422)
        created = self.w.client.post(url, headers=self.manager_h,
                                     json={"title": f"Where is my parcel {self.w.sfx}", "body": "It's on its way."})
        self.assertEqual(created.status_code, 201, created.text)
        row = created.json()
        self.assertTrue(row["is_active"])
        listing = self.w.client.get(url, headers=self.support_h).json()
        self.assertIn(row["id"], [r["id"] for r in listing])
        edited = self.w.client.patch(f"{url}/{row['id']}", headers=self.manager_h,
                                     json={"body": "Updated wording.", "is_active": False})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["body"], "Updated wording.")
        self.assertFalse(edited.json()["is_active"])
        self.assertEqual(self.w.client.patch(f"{url}/{row['id']}", headers=self.manager_h,
                                             json={"title": " "}).status_code, 422)
        self.assertEqual(self.w.client.delete(f"{url}/{row['id']}", headers=self.manager_h).status_code, 204)
        after = self.w.client.get(url, headers=self.support_h).json()
        self.assertNotIn(row["id"], [r["id"] for r in after])


if __name__ == "__main__":
    unittest.main()
