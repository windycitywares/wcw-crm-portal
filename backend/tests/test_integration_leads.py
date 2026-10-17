"""Leads: create/filter/summary, own-vs-any + handover, notes and timeline on a lead, and converting one
into a customer and a deal (reusing an existing customer, atomic, one conversion only)."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class LeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())  # lead_source values
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.sales2, cls.sales2_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()
        self.pipeline = self.make_pipeline()
        self.stages = {s["name"]: s for s in self.pipeline["stages"]}

    # ---- helpers ------------------------------------------------------------------------------
    def name(self, label: str = "x") -> str:
        return self.w.email(label)  # unique, so tests never clash with leftover rows

    def make_pipeline(self, name: str | None = None, **data):
        res = self.w.client.post(f"{API}/sales/pipelines", headers=self.manager_h,
                                 json={"name": name or self.name("board"), "is_default": True, **data})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def lead(self, headers=None, **data):
        data.setdefault("email", self.name("lead"))
        res = self.w.client.post(f"{API}/leads", headers=headers or self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def patch(self, lead_id: int, headers=None, **data):
        return self.w.client.patch(f"{API}/leads/{lead_id}", headers=headers or self.sales_h, json=data)

    def convert(self, lead_id: int, headers=None, **data):
        return self.w.client.post(f"{API}/leads/{lead_id}/convert", headers=headers or self.sales_h, json=data)

    def ids(self, headers=None, **params) -> list[int]:
        res = self.w.client.get(f"{API}/leads", headers=headers or self.sales_h,
                                params={"page_size": 200, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return [x["id"] for x in res.json()["items"]]

    def summary(self, headers=None) -> dict:
        res = self.w.client.get(f"{API}/leads/summary", headers=headers or self.sales_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def titles(self, entity_type: str, entity_id: int, headers=None) -> list[str]:
        res = self.w.client.get(f"{API}/entities/{entity_type}/{entity_id}/timeline",
                                headers=headers or self.sales_h, params={"page_size": 200})
        self.assertEqual(res.status_code, 200, res.text)
        return [a["title"] for a in res.json()["items"]]

    def customer(self, headers=None, **data):
        res = self.w.client.post(f"{API}/customers", headers=headers or self.manager_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def deals(self, customer_id: int) -> list[int]:
        res = self.w.client.get(f"{API}/sales/deals", headers=self.sales_h,
                                params={"customer_id": customer_id, "status": "all", "page_size": 200})
        self.assertEqual(res.status_code, 200, res.text)
        return [d["id"] for d in res.json()["items"]]

    # ---- tests --------------------------------------------------------------------------------
    def test_create_defaults_list_filters_and_summary(self):
        made = self.lead(first_name="Ada", last_name="Ng")
        self.assertEqual(made["status"], "new")
        self.assertEqual((made["full_name"], made["display_name"]), ("Ada Ng", "Ada Ng"))
        self.assertEqual(made["owner_id"], self.sales["id"])
        self.assertEqual(made["owner_name"], "Sales")  # from the user directory
        self.assertEqual((made["custom_fields"], made["converted_at"]), ({}, None))
        self.assertIsNone(made["converted_customer_id"])

        # name, company or email — whichever is at hand
        self.assertEqual(self.lead(company="Windy Widgets Co")["display_name"], "Windy Widgets Co")
        named = self.lead(first_name="Bo", company="Bo's Bikes")
        self.assertEqual(named["display_name"], "Bo")  # the person, when there is one
        # addresses are stored lower-case, so the same person is one email
        mixed = self.lead(email="Ada.NG@Example.COM")
        self.assertEqual(mixed["email"], "ada.ng@example.com")

        # a form with nothing on it is refused, as is a made-up source or status
        self.assertEqual(self.w.client.post(f"{API}/leads", headers=self.sales_h, json={}).status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/leads", headers=self.sales_h,
                                           json={"company": "X", "source": "carrier pigeon"}).status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/leads", headers=self.sales_h,
                                           json={"company": "X", "email": "not-an-email"}).status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/leads", headers=self.sales_h,
                                           json={"company": "X", "status": "converted"}).status_code, 422)

        # the list is newest first, searchable, and filterable by status/source
        other = self.lead(company="Cobalt Studio", source="referral")
        self.assertEqual(self.ids()[0], other["id"])
        self.assertIn(other["id"], self.ids(q="cobalt"))
        self.assertIn(other["id"], self.ids(source="referral"))
        self.assertIn(other["id"], self.ids(view="mine"))
        self.assertNotIn(other["id"], self.ids(status="contacted"))
        self.assertEqual(self.patch(other["id"], status="contacted").json()["status"], "contacted")
        self.assertIn(other["id"], self.ids(status="contacted"))

        counts = self.summary()
        self.assertGreaterEqual(counts["new"], 1)
        self.assertGreaterEqual(counts["contacted"], 1)
        self.assertGreaterEqual(counts["total"], 3)

    def test_own_vs_any_and_handover(self):
        lead = self.lead()
        # another salesperson can't touch it; a manager can
        self.assertEqual(self.patch(lead["id"], self.sales2_h, notes="mine now").status_code, 403)
        self.assertEqual(self.convert(lead["id"], self.sales2_h).status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/leads/{lead['id']}", headers=self.sales2_h).status_code, 403)
        self.assertEqual(self.patch(lead["id"], self.manager_h, status="qualified").status_code, 200)
        # only managers hand a lead to someone else
        self.assertEqual(self.w.client.post(f"{API}/leads", headers=self.sales_h,
                                           json={"company": "Y", "owner_id": self.sales2["id"]}).status_code, 403)
        given = self.lead(headers=self.manager_h, owner_id=self.sales2["id"])
        self.assertEqual(given["owner_id"], self.sales2["id"])
        self.assertEqual(self.patch(given["id"], self.sales2_h, notes="working it").status_code, 200)
        self.assertEqual(self.patch(given["id"], self.sales_h, notes="not mine").status_code, 403)
        self.assertNotIn(given["id"], self.ids(view="mine"))
        # read-only can look but not touch
        self.assertEqual(self.w.client.get(f"{API}/leads", headers=self.ro_h).status_code, 200)
        self.assertEqual(self.w.client.post(f"{API}/leads", headers=self.ro_h,
                                           json={"company": "Z"}).status_code, 403)
        # deleting hides it
        self.assertEqual(self.w.client.delete(f"{API}/leads/{lead['id']}", headers=self.sales_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/leads/{lead['id']}", headers=self.sales_h).status_code, 404)
        self.assertNotIn(lead["id"], self.ids())

    def test_updates_notes_and_timeline(self):
        lead = self.lead(first_name="Cass", notes="Met at the trade show")
        self.assertIn(f"Lead added: {lead['display_name']}", self.titles("lead", lead["id"]))
        # a lead is a record type, so notes work on it like on a customer
        note = self.w.client.post(f"{API}/entities/lead/{lead['id']}/notes", headers=self.sales_h,
                                  json={"body": "Called, left a message"})
        self.assertEqual(note.status_code, 201, note.text)
        # edits are audited on the timeline, in words
        changed = self.patch(lead["id"], company="Cass Woodworks", status="contacted")
        self.assertEqual((changed.status_code, changed.json()["company"]), (200, "Cass Woodworks"))
        self.assertTrue(any("Changed company, status" in t for t in self.titles("lead", lead["id"])))
        self.assertEqual(self.patch(lead["id"], source="nope").status_code, 422)
        self.assertEqual(self.w.client.patch(f"{API}/leads/99999999", headers=self.sales_h,
                                            json={"notes": "x"}).status_code, 404)

    def test_convert_makes_customer_and_deal(self):
        email = self.name("convert")
        lead = self.lead(first_name="Cara", last_name="Voss", company="Voss Woodworks", email=email,
                         phone="555-0100", source="referral", status="qualified")
        res = self.convert(lead["id"], value="1500.00", expected_close_on="2026-12-01")
        self.assertEqual(res.status_code, 200, res.text)
        converted = res.json()
        customer_id, deal_id = converted["converted_customer_id"], converted["converted_deal_id"]
        self.assertEqual(converted["status"], "converted")
        self.assertIsNotNone(converted["converted_at"])
        self.assertIsNotNone(customer_id)
        self.assertIsNotNone(deal_id)
        self.assertIn("Cara", converted["converted_customer_name"])
        self.assertEqual(converted["converted_deal_title"], "Voss Woodworks")

        # the customer carries the lead's details and follows it to the same owner
        customer = self.w.client.get(f"{API}/customers/{customer_id}", headers=self.sales_h).json()
        self.assertEqual([customer[k] for k in ("first_name", "last_name", "company", "email", "phone", "source")],
                         ["Cara", "Voss", "Voss Woodworks", email, "555-0100", "referral"])
        self.assertEqual(customer["owner_id"], self.sales["id"])
        # the deal opens on the default pipeline's first stage, in the lead's name
        deal = self.w.client.get(f"{API}/sales/deals/{deal_id}", headers=self.sales_h).json()
        self.assertEqual((deal["title"], deal["customer_id"], deal["stage_id"]), ("Voss Woodworks", customer_id,
                                                                                 self.stages["New"]["id"]))
        self.assertEqual((deal["status"], deal["owner_id"], deal["expected_close_on"]), ("open", self.sales["id"],
                                                                                        "2026-12-01"))
        self.assertEqual((float(deal["value"]), deal["currency"]), (1500.0, "USD"))
        # both timelines tell the story, and the deal shows on the customer
        self.assertTrue(any(t.startswith("Lead converted to customer") for t in self.titles("lead", lead["id"])))
        self.assertIn("Deal opened: Voss Woodworks", self.titles("customer", customer_id))

        # converting again, or taking a converted lead back out of the funnel, is refused
        self.assertEqual(self.convert(lead["id"]).status_code, 422)
        self.assertEqual(self.patch(lead["id"], status="new").status_code, 422)
        self.assertEqual(self.patch(lead["id"], notes="still editable").status_code, 200)

    def test_convert_reuses_customers_and_can_skip_the_deal(self):
        # someone already in the CRM with that email: link, don't duplicate
        email = self.name("dup")
        existing = self.customer(first_name="Existing", email=email)
        lead = self.lead(email=email, company="Reuse Co")
        converted = self.convert(lead["id"], create_deal=False).json()
        self.assertEqual(converted["converted_customer_id"], existing["id"])
        self.assertIsNone(converted["converted_deal_id"])
        # asked not to open a deal, so none is open for them
        self.assertEqual(self.deals(existing["id"]), [])

        # an explicit customer wins, and the deal can be titled and valued from the form
        picked = self.customer(first_name="Picked", email=self.name("pick"))
        lead2 = self.lead(company="Picked Co")
        converted2 = self.convert(lead2["id"], customer_id=picked["id"], deal_title="Custom order",
                                  value="99.50").json()
        self.assertEqual(converted2["converted_customer_id"], picked["id"])
        deal = self.w.client.get(f"{API}/sales/deals/{converted2['converted_deal_id']}", headers=self.sales_h).json()
        self.assertEqual((deal["title"], float(deal["value"])), ("Custom order", 99.5))
        self.assertEqual(self.deals(picked["id"]), [deal["id"]])

        # a made-up customer is refused
        self.assertEqual(self.convert(self.lead(company="Nope")["id"], customer_id=99_999_999).status_code, 404)

    def test_convert_is_atomic(self):
        email = self.name("atomic")
        lead = self.lead(email=email, company="Atomic Co")
        # the customer is built first, then the deal fails: the whole conversion rolls back
        self.assertEqual(self.convert(lead["id"], stage_id=99_999_999).status_code, 404)
        self.assertEqual(self.w.client.get(f"{API}/leads/{lead['id']}", headers=self.sales_h).json()["status"], "new")
        check = self.w.client.get(f"{API}/customers/check-email", headers=self.manager_h,
                                  params={"email": email}).json()
        self.assertFalse(check["exists"])
