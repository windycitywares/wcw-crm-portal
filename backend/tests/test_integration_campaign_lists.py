"""Campaign audiences: target lists, the customers on them, who a campaign would actually reach, and what
happens to a list when a customer is deleted or merged away."""

import unittest

from tests.support import API, World, reset_limits, skip_unless_db


@skip_unless_db
class TargetListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    # ---- helpers ------------------------------------------------------------------------------
    def name(self, label: str = "x") -> str:
        return self.w.email(label)

    def make_list(self, headers=None, **data):
        data.setdefault("name", self.name("list"))
        res = self.w.client.post(f"{API}/campaigns/lists", headers=headers or self.marketing_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def customer(self, **data):
        data.setdefault("first_name", "Pat")
        data.setdefault("email", self.name("customer"))
        res = self.w.client.post(f"{API}/customers", headers=self.admin_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def consent(self, customer_id: int, consent: bool):
        """Flipping consent on and off is how a customer ends up unsubscribed."""
        res = self.w.client.patch(f"{API}/customers/{customer_id}", headers=self.admin_h,
                                  json={"marketing_consent": consent})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def add(self, list_id: int, ids: list[int], headers=None):
        return self.w.client.post(f"{API}/campaigns/lists/{list_id}/members", headers=headers or self.marketing_h,
                                  json={"customer_ids": ids})

    def members(self, list_id: int, headers=None, **params) -> dict:
        res = self.w.client.get(f"{API}/campaigns/lists/{list_id}/members", headers=headers or self.marketing_h,
                                params={"page_size": 200, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def get_list(self, list_id: int, headers=None) -> dict:
        res = self.w.client.get(f"{API}/campaigns/lists/{list_id}", headers=headers or self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def suppress(self, email: str):
        res = self.w.client.post(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                 json={"email": email, "reason": "unsubscribed"})
        self.assertEqual(res.status_code, 201, res.text)

    # ---- the list itself ----------------------------------------------------------------------
    def test_list_round_trip(self):
        made = self.make_list(description="People who asked about wholesale")
        self.assertEqual(made["kind"], "static")
        self.assertEqual((made["members"], made["reachable"]), (0, 0))
        self.assertEqual(made["updated_by_name"], "Marketing")  # the test world's marketing user

        listing = self.w.client.get(f"{API}/campaigns/lists", headers=self.marketing_h,
                                    params={"q": made["name"]}).json()
        self.assertEqual([x["id"] for x in listing["items"]], [made["id"]])

        res = self.w.client.patch(f"{API}/campaigns/lists/{made['id']}", headers=self.marketing_h,
                                  json={"name": made["name"] + " (2026)", "description": ""})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["name"], made["name"] + " (2026)")
        self.assertIsNone(res.json()["description"])  # an emptied description is cleared

        res = self.w.client.post(f"{API}/campaigns/lists", headers=self.marketing_h,
                                 json={"name": made["name"] + " (2026)"})
        self.assertEqual(res.status_code, 409, res.text)

        res = self.w.client.delete(f"{API}/campaigns/lists/{made['id']}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 204, res.text)
        self.assertEqual(self.w.client.get(f"{API}/campaigns/lists/{made['id']}",
                                           headers=self.marketing_h).status_code, 404)

    def test_segments_are_not_here_yet(self):
        res = self.w.client.post(f"{API}/campaigns/lists", headers=self.marketing_h,
                                 json={"name": self.name("segment"), "kind": "segment"})
        self.assertEqual(res.status_code, 422, res.text)

    # ---- members ------------------------------------------------------------------------------
    def test_members_add_remove_and_who_is_reachable(self):
        made = self.make_list()
        agreed = self.customer(marketing_consent=True)
        never = self.customer(marketing_consent=False)
        opted_out = self.customer(marketing_consent=True)
        self.consent(opted_out["id"], False)  # agreed, then unsubscribed

        res = self.add(made["id"], [agreed["id"], never["id"], opted_out["id"], 99999999, agreed["id"]])
        self.assertEqual(res.status_code, 200, res.text)
        # the duplicate is counted once, the missing id is reported rather than added
        self.assertEqual(res.json(), {"added": 3, "already": 0, "missing": 1, "total": 3})

        again = self.add(made["id"], [agreed["id"], 99999999])
        self.assertEqual(again.json(), {"added": 0, "already": 1, "missing": 1, "total": 3})

        page = self.members(made["id"])
        self.assertEqual(page["total"], 3)
        who = {m["customer_id"]: m for m in page["items"]}
        self.assertTrue(who[agreed["id"]]["reachable"])
        self.assertFalse(who[never["id"]]["reachable"])  # never agreed to marketing email
        self.assertFalse(who[never["id"]]["unsubscribed"])
        self.assertTrue(who[opted_out["id"]]["unsubscribed"])
        self.assertFalse(who[opted_out["id"]]["reachable"])
        self.assertIsNotNone(who[agreed["id"]]["added_at"])

        # the list says the same thing: three members, one of whom a campaign could email
        self.assertEqual((self.get_list(made["id"])["members"], self.get_list(made["id"])["reachable"]), (3, 1))

        res = self.w.client.delete(f"{API}/campaigns/lists/{made['id']}/members/{never['id']}",
                                   headers=self.marketing_h)
        self.assertEqual(res.status_code, 204, res.text)
        self.assertEqual(self.get_list(made["id"])["members"], 2)
        res = self.w.client.delete(f"{API}/campaigns/lists/{made['id']}/members/{never['id']}",
                                   headers=self.marketing_h)
        self.assertEqual(res.status_code, 404, res.text)

    def test_a_suppressed_address_is_not_reachable(self):
        made = self.make_list()
        person = self.customer(marketing_consent=True)
        self.add(made["id"], [person["id"]])
        self.assertEqual(self.get_list(made["id"])["reachable"], 1)

        self.suppress(person["email"])
        member = self.members(made["id"])["items"][0]
        self.assertTrue(member["suppressed"])
        self.assertFalse(member["reachable"])
        self.assertEqual(self.get_list(made["id"])["reachable"], 0)

    def test_members_can_be_searched(self):
        made = self.make_list()
        ada = self.customer(first_name="Ada", last_name="Lovelace", company="Analytical Engines")
        gary = self.customer(first_name="Gary", last_name="Kildall")
        self.add(made["id"], [ada["id"], gary["id"]])
        page = self.members(made["id"], q="lovelace")
        self.assertEqual([m["customer_id"] for m in page["items"]], [ada["id"]])
        self.assertEqual(page["total"], 1)
        self.assertEqual(self.members(made["id"], q="analytical")["items"][0]["customer_id"], ada["id"])
        self.assertEqual(self.members(made["id"], q="nobody")["total"], 0)

    def test_a_deleted_customer_leaves_the_list(self):
        made = self.make_list()
        person = self.customer(marketing_consent=True)
        self.add(made["id"], [person["id"]])
        self.assertEqual(self.get_list(made["id"])["members"], 1)

        res = self.w.client.delete(f"{API}/customers/{person['id']}", headers=self.admin_h)
        self.assertEqual(res.status_code, 204, res.text)
        self.assertEqual(self.get_list(made["id"])["members"], 0)
        self.assertEqual(self.members(made["id"])["items"], [])

    def test_merging_a_customer_keeps_their_lists(self):
        """The duplicate's memberships move to the record that stayed, once each (M2's merge event)."""
        lists = [self.make_list() for _ in range(2)]
        keep = self.customer(first_name="Keep")
        gone = self.customer(first_name="Gone")
        self.add(lists[0]["id"], [gone["id"]])  # only the record that goes away is on this one
        self.add(lists[1]["id"], [keep["id"], gone["id"]])  # both are on this one

        res = self.w.client.post(f"{API}/customers/{keep['id']}/merge", headers=self.admin_h,
                                 json={"other_id": gone["id"]})
        self.assertEqual(res.status_code, 200, res.text)

        self.assertEqual([m["customer_id"] for m in self.members(lists[0]["id"])["items"]], [keep["id"]])
        self.assertEqual([m["customer_id"] for m in self.members(lists[1]["id"])["items"]], [keep["id"]])

    # ---- permissions --------------------------------------------------------------------------
    def test_permissions(self):
        made = self.make_list()
        self.assertEqual(self.w.client.get(f"{API}/campaigns/lists", headers=self.ro_h).status_code, 200)
        self.assertEqual(self.w.client.get(f"{API}/campaigns/lists", headers=self.sales_h).status_code, 403)
        res = self.w.client.post(f"{API}/campaigns/lists", headers=self.ro_h, json={"name": self.name("x")})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.add(made["id"], [1], headers=self.ro_h).status_code, 403)
