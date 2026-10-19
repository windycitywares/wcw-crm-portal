"""Campaigns: email templates (merge fields, preview, test send, version, names) and the suppression list.

The renderer and the unsubscribe tokens need no database, so their tests always run; the rest needs one.
"""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


class RenderTests(unittest.TestCase):
    """The sandboxed renderer and the compliance footer — no database needed."""

    def render(self, **kw):
        from app.modules.campaigns import render

        return render

    def test_merge_fields_and_footer(self):
        render = self.render()
        context = render.sample_context()
        subject = render.render("Hi {{ customer.first_name }}", context)
        self.assertEqual(subject, "Hi Dana")
        body = render.render("<p>Hello {{ customer.full_name }}</p>", context, html=True)
        html, text = render.with_footer(body, render.plain_text(body), sender_name="Windy City Wares",
                                        footer_address="1 Warehouse Way, Chicago, IL",
                                        unsubscribe_url=context["unsubscribe_url"])
        self.assertIn("Dana Reed", html)
        self.assertIn("1 Warehouse Way, Chicago, IL", html)
        self.assertIn(context["unsubscribe_url"], html)
        self.assertIn("Unsubscribe", text)
        self.assertIn("1 Warehouse Way, Chicago, IL", text)

    def test_html_is_escaped_and_text_is_not(self):
        render = self.render()
        context = {**render.sample_context(), "customer": {"first_name": "Dana & Co <b>"}}
        self.assertEqual(render.render("{{ customer.first_name }}", context, html=True),
                         "Dana &amp; Co &lt;b&gt;")
        self.assertEqual(render.render("{{ customer.first_name }}", context), "Dana & Co <b>")

    def test_plain_text_strips_tags(self):
        render = self.render()
        text = render.plain_text("<h1>Sale</h1><p>Ends <b>Friday</b>.</p><p>Buy<br>now</p>")
        self.assertEqual(text, "Sale\n\nEnds Friday.\n\nBuy\nnow")

    def test_bad_merge_field_is_an_error(self):
        from app.core.exceptions import ValidationFailedError

        with self.assertRaises(ValidationFailedError):
            self.render().render("{{ customer.nickname }}", self.render().sample_context())

    def test_sandbox_refuses_object_poking(self):
        from app.core.exceptions import ValidationFailedError

        with self.assertRaises(ValidationFailedError):
            self.render().render("{{ ''.__class__ }}", self.render().sample_context())


class TokenTests(unittest.TestCase):
    """The signed unsubscribe link: only the customer it was minted for, and only until it expires."""

    def test_round_trip(self):
        from app.modules.campaigns import tokens

        token = tokens.sign(42)
        self.assertEqual(tokens.read_unsubscribe_token(token), 42)
        self.assertIn("/unsubscribe?token=", tokens.unsubscribe_url(42, base_url="https://crm.example.com/"))

    def test_rejects_forgery_and_tampering(self):
        from app.modules.campaigns import tokens

        self.assertIsNone(tokens.read_unsubscribe_token("nonsense"))
        self.assertIsNone(tokens.read_unsubscribe_token(""))
        self.assertIsNone(tokens.read_unsubscribe_token(tokens.sign(1)[:-1] + "x"))

    def test_rejects_expired_and_wrong_purpose(self):
        from app.modules.campaigns import tokens

        self.assertIsNone(tokens.read_unsubscribe_token(tokens.sign(7, ttl_days=-1)))
        self.assertIsNone(tokens.read_unsubscribe_token(tokens.sign(7, "open")))


