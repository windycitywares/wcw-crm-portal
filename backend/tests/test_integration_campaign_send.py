"""Campaigns going out: the audience snapshot taken when one starts, the dispatcher pacing to the SMTP limits,
every recipient followed through the outbox, and the public unsubscribe link (SPEC §3.6)."""

import re
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from tests.support import API, World, reset_limits, run, skip_unless_db
from tests.test_integration_mail import FakeTransport, no_sleep


@skip_unless_db
class CampaignSendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")  # view + edit + send
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")
        cls._n = 0

    def setUp(self):
        reset_limits()
        self.clear_outbox()
        self.email(enabled=True, daily_limit=300, per_minute=600)

    # ---- helpers ------------------------------------------------------------------------------
    def name(self, label: str = "x") -> str:
        self._n += 1
        return f"{label}-{self._n}-{self.w.sfx}@example.com"

    def clear_outbox(self):
        """A clean slate: mail left by other tests must not count against the SMTP limits."""
        from app.modules.mail.models import EmailOutbox

        run(lambda s: s.execute(update(EmailOutbox).values(status="failed", sent_at=None)))

    def email(self, **values):
        base = {"smtp_host": "mail.example.com", "from_address": "crm@example.com",
                "from_name": "Windy City Wares", "footer_address": "1 Warehouse Way, Chicago, IL"}
        res = self.w.client.put(f"{API}/settings/email", headers=self.admin_h, json={**base, **values})
        self.assertEqual(res.status_code, 200, res.text)

    def template(self, **data) -> dict:
        data.setdefault("name", self.name("template"))
        data.setdefault("subject", "Hi {{ customer.first_name }}")
        data.setdefault("html", "<p>Hello {{ customer.first_name }}, sale this week.</p>")
        res = self.w.client.post(f"{API}/campaigns/templates", headers=self.marketing_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def customer(self, **data) -> dict:
        data.setdefault("first_name", "Pat")
        data.setdefault("email", self.name("customer"))
        data.setdefault("marketing_consent", True)
        res = self.w.client.post(f"{API}/customers", headers=self.admin_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def audience(self, customers: list[dict] | None = None, **data) -> dict:
        data.setdefault("name", self.name("list"))
        made = self.w.client.post(f"{API}/campaigns/lists", headers=self.marketing_h, json=data)
        self.assertEqual(made.status_code, 201, made.text)
        made = made.json()
        if customers:
            res = self.add(made["id"], [c["id"] for c in customers])
            self.assertEqual(res.status_code, 200, res.text)
        return made

    def add(self, list_id: int, ids: list[int]):
        return self.w.client.post(f"{API}/campaigns/lists/{list_id}/members", headers=self.marketing_h,
                                  json={"customer_ids": ids})

    def tag(self, customer_id: int, *names: str) -> None:
        self._n += 1
        res = self.w.client.put(f"{API}/entities/customer/{customer_id}/tags", headers=self.marketing_h,
                                json={"names": [f"{n}-{self.w.sfx}" for n in names]})
        self.assertEqual(res.status_code, 200, res.text)

    def campaign(self, template: dict, audience: dict, headers=None, **data) -> dict:
        data.setdefault("name", self.name("campaign"))
        data["template_id"], data["target_list_id"] = template["id"], audience["id"]
        res = self.w.client.post(f"{API}/campaigns", headers=headers or self.marketing_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def get_campaign(self, campaign_id: int) -> dict:
        res = self.w.client.get(f"{API}/campaigns/{campaign_id}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def start(self, campaign_id: int, headers=None) -> dict:
        res = self.w.client.post(f"{API}/campaigns/{campaign_id}/send", headers=headers or self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def recipients(self, campaign_id: int, **params) -> dict:
        res = self.w.client.get(f"{API}/campaigns/{campaign_id}/recipients", headers=self.marketing_h,
                                params={"page_size": 200, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def dispatch(self) -> str | None:
        """One run of the campaigns job."""
        from app.modules.campaigns.service import CampaignService

        return run(lambda s: CampaignService(s).dispatch_due())

    def deliver(self, transport) -> str | None:
        """One run of the outbox job, with a transport that records instead of sending."""
        from app.modules.mail.service import MailService

        return run(lambda s: MailService(s, transport, sleep=no_sleep).deliver_due())

    def poke_campaign(self, campaign_id: int, **columns) -> None:
        from app.modules.campaigns.models import Campaign

        async def touch(session):
            row = await session.get(Campaign, campaign_id)
            for key, value in columns.items():
                setattr(row, key, value)

        run(touch)

    def poke_outbox(self, campaign_id: int, **columns) -> None:
        """Stand in for the outbox after it has retried and given up (that part is the mail module's own)."""
        from app.modules.campaigns.models import CampaignRecipient
        from app.modules.mail.models import EmailOutbox

        async def touch(session):
            ids = (await session.execute(
                select(CampaignRecipient.outbox_id).where(
                    CampaignRecipient.campaign_id == campaign_id,
                    CampaignRecipient.outbox_id.is_not(None)))).scalars().all()
            await session.execute(update(EmailOutbox).where(EmailOutbox.id.in_(list(ids))).values(**columns))

        run(touch)

    def on_suppressions(self, email: str) -> dict:
        res = self.w.client.get(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                params={"q": email})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    # ---- a campaign going out ------------------------------------------------------------------
    def test_a_campaign_goes_out_to_its_audience(self):
        template = self.template()
        ada = self.customer(first_name="Ada")
        grace = self.customer(first_name="Grace")
        never = self.customer(first_name="Nope", marketing_consent=False)
        audience = self.audience([ada, grace, never])
        campaign = self.campaign(template, audience)

        self.assertEqual(campaign["status"], "draft")
        self.assertEqual((campaign["template_name"], campaign["target_list_name"]),
                         (template["name"], audience["name"]))
        # nobody has been copied in yet, so the numbers are the audience as it is now
        self.assertEqual((campaign["audience"], campaign["reachable"]), (3, 2))
        self.assertEqual(campaign["recipients"]["total"], 0)

        started = self.start(campaign["id"])
        self.assertEqual(started["status"], "sending")
        self.assertEqual(started["recipients"]["total"], 3)
        self.assertEqual(started["recipients"]["pending"], 3)  # copied in, nothing queued yet
        self.assertIsNotNone(started["started_at"])

        self.assertIn("queued 2", self.dispatch())
        transport = FakeTransport()
        self.assertIn("sent 2", self.deliver(transport))

        # each recipient got their own message, footer and their own unsubscribe link
        self.assertEqual(sorted(m.to for m in transport.sent), sorted([ada["email"], grace["email"]]))
        body = {m.to: m.html for m in transport.sent}
        self.assertIn("Hello Ada", body[ada["email"]])
        self.assertIn("1 Warehouse Way, Chicago, IL", body[ada["email"]])
        self.assertIn("unsubscribe?token=", body[ada["email"]])
        self.assertIn(f"&c={campaign['id']}", body[ada["email"]])  # the campaign is noted on the link
        self.assertIn(f"&c={campaign['id']}", body[grace["email"]])
        links = {m.to: re.search(r"unsubscribe\?token=([\w\-.]+)", m.html).group(1) for m in transport.sent}
        self.assertEqual(len(set(links.values())), 2)  # … and it is each customer's own token

        # the campaign learns from the outbox and closes itself
        self.assertIn("finished 1", self.dispatch())
        done = self.get_campaign(campaign["id"])
        self.assertEqual(done["status"], "sent")
        self.assertIsNotNone(done["finished_at"])
        self.assertEqual(done["recipients"]["sent"], 2)
        self.assertEqual(done["recipients"]["skipped"], 1)

        page = self.recipients(campaign["id"])
        who = {r["email"]: r for r in page["items"]}
        self.assertEqual(who[ada["email"]]["status"], "sent")
        self.assertIsNotNone(who[ada["email"]]["sent_at"])
        self.assertEqual(who[ada["email"]]["full_name"], "Ada")
        # consent is checked when the message would go out, and the reason is kept
        self.assertEqual((who[never["email"]]["status"], who[never["email"]]["reason"]),
                         ("skipped", "no marketing consent"))
        self.assertEqual(page["counts"]["total"], 3)

        # the list shows what happened, and the campaign can be filtered to
        listing = self.w.client.get(f"{API}/campaigns", headers=self.marketing_h,
                                    params={"status": "sent", "q": campaign["name"]}).json()
        self.assertEqual([c["id"] for c in listing["items"]], [campaign["id"]])

    def test_the_dispatcher_never_queues_more_than_can_go_out(self):
        """The outbox does the pacing; the dispatcher only hands it as much as it has room for, so no message
        waits long enough to expire unsent."""
        self.email(enabled=True, daily_limit=2, per_minute=600)
        people = [self.customer(first_name=f"P{i}") for i in range(4)]
        campaign = self.campaign(self.template(), self.audience(people))
        self.start(campaign["id"])

        self.assertIn("queued 2", self.dispatch())  # the daily limit, not the audience size
        transport = FakeTransport()
        self.assertIn("sent 2", self.deliver(transport))
        self.assertIsNone(self.dispatch())  # no room: nothing queued, and nobody lost
        page = self.recipients(campaign["id"])
        self.assertEqual((page["counts"]["sent"], page["counts"]["pending"]), (2, 2))
        self.assertEqual(self.get_campaign(campaign["id"])["status"], "sending")

        # another day's room lets the rest out, and only then is the campaign finished
        self.email(enabled=True, daily_limit=300, per_minute=600)
        self.assertIn("queued 2", self.dispatch())
        self.deliver(transport)
        self.assertIn("finished 1", self.dispatch())
        self.assertEqual(len(transport.sent), 4)
        self.assertEqual(self.get_campaign(campaign["id"])["status"], "sent")

    def test_nothing_goes_out_while_email_is_off(self):
        self.email(enabled=False)
        campaign = self.campaign(self.template(), self.audience([self.customer()]))
        self.start(campaign["id"])
        self.assertIn("email is off", self.dispatch())
        self.assertEqual(self.recipients(campaign["id"])["counts"]["pending"], 1)

        self.email(enabled=True)
        self.assertIn("queued 1", self.dispatch())

    def test_a_segment_is_frozen_when_the_campaign_starts(self):
        ada = self.customer(first_name="Ada")
        gary = self.customer(first_name="Gary")
        self.tag(ada["id"], "vip")
        segment = self.audience(kind="segment", rules={
            "match": "all", "rules": [{"field": "tags", "op": "has_any", "value": [f"vip-{self.w.sfx}"]}]})
        campaign = self.campaign(self.template(), segment)
        self.assertEqual(campaign["target_list_kind"], "segment")
        self.assertEqual(campaign["audience"], 1)

        self.start(campaign["id"])
        self.tag(gary["id"], "vip")  # the rules now match two …
        self.assertEqual(self.get_campaign(campaign["id"])["audience"], 2)
        self.assertEqual(self.recipients(campaign["id"])["counts"]["total"], 1)  # … the campaign has one

        self.dispatch()
        transport = FakeTransport()
        self.deliver(transport)
        self.assertEqual([m.to for m in transport.sent], [ada["email"]])

    def test_a_failed_message_is_kept_on_the_recipient(self):
        campaign = self.campaign(self.template(), self.audience([self.customer(first_name="Ada")]))
        self.start(campaign["id"])
        self.dispatch()
        self.poke_outbox(campaign["id"], status="failed", last_error="550 no such user")

        self.assertIn("finished 1", self.dispatch())
        recipient = self.recipients(campaign["id"])["items"][0]
        self.assertEqual((recipient["status"], recipient["reason"]), ("failed", "550 no such user"))
        done = self.get_campaign(campaign["id"])
        self.assertEqual((done["status"], done["recipients"]["failed"]), ("sent", 1))

    # ---- the calendar ---------------------------------------------------------------------------
    def test_scheduling_and_taking_it_off_the_calendar(self):
        campaign = self.campaign(self.template(), self.audience([self.customer()]))
        now = datetime.now(timezone.utc)
        past = self.w.client.post(f"{API}/campaigns/{campaign['id']}/schedule", headers=self.marketing_h,
                                  json={"scheduled_at": (now - timedelta(hours=1)).isoformat()})
        self.assertEqual(past.status_code, 422, past.text)

        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/schedule", headers=self.marketing_h,
                                 json={"scheduled_at": (now + timedelta(hours=2)).isoformat()})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["status"], "scheduled")

        # not due yet: the job leaves it alone
        self.assertIsNone(self.dispatch())
        self.assertEqual(self.get_campaign(campaign["id"])["status"], "scheduled")

        self.poke_campaign(campaign["id"], scheduled_at=now - timedelta(minutes=1))
        self.assertIn("started 1", self.dispatch())
        self.assertEqual(self.get_campaign(campaign["id"])["status"], "sending")
        self.assertEqual(self.recipients(campaign["id"])["counts"]["total"], 1)  # copied in on the way

        # taking an unscheduled campaign off the calendar is meaningless … 
        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/unschedule", headers=self.marketing_h)
        self.assertEqual(res.status_code, 422, res.text)

        # … and a scheduled one goes back to being a draft
        other = self.campaign(self.template(), self.audience([self.customer()]))
        self.w.client.post(f"{API}/campaigns/{other['id']}/schedule", headers=self.marketing_h,
                           json={"scheduled_at": (now + timedelta(days=1)).isoformat()})
        res = self.w.client.post(f"{API}/campaigns/{other['id']}/unschedule", headers=self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual((res.json()["status"], res.json()["scheduled_at"]), ("draft", None))

    # ---- the rules around a campaign that has started -------------------------------------------
    def test_editing_a_campaign_and_deleting_it(self):
        template = self.template()
        second = self.template()
        campaign = self.campaign(template, self.audience([self.customer()]))

        res = self.w.client.post(f"{API}/campaigns", headers=self.marketing_h,
                                 json={"name": campaign["name"], "template_id": template["id"],
                                       "target_list_id": campaign["target_list_id"]})
        self.assertEqual(res.status_code, 409, res.text)  # names are unique

        res = self.w.client.patch(f"{API}/campaigns/{campaign['id']}", headers=self.marketing_h,
                                  json={"template_id": second["id"]})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["template_name"], second["name"])

        self.start(campaign["id"])
        res = self.w.client.patch(f"{API}/campaigns/{campaign['id']}", headers=self.marketing_h,
                                  json={"name": self.name("renamed")})
        self.assertEqual(res.status_code, 422, res.text)
        res = self.w.client.delete(f"{API}/campaigns/{campaign['id']}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 422, res.text)
        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/send", headers=self.marketing_h)
        self.assertEqual(res.status_code, 422, res.text)

        # pausing holds it (nothing new is queued), resuming lets it carry on, and a paused one can go
        self.assertEqual(self.w.client.get(f"{API}/campaigns/{campaign['id']}",
                                           headers=self.marketing_h).json()["status"], "sending")
        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/pause", headers=self.marketing_h)
        self.assertEqual(res.json()["status"], "paused")
        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/pause", headers=self.marketing_h)
        self.assertEqual(res.status_code, 422, res.text)
        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/resume", headers=self.marketing_h)
        self.assertEqual(res.json()["status"], "sending")
        self.assertEqual(self.w.client.delete(f"{API}/campaigns/{campaign['id']}",
                                              headers=self.marketing_h).status_code, 422)

    def test_sending_to_an_empty_audience_is_refused(self):
        campaign = self.campaign(self.template(), self.audience())
        self.assertEqual(self.get_campaign(campaign["id"])["audience"], 0)
        res = self.w.client.post(f"{API}/campaigns/{campaign['id']}/send", headers=self.marketing_h)
        self.assertEqual(res.status_code, 422, res.text)
        self.assertIn("nobody in this audience", res.text)
        self.assertEqual(self.get_campaign(campaign["id"])["status"], "draft")

    # ---- the unsubscribe link -------------------------------------------------------------------
    def test_the_unsubscribe_link_works_without_a_login(self):
        from app.modules.campaigns import tokens

        person = self.customer(first_name="Dana", last_name="Lee")
        audience = self.audience([person])
        campaign = self.campaign(self.template(), audience)
        token = tokens.sign(person["id"])  # the same token the footer's link carries

        # the GET shows the customer who they are, and changes nothing
        res = self.w.client.get(f"{API}/campaigns/unsubscribe", params={"token": token})
        self.assertEqual(res.status_code, 200, res.text)  # no headers at all: no login
        self.assertEqual(res.json(), {"name": "Dana Lee", "email": person["email"], "unsubscribed": False})
        self.assertTrue(self.w.client.get(f"{API}/customers/{person['id']}",
                                          headers=self.marketing_h).json()["marketing_consent"])

        res = self.w.client.post(f"{API}/campaigns/unsubscribe",
                                 json={"token": token, "campaign_id": campaign["id"]})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["unsubscribed"])

        after = self.w.client.get(f"{API}/customers/{person['id']}", headers=self.marketing_h).json()
        self.assertFalse(after["marketing_consent"])
        self.assertIsNotNone(after["unsubscribed_at"])
        on_list = self.on_suppressions(person["email"])
        self.assertEqual(on_list["total"], 1)
        self.assertEqual(on_list["items"][0]["reason"], "unsubscribed")
        self.assertEqual(on_list["items"][0]["source"], "link")
        self.assertIn(campaign["name"], on_list["items"][0]["note"])  # which campaign they left from
        self.assertEqual(self.w.client.get(f"{API}/campaigns/unsubscribe",
                                           params={"token": token}).json()["unsubscribed"], True)

        # clicking again is a no-op, not a second suppression
        res = self.w.client.post(f"{API}/campaigns/unsubscribe", json={"token": token})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.on_suppressions(person["email"])["total"], 1)

        # a forged token, a token for something else, and no token at all
        self.assertEqual(self.w.client.get(f"{API}/campaigns/unsubscribe",
                                           params={"token": "not-a-token"}).status_code, 404)
        self.assertEqual(self.w.client.post(f"{API}/campaigns/unsubscribe",
                                            json={"token": tokens.sign(person["id"], "campaign")}).status_code, 404)
        self.assertEqual(self.w.client.post(f"{API}/campaigns/unsubscribe", json={}).status_code, 422)

        # and the next campaign to that audience skips them, with the reason kept
        again = self.campaign(self.template(), audience)
        self.start(again["id"])
        self.assertIn("skipped 1", self.dispatch())
        recipient = self.recipients(again["id"])["items"][0]
        self.assertEqual((recipient["status"], recipient["reason"]), ("skipped", "unsubscribed"))

    def test_a_suppressed_address_is_skipped(self):
        person = self.customer(first_name="Bounce")
        res = self.w.client.post(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                 json={"email": person["email"], "reason": "bounced"})
        self.assertEqual(res.status_code, 201, res.text)
        campaign = self.campaign(self.template(), self.audience([person]))
        self.start(campaign["id"])
        self.assertIn("skipped 1", self.dispatch())
        recipient = self.recipients(campaign["id"])["items"][0]
        self.assertEqual((recipient["status"], recipient["reason"]), ("skipped", "suppressed"))

    # ---- permissions ----------------------------------------------------------------------------
    def test_permissions(self):
        template = self.template()
        audience = self.audience([self.customer()])
        campaign = self.campaign(template, audience)

        self.assertEqual(self.w.client.get(f"{API}/campaigns", headers=self.ro_h).status_code, 200)
        self.assertEqual(self.w.client.get(f"{API}/campaigns", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/campaigns/{campaign['id']}/recipients",
                                           headers=self.sales_h).status_code, 403)

        # writing needs campaigns:edit, and sending needs campaigns:send
        draft = {"name": self.name("nope"), "template_id": template["id"], "target_list_id": audience["id"]}
        self.assertEqual(self.w.client.post(f"{API}/campaigns", headers=self.ro_h,
                                            json=draft).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/campaigns/{campaign['id']}/send",
                                            headers=self.ro_h).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/campaigns/{campaign['id']}/send",
                                            headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/campaigns/{campaign['id']}/send",
                                            headers=self.marketing_h).status_code, 200)


if __name__ == "__main__":
    unittest.main()
