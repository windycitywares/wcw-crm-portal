"""Sales: pipelines + stages (admin), deals own-vs-any + assign, stage moves decide won/lost,
board + forecast summary, customer timeline, delete guards, lookup validation."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class SalesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())  # lead_source / lost_reason values
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.sales2, cls.sales2_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")
        cls.customer = cls.w.client.post(f"{API}/customers", headers=cls.manager_h, json={
            "first_name": "Dana", "last_name": "Deal", "email": cls.w.email("dana")}).json()

    def setUp(self):
        reset_limits()
        self.pipeline = self.make_pipeline()
        self.stages = {s["name"]: s for s in self.pipeline["stages"]}

    # ---- helpers ------------------------------------------------------------------------------
    def name(self, label: str = "board") -> str:
        return self.w.email(label)  # unique, so tests never clash with leftover rows

    def make_pipeline(self, name: str | None = None, **data):
        res = self.w.client.post(f"{API}/sales/pipelines", headers=self.manager_h,
                                 json={"name": name or self.name(), "is_default": True, **data})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def deal(self, headers=None, **data):
        data.setdefault("title", f"Deal {self.name('t')}")
        res = self.w.client.post(f"{API}/sales/deals", headers=headers or self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def patch(self, deal_id: int, headers=None, **data):
        return self.w.client.patch(f"{API}/sales/deals/{deal_id}", headers=headers or self.sales_h, json=data)

    def ids(self, headers=None, **params) -> list[int]:
        res = self.w.client.get(f"{API}/sales/deals", headers=headers or self.sales_h,
                                params={"page_size": 200, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return [d["id"] for d in res.json()["items"]]

    def titles(self, entity_type: str, entity_id: int, headers=None) -> list[str]:
        res = self.w.client.get(f"{API}/entities/{entity_type}/{entity_id}/timeline",
                                headers=headers or self.sales_h, params={"page_size": 200})
        self.assertEqual(res.status_code, 200, res.text)
        return [a["title"] for a in res.json()["items"]]

    def column(self, board: dict, stage: str) -> dict:
        return next(c for c in board["stages"] if c["stage"]["name"] == stage)

    # ---- tests --------------------------------------------------------------------------------
    def test_pipeline_and_stage_admin(self):
        # setting boards up is an admin/manager job, not a salesperson's
        self.assertEqual(self.w.client.post(f"{API}/sales/pipelines", headers=self.sales_h,
                                           json={"name": self.name()}).status_code, 403)
        self.assertEqual([s["name"] for s in self.pipeline["stages"]],
                         ["New", "Qualified", "Proposal", "Negotiation", "Won", "Lost"])
        self.assertTrue(self.pipeline["is_default"])
        self.assertEqual([s["position"] for s in self.pipeline["stages"]], [0, 1, 2, 3, 4, 5])
        self.assertEqual([s["probability"] for s in self.pipeline["stages"]], [10, 30, 50, 70, 100, 0])
        self.assertTrue(self.stages["Won"]["is_won"])
        self.assertTrue(self.stages["Lost"]["is_lost"])
        self.assertFalse(self.stages["New"]["is_won"] or self.stages["New"]["is_lost"])

        # a new stage goes to the end; a theme tone is accepted, a made-up colour isn't
        added = self.w.client.post(f"{API}/sales/pipelines/{self.pipeline['id']}/stages", headers=self.manager_h,
                                   json={"name": "On hold", "probability": 20, "color": "info"})
        self.assertEqual(added.status_code, 201, added.text)
        self.assertEqual((added.json()["position"], added.json()["probability"]), (6, 20))
        self.assertEqual(self.w.client.post(f"{API}/sales/pipelines/{self.pipeline['id']}/stages",
                                           headers=self.manager_h,
                                           json={"name": "Odd", "color": "chartreuse"}).status_code, 422)
        # a stage can't be both the won and the lost column
        self.assertEqual(self.w.client.patch(
            f"{API}/sales/pipelines/{self.pipeline['id']}/stages/{self.stages['Won']['id']}",
            headers=self.manager_h, json={"is_won": True, "is_lost": True}).status_code, 422)

        # renames stick; two pipelines can't share a name
        renamed = self.w.client.patch(f"{API}/sales/pipelines/{self.pipeline['id']}", headers=self.manager_h,
                                      json={"name": "Custom orders"})
        self.assertEqual((renamed.status_code, renamed.json()["name"]), (200, "Custom orders"))
        self.assertEqual(self.w.client.post(f"{API}/sales/pipelines", headers=self.manager_h,
                                           json={"name": "Custom orders"}).status_code, 422)
        # anyone who can see sales can read the boards
        listing = self.w.client.get(f"{API}/sales/pipelines", headers=self.ro_h)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertTrue(any(p["id"] == self.pipeline["id"] for p in listing.json()))

    def test_deal_defaults_customer_and_timeline(self):
        d = self.deal(customer_id=self.customer["id"])
        # with no stage given it lands on the first stage of the default pipeline and takes its odds
        self.assertEqual((d["stage_id"], d["stage_name"], d["pipeline_name"]),
                         (self.stages["New"]["id"], "New", self.pipeline["name"]))
        self.assertEqual((d["status"], d["probability"], d["owner_id"]), ("open", 10, self.sales["id"]))
        self.assertEqual((float(d["value"]), d["currency"], float(d["weighted_value"])), (0.0, "USD", 0.0))
        self.assertIsNone(d["closed_at"])
        self.assertIn("Dana", d["customer_name"])
        self.assertEqual(d["owner_name"], "Sales")  # the salesperson's name, from the user directory
        # the deal is on the customer's timeline and has its own
        self.assertIn(f"Deal opened: {d['title']}", self.titles("customer", self.customer["id"]))
        self.assertIn(f"Deal opened: {d['title']}", self.titles("deal", d["id"]))
        # and it can be found by title and filtered by stage
        self.assertIn(d["id"], self.ids(q=d["title"][:20], stage_id=self.stages["New"]["id"]))
        self.assertIn(d["id"], self.ids(view="mine"))
        self.assertEqual(self.w.client.post(f"{API}/sales/deals", headers=self.sales_h,
                                           json={"title": "  "}).status_code, 422)

    def test_own_vs_any_and_assign(self):
        d = self.deal(customer_id=self.customer["id"])
        # another salesperson can't touch it; a manager can
        self.assertEqual(self.patch(d["id"], self.sales2_h, title="Hijacked").status_code, 403)
        self.assertEqual(self.patch(d["id"], self.manager_h, title="Manager edit").status_code, 200)
        # only managers hand a deal to someone else
        self.assertEqual(self.w.client.post(f"{API}/sales/deals", headers=self.sales_h,
                                           json={"title": self.name("t"), "owner_id": self.sales2["id"]}).status_code,
                         403)
        given = self.deal(headers=self.manager_h, owner_id=self.sales2["id"])
        self.assertEqual(given["owner_id"], self.sales2["id"])
        # the owner works it; the other salesperson still can't
        self.assertEqual(self.patch(given["id"], self.sales2_h, value="250").status_code, 200)
        self.assertNotIn(given["id"], self.ids(view="mine"))
        self.assertIn(given["id"], self.ids(view="all"))
        # read-only sees the board but changes nothing
        self.assertEqual(self.w.client.get(f"{API}/sales/deals", headers=self.ro_h).status_code, 200)
        self.assertEqual(self.w.client.post(f"{API}/sales/deals", headers=self.ro_h,
                                           json={"title": self.name("t")}).status_code, 403)
        self.assertEqual(self.patch(d["id"], self.ro_h, title="x").status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/sales/deals/{d['id']}", headers=self.ro_h).status_code, 403)

    def test_stage_move_sets_the_outcome(self):
        d = self.deal(value="1200.00", expected_close_on="2026-11-30")
        won = self.patch(d["id"], stage_id=self.stages["Won"]["id"])
        self.assertEqual(won.status_code, 200, won.text)
        self.assertEqual((won.json()["status"], won.json()["probability"]), ("won", 100))
        self.assertIsNotNone(won.json()["closed_at"])
        self.assertEqual(float(won.json()["weighted_value"]), 1200.0)
        self.assertEqual(won.json()["expected_close_on"], "2026-11-30")
        # losing it keeps the reason
        lost = self.patch(d["id"], stage_id=self.stages["Lost"]["id"], lost_reason="price").json()
        self.assertEqual((lost["status"], lost["lost_reason"], lost["probability"]), ("lost", "price", 0))
        # a won deal isn't a lost one
        self.assertEqual(self.patch(d["id"], stage_id=self.stages["Won"]["id"]).json()["lost_reason"], None)
        # back to work: open again, no close date
        again = self.patch(d["id"], stage_id=self.stages["Qualified"]["id"]).json()
        self.assertEqual((again["status"], again["closed_at"], again["probability"]), ("open", None, 30))
        titles = self.titles("deal", d["id"])
        self.assertIn(f"Deal won: {d['title']}", titles)
        self.assertIn(f"Deal lost: {d['title']}", titles)
        self.assertTrue(any("moved to Qualified" in t for t in titles))
        # a made-up stage or reason is refused
        self.assertEqual(self.patch(d["id"], stage_id=99_999_999).status_code, 404)
        self.assertEqual(self.patch(d["id"], lost_reason="weather").status_code, 422)

    def test_board_and_forecast(self):
        before = self.w.client.get(f"{API}/sales/summary", headers=self.sales_h).json()
        d = self.deal(value="400.00")
        board = self.w.client.get(f"{API}/sales/board", headers=self.sales_h,
                                  params={"pipeline_id": self.pipeline["id"]}).json()
        self.assertEqual((board["pipeline_id"], board["pipeline_name"]), (self.pipeline["id"], self.pipeline["name"]))
        self.assertEqual([c["stage"]["name"] for c in board["stages"]],
                         ["New", "Qualified", "Proposal", "Negotiation", "Won", "Lost"])
        new = self.column(board, "New")
        self.assertIn(d["id"], [x["id"] for x in new["deals"]])
        self.assertEqual((float(new["total_value"]), float(new["weighted_value"])), (400.0, 40.0))
        after = self.w.client.get(f"{API}/sales/summary", headers=self.sales_h).json()
        self.assertEqual(after["open_count"], before["open_count"] + 1)
        self.assertAlmostEqual(float(after["open_value"]) - float(before["open_value"]), 400.0, places=2)
        self.assertAlmostEqual(float(after["weighted_value"]) - float(before["weighted_value"]), 40.0, places=2)
        # winning it takes it off the board and into the month's numbers
        self.patch(d["id"], stage_id=self.stages["Won"]["id"])
        board = self.w.client.get(f"{API}/sales/board", headers=self.sales_h,
                                  params={"pipeline_id": self.pipeline["id"]}).json()
        self.assertEqual(float(self.column(board, "New")["total_value"]), 0.0)
        self.assertNotIn(d["id"], [x["id"] for x in self.column(board, "New")["deals"]])
        won = self.w.client.get(f"{API}/sales/summary", headers=self.sales_h).json()
        self.assertEqual(won["won_count"], after["won_count"] + 1)
        self.assertAlmostEqual(float(won["won_value"]) - float(after["won_value"]), 400.0, places=2)

    def test_delete_guards(self):
        d = self.deal()
        first = self.stages["New"]["id"]
        # a board or a stage with open deals can't be removed
        self.assertEqual(self.w.client.delete(f"{API}/sales/pipelines/{self.pipeline['id']}/stages/{first}",
                                             headers=self.manager_h).status_code, 422)
        self.assertEqual(self.w.client.delete(f"{API}/sales/pipelines/{self.pipeline['id']}",
                                             headers=self.manager_h).status_code, 422)
        # the owner removes their deal; it's gone from the board and the list
        self.assertEqual(self.w.client.delete(f"{API}/sales/deals/{d['id']}", headers=self.sales_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/sales/deals/{d['id']}", headers=self.sales_h).status_code, 404)
        self.assertEqual(self.w.client.delete(f"{API}/sales/deals/{d['id']}", headers=self.sales_h).status_code, 404)
        self.assertNotIn(d["id"], self.ids())
        self.assertEqual(self.w.client.delete(f"{API}/sales/pipelines/{self.pipeline['id']}/stages/{first}",
                                             headers=self.manager_h).status_code, 204)
        self.assertEqual(self.w.client.delete(f"{API}/sales/pipelines/{self.pipeline['id']}",
                                             headers=self.manager_h).status_code, 204)
        remaining = self.w.client.get(f"{API}/sales/pipelines", headers=self.manager_h).json()
        self.assertNotIn(self.pipeline["id"], [p["id"] for p in remaining])

    def test_custom_fields_and_lookups(self):
        self.assertEqual(self.w.client.post(f"{API}/sales/deals", headers=self.sales_h,
                                           json={"title": self.name("t"), "source": "carrier pigeon"}).status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/sales/deals", headers=self.sales_h,
                                           json={"title": self.name("t"), "value": "-5"}).status_code, 422)
        d = self.deal(source="referral", probability=42)
        self.assertEqual((d["source"], d["probability"]), ("referral", 42))
        self.assertIn(d["id"], self.ids(status="all", q=d["title"][:20]))