class CampaignTrackingUnitTests(unittest.TestCase):
    def test_record_event_and_report_are_derived_from_campaign_events(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from app.modules.campaigns.models import Campaign, CampaignRecipient, CLICK, OPEN
        from app.modules.campaigns.service import CampaignService

        service = CampaignService(AsyncMock())
        service.recipients.with_campaign = AsyncMock(return_value=(CampaignRecipient(
            id=21, campaign_id=7, customer_id=9, email="pink@example.com", status="sent"
        ), "Spring sale"))
        service.events.add_once = AsyncMock(return_value=True)
        service.timeline.record = AsyncMock()

        self.assertTrue(asyncio.run(service.record_event(recipient_id=21, kind=OPEN, url="")))
        service.timeline.record.assert_awaited_once()

        service._get_campaign = AsyncMock(return_value=Campaign(
            id=7, name="Spring sale", status="sent", template_id=5,
            target_list_id=11, created_by=1, updated_by=1,
        ))
        service.recipients.counts = AsyncMock(return_value={7: {"pending": 0, "queued": 0, "sent": 4, "failed": 0, "skipped": 1}})
        service.events.people = AsyncMock(return_value={OPEN: 3, CLICK: 2, "unsubscribe": 1})
        service.events.links = AsyncMock(return_value=[("https://shop.example.com/sale", 2)])
        template = MagicMock()
        template.name = "Spring template"
        service.templates.get = AsyncMock(return_value=template)
        service._list_names = AsyncMock(return_value={11: "VIP list"})

        report = asyncio.run(service.report(7))
        self.assertEqual(report.campaign_id, 7)
        self.assertEqual(report.opened, 3)
        self.assertEqual(report.clicked, 2)
        self.assertEqual(report.delivered, 4)
        self.assertEqual(report.links[0].url, "https://shop.example.com/sale")


@skip_unless_db
class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")
        # the postal address every campaign email has to carry (CAN-SPAM)
        res = cls.w.client.put(f"{API}/settings/email", headers=cls.admin_h,
                               json={"from_name": "Windy City Wares", "footer_address": "1 Warehouse Way, Chicago, IL"})
        assert res.status_code == 200, res.text

    def setUp(self):
        reset_limits()

    # ---- helpers ------------------------------------------------------------------------------
    def name(self, label: str = "x") -> str:
        return self.w.email(label)  # unique, so tests never clash with leftover rows

    def template(self, content: str = "<p>Hello {{ customer.first_name }}</p>", **data):
        res = self.w.client.post(f"{API}/campaigns/templates", headers=self.marketing_h, json={
            "name": self.name("template"), "subject": "Hi {{ customer.first_name }}", "html": content, **data})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def save_template(self, headers=None, **data):
        data.setdefault("name", self.name("template"))
        data.setdefault("subject", "A fine subject")
        data.setdefault("html", "<p>Body</p>")
        return self.w.client.post(f"{API}/campaigns/templates", headers=headers or self.marketing_h, json=data)

    def suppress(self, email: str, **data):
        return self.w.client.post(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                  json={"email": email, **data})

    def customer(self, **data):
        res = self.w.client.post(f"{API}/customers", headers=self.admin_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    # ---- templates ----------------------------------------------------------------------------
    def test_template_round_trip_and_derived_text(self):
        made = self.template("<p>Hello {{ customer.first_name }},</p><p>Sale this week.</p>")
        self.assertEqual(made["version"], 1)
        # the text body is derived from the HTML, so every email has one
        self.assertEqual(made["text"], "Hello {{ customer.first_name }},\n\nSale this week.")

        res = self.w.client.get(f"{API}/campaigns/templates/{made['id']}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["html"], made["html"])

        listing = self.w.client.get(f"{API}/campaigns/templates", headers=self.marketing_h,
                                    params={"q": made["name"]}).json()
        self.assertEqual([x["name"] for x in listing["items"]], [made["name"]])
        self.assertNotIn("html", listing["items"][0])  # the list stays light

        res = self.w.client.patch(f"{API}/campaigns/templates/{made['id']}", headers=self.marketing_h,
                                  json={"subject": "Still hi", "html": "<p>New words</p>"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["version"], 2)
        self.assertEqual(res.json()["subject"], "Still hi")
        self.assertEqual(res.json()["text"], "New words")  # re-derived from the new HTML

        res = self.w.client.delete(f"{API}/campaigns/templates/{made['id']}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 204, res.text)
        self.assertEqual(self.w.client.get(f"{API}/campaigns/templates/{made['id']}",
                                           headers=self.marketing_h).status_code, 404)

    def test_template_keeps_a_written_text_body(self):
        made = self.template("<p>Hello</p>", text="Write to us at 555-0100.")
        self.assertEqual(made["text"], "Write to us at 555-0100.")
        res = self.w.client.patch(f"{API}/campaigns/templates/{made['id']}", headers=self.marketing_h,
                                  json={"preheader": "  A grey line  "})
        self.assertEqual(res.json()["preheader"], "A grey line")
        self.assertEqual(res.json()["text"], "Write to us at 555-0100.")  # untouched: only the preheader changed
        res = self.w.client.patch(f"{API}/campaigns/templates/{made['id']}", headers=self.marketing_h,
                                  json={"preheader": ""})
        self.assertIsNone(res.json()["preheader"])  # an explicitly emptied preheader is cleared

    def test_template_names_are_unique_and_merge_fields_checked(self):
        first = self.template()
        res = self.save_template(name=first["name"].upper(), subject="x", html="<p>y</p>")
        self.assertEqual(res.status_code, 409, res.text)

        res = self.save_template(name="   ")
        self.assertEqual(res.status_code, 422, res.text)

        res = self.save_template(html="<p>Hi {{ customer.nickname }}</p>")
        self.assertEqual(res.status_code, 422, res.text)
        self.assertIn("Could not render", res.json()["detail"])

        res = self.save_template(html="<p>{% for x in %}</p>")
        self.assertEqual(res.status_code, 422, res.text)

    def test_merge_fields_endpoint(self):
        res = self.w.client.get(f"{API}/campaigns/merge-fields", headers=self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        names = [f["name"] for f in res.json()]
        self.assertIn("customer.first_name", names)
        self.assertIn("unsubscribe_url", names)

    def test_preview_uses_the_customer_and_appends_the_footer(self):
        made = self.template("<p>Hello {{ customer.first_name }} at {{ customer.company }}.</p>")
        person = self.customer(first_name="Ada", last_name="Lovelace", company="Analytical Engines",
                               email=self.name("ada"))
        res = self.w.client.get(f"{API}/campaigns/templates/{made['id']}/preview", headers=self.marketing_h,
                                params={"customer_id": person["id"]})
        self.assertEqual(res.status_code, 200, res.text)
        rendered = res.json()
        self.assertEqual(rendered["subject"], "Hi Ada")
        self.assertIn("Hello Ada at Analytical Engines.", rendered["html"])
        self.assertIn("1 Warehouse Way, Chicago, IL", rendered["html"])
        self.assertIn("/unsubscribe?token=", rendered["html"])
        self.assertIn("Unsubscribe", rendered["text"])

    def test_preview_without_a_customer_shows_the_sample(self):
        made = self.template()
        res = self.w.client.get(f"{API}/campaigns/templates/{made['id']}/preview", headers=self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["subject"], "Hi Dana")

    def test_draft_preview_renders_unsaved_content_and_refuses_unknown_fields(self):
        path = f"{API}/campaigns/templates/preview"
        res = self.w.client.post(path, headers=self.marketing_h, json={
            "subject": "Hi {{ customer.first_name }}",
            "preheader": "For {{ customer.full_name }}",
            "html": "<p>Hello {{ customer.first_name }}.</p>",
        })
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["subject"], "Hi Dana")
        self.assertIn("Hello Dana.", res.json()["html"])
        self.assertIn("Unsubscribe", res.json()["text"])

        invalid = self.w.client.post(path, headers=self.marketing_h, json={
            "subject": "Hi {{ customer.nickname }}",
            "html": "<p>Hello</p>",
        })
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertIn("Could not render", invalid.json()["detail"])

    def test_an_empty_subject_for_a_real_customer_is_refused(self):
        # the sample has a company, so this only shows up once there is a real customer without one
        made = self.template("<p>Hello</p>", subject="{{ customer.company }}")
        person = self.customer(first_name="Solo", email=self.name("solo"))
        res = self.w.client.get(f"{API}/campaigns/templates/{made['id']}/preview", headers=self.marketing_h,
                                params={"customer_id": person["id"]})
        self.assertEqual(res.status_code, 422, res.text)
        self.assertIn("subject comes out empty", res.json()["detail"])

    def test_test_send_goes_out_with_the_rendered_subject(self):
        made = self.template("<p>Just for you, {{ customer.first_name }}.</p>")
        res = self.w.client.post(f"{API}/campaigns/templates/{made['id']}/test", headers=self.marketing_h,
                                 json={"to": self.name("me")})
        self.assertEqual(res.status_code, 202, res.text)
        sent = self.w.mail.sent[-1]
        self.assertEqual(sent.subject, "Hi Dana")
        self.assertIn("Just for you, Dana.", sent.html or "")
        self.assertIn("Unsubscribe", sent.text)

    def test_permissions(self):
        made = self.template()
        self.assertEqual(self.w.client.get(f"{API}/campaigns/templates", headers=self.ro_h).status_code, 200)
        # campaigns are marketing's: sales has no campaigns:view at all
        self.assertEqual(self.w.client.get(f"{API}/campaigns/templates", headers=self.sales_h).status_code, 403)
        # read-only may look but not write
        self.assertEqual(self.save_template(headers=self.ro_h).status_code, 403)
        res = self.w.client.patch(f"{API}/campaigns/templates/{made['id']}", headers=self.ro_h, json={"subject": "x"})
        self.assertEqual(res.status_code, 403)
        # and read-only may not send a test either
        res = self.w.client.post(f"{API}/campaigns/templates/{made['id']}/test", headers=self.ro_h,
                                 json={"to": self.name("me")})
        self.assertEqual(res.status_code, 403)

    # ---- suppression list ---------------------------------------------------------------------
    def test_suppression_list_lifecycle(self):
        email = self.name("bounced")
        res = self.suppress(email.upper(), reason="bounced", note="Mailbox does not exist")
        self.assertEqual(res.status_code, 201, res.text)
        row = res.json()
        self.assertEqual(row["email"], email.lower())  # stored lower-case
        self.assertEqual(row["reason"], "bounced")
        self.assertIn(row["source"], ("staff", None))

        res = self.suppress(email)
        self.assertEqual(res.status_code, 409, res.text)

        listing = self.w.client.get(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                    params={"q": email, "reason": "bounced"}).json()
        self.assertEqual([x["id"] for x in listing["items"]], [row["id"]])
        self.assertEqual(self.w.client.get(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                           params={"q": email, "reason": "manual"}).json()["items"], [])

        res = self.w.client.delete(f"{API}/campaigns/suppressions/{row['id']}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 204, res.text)
        self.assertEqual(self.w.client.get(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                           params={"q": email}).json()["items"], [])

        # adding it back restores the same row
        res = self.suppress(email, reason="complained", note="Marked as spam")
        self.assertEqual(res.status_code, 201, res.text)
        self.assertEqual(res.json()["id"], row["id"])
        self.assertEqual(res.json()["reason"], "complained")

    def test_suppressed_lookup_used_by_the_sender(self):
        from app.modules.campaigns.service import CampaignService

        email = self.name("optout")
        self.assertEqual(self.suppress(email, reason="unsubscribed").status_code, 201)
        result = run(lambda s: CampaignService(s).suppressed([email.upper(), self.name("other")]))
        self.assertEqual(result, {email.lower()})
        self.assertTrue(run(lambda s: CampaignService(s).is_suppressed(email.upper())))
        self.assertFalse(run(lambda s: CampaignService(s).is_suppressed(self.name("other"))))

    def test_suppression_permissions(self):
        self.assertEqual(self.w.client.get(f"{API}/campaigns/suppressions", headers=self.sales_h).status_code, 403)
        res = self.w.client.post(f"{API}/campaigns/suppressions", headers=self.ro_h,
                                 json={"email": self.name("x"), "reason": "manual"})
        self.assertEqual(res.status_code, 403)
