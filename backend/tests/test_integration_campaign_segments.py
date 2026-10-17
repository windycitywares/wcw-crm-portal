"""Campaign segments: audiences defined by rules instead of by hand.

The rules are a closed vocabulary that compiles to a query over the customers (see `segments.py`), so a
segment is always current: nobody is put on it, and a customer who stops matching simply falls out of it.

Checking a rule set needs no database, so those tests always run; the rest needs PostgreSQL.
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.support import API, World, reset_limits, run, skip_unless_db


class SegmentRuleTests(unittest.TestCase):
    """Reading and checking rules — everything that happens before any SQL runs."""

    def setUp(self):
        from app.modules.campaigns import segments

        self.segments = segments

    def test_a_rule_set_is_read_and_filled_in(self):
        parsed = self.segments.parse({"match": "any", "rules": [
            {"field": "orders_count", "op": "gte", "value": 2},
            {"field": "owner_id", "op": "none"},
        ]})
        self.assertEqual(parsed.match, "any")
        self.assertEqual(parsed.rules[0].value, 2)
        self.assertIsNone(parsed.rules[1].value)  # "is nobody" carries no value
        # a rule set with no `match` means every rule has to hold
        self.assertEqual(self.segments.parse({"rules": [
            {"field": "tags", "op": "has_any", "value": [1]}]}).match, "all")

    def test_the_vocabulary_is_described_for_the_editor(self):
        fields = {field["field"]: field for field in self.segments.fields()}
        self.assertEqual(len(fields), len(self.segments.FIELDS))
        self.assertEqual(fields["tags"]["value_kind"], "tags")
        self.assertEqual([op["op"] for op in fields["last_order_at"]["ops"]],
                         ["within_days", "not_within_days", "never"])
        self.assertEqual(fields["last_order_at"]["ops"][0]["label"], "in the last … days")
        # every op the module knows is offered by some field, and no field offers a stranger
        offered = {op["op"] for field in self.segments.fields() for op in field["ops"]}
        self.assertEqual(offered, set(self.segments.OPS))

    def test_odd_rules_are_refused(self):
        from app.core.exceptions import ValidationFailedError

        cases = [
            {},  # nothing at all
            {"rules": []},  # no rules: that would be every customer
            {"match": "some", "rules": [{"field": "status", "op": "is", "value": "active"}]},  # all or any
            {"rules": [{"field": "nonsense", "op": "is", "value": 1}]},  # not a field
            {"rules": [{"field": "orders_count", "op": "has_any", "value": [1]}]},  # op from another field
            {"rules": [{"field": "status", "op": "is", "value": "archived"}]},  # not a status
            {"rules": [{"field": "marketing_consent", "op": "is", "value": "yes"}]},  # not a yes/no
            {"rules": [{"field": "tags", "op": "has_any", "value": []}]},  # nothing picked
            {"rules": [{"field": "tags", "op": "has_any", "value": ["2"]}]},  # ids, not names
            {"rules": [{"field": "tags", "op": "has_any", "value": list(range(1, 61))}]},  # too many at once
            {"rules": [{"field": "orders_count", "op": "gte", "value": -1}]},  # counts are not negative
            {"rules": [{"field": "orders_count", "op": "gte", "value": "three"}]},  # a whole number
            {"rules": [{"field": "total_spent", "op": "gte", "value": "lots"}]},  # an amount
            {"rules": [{"field": "last_order_at", "op": "within_days", "value": 0}]},  # at least a day
            {"rules": [{"field": "last_order_at", "op": "within_days", "value": 99999}]},  # at most ten years
            {"rules": [{"field": "status", "op": "is", "value": "active"}] * 21},  # too many rules
        ]
        for rules in cases:
            with self.subTest(rules=str(rules)[:70]):
                with self.assertRaises(ValidationFailedError):
                    self.segments.parse(rules)

    def test_every_field_and_op_compiles_to_a_query(self):
        """A smoke test that the whole vocabulary builds SQL — no database needed to see the statement."""
        samples = {
            "customer_type": [("in", ["retail"]), ("not_in", ["marketplace"])],
            "source": [("in", ["etsy"])],
            "status": [("is", "active")],
            "tags": [("has_any", [1, 2]), ("has_all", [1, 2]), ("has_none", [1])],
            "owner_id": [("in", [1]), ("none", None)],
            "orders_count": [("gte", 2), ("lte", 10), ("eq", 0)],
            "total_spent": [("gte", 500.25), ("lte", 20)],
            "last_order_at": [("within_days", 30), ("not_within_days", 90), ("never", None)],
            "created_at": [("within_days", 7), ("not_within_days", 365)],
            "marketing_consent": [("is", True)],
        }
        seen = set()
        for field, pairs in samples.items():
            for op, value in pairs:
                rules = {"rules": [{"field": field, "op": op, "value": value}]}
                self.assertIn("customers", str(self.segments.members_stmt(rules, q="ada")), f"{field} {op}")
                self.assertIn("count", str(self.segments.count_stmt(rules, reachable=True)), f"{field} {op}")
                seen.add(op)
        self.assertEqual(seen, set(self.segments.OPS))


@skip_unless_db
class SegmentTests(unittest.TestCase):
    """A segment is asked about rather than filled, so these tests change the customers and look again."""

    _tags: int = 0

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

    def tag_name(self, label: str = "tag") -> str:
        """A tag name nothing else in the database uses (tags are unique by name)."""
        type(self)._tags += 1
        return f"seg-{label}-{self.w.sfx}-{self._tags}"

    def customer(self, **data) -> dict:
        data.setdefault("first_name", "Pat")
        data.setdefault("email", self.name("customer"))
        res = self.w.client.post(f"{API}/customers", headers=self.admin_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def tag(self, customer_id: int, *names: str) -> dict[str, int]:
        res = self.w.client.put(f"{API}/entities/customer/{customer_id}/tags", headers=self.marketing_h,
                                json={"names": list(names)})
        self.assertEqual(res.status_code, 200, res.text)
        return {tag["name"]: tag["id"] for tag in res.json()}

    def poke(self, customer_id: int, **columns) -> None:
        """Order count, spend and last-order date come from the shop sync, so a test sets them directly."""
        from app.modules.customers.models import Customer

        async def touch(session):
            row = await session.get(Customer, customer_id)
            for key, value in columns.items():
                setattr(row, key, value)

        run(touch)

    def make_segment(self, rules: dict, **data) -> dict:
        data.setdefault("name", self.name("segment"))
        data.setdefault("kind", "segment")
        data["rules"] = rules
        res = self.w.client.post(f"{API}/campaigns/lists", headers=self.marketing_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def get_segment(self, list_id: int) -> dict:
        res = self.w.client.get(f"{API}/campaigns/lists/{list_id}", headers=self.marketing_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def members(self, list_id: int, **params) -> dict:
        res = self.w.client.get(f"{API}/campaigns/lists/{list_id}/members", headers=self.marketing_h,
                                params={"page_size": 200, **params})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def matched(self, list_id: int) -> list[int]:
        """Customer ids the segment matches, in the order the API lists them (name, then id)."""
        return [member["customer_id"] for member in self.members(list_id)["items"]]

    def consent(self, customer_id: int, consent: bool) -> None:
        res = self.w.client.patch(f"{API}/customers/{customer_id}", headers=self.admin_h,
                                  json={"marketing_consent": consent})
        self.assertEqual(res.status_code, 200, res.text)

    def suppress(self, email: str) -> None:
        res = self.w.client.post(f"{API}/campaigns/suppressions", headers=self.marketing_h,
                                 json={"email": email, "reason": "unsubscribed"})
        self.assertEqual(res.status_code, 201, res.text)

    @staticmethod
    def ago(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)

    # ---- the rules ----------------------------------------------------------------------------
    def test_a_segment_stays_current_by_itself(self):
        how = self.tag_name("regulars")
        keen = self.customer(marketing_consent=True)
        quiet = self.customer(marketing_consent=True)
        self.customer(marketing_consent=True)  # never tagged, so the rule can only see this test's customers
        tag_id = self.tag(keen["id"], how)[how]
        self.tag(quiet["id"], how)

        made = self.make_segment({"match": "all", "rules": [
            {"field": "tags", "op": "has_any", "value": [tag_id]},
            {"field": "orders_count", "op": "gte", "value": 2},
        ]}, description="Customers who order often")
        self.assertEqual(made["kind"], "segment")
        self.assertEqual((made["members"], made["reachable"]), (0, 0))
        # the rules come back with the list, so the editor can load and change them
        self.assertEqual(made["rules"]["rules"][1]["value"], 2)

        self.poke(keen["id"], orders_count=3)
        self.assertEqual(self.matched(made["id"]), [keen["id"]])
        self.assertEqual(self.get_segment(made["id"])["reachable"], 1)
        self.assertIsNone(self.members(made["id"])["items"][0]["added_at"])  # nobody was added: they match

        # nobody puts the second customer on the list — placing a second order is enough
        self.poke(quiet["id"], orders_count=2)
        self.assertEqual(sorted(self.matched(made["id"])), sorted([keen["id"], quiet["id"]]))
        self.assertEqual(self.get_segment(made["id"])["members"], 2)

        # and they fall out of it again when they stop matching
        self.poke(quiet["id"], orders_count=1)
        self.assertEqual(self.matched(made["id"]), [keen["id"]])

        res = self.w.client.delete(f"{API}/customers/{keen['id']}", headers=self.admin_h)
        self.assertEqual(res.status_code, 204, res.text)
        self.assertEqual((self.get_segment(made["id"])["members"], self.get_segment(made["id"])["reachable"]), (0, 0))
        self.assertEqual(self.matched(made["id"]), [])

    def test_people_are_picked_by_what_they_spent_and_when_they_ordered(self):
        how = self.tag_name("spenders")
        big = self.customer(marketing_consent=True)
        small = self.customer(marketing_consent=True)
        quiet = self.customer(marketing_consent=True)  # never ordered
        tags = self.tag(big["id"], how)
        self.tag(small["id"], how)
        self.tag(quiet["id"], how)
        self.poke(big["id"], orders_count=5, total_spent=Decimal("620.00"), last_order_at=self.ago(10))
        self.poke(small["id"], orders_count=1, total_spent=Decimal("18.50"), last_order_at=self.ago(400))
        tag_rule = {"field": "tags", "op": "has_any", "value": [tags[how]]}

        def who(rule: dict) -> list[int]:
            return sorted(self.matched(self.make_segment({"rules": [tag_rule, rule]})["id"]))

        self.assertEqual(who({"field": "total_spent", "op": "gte", "value": 500}), [big["id"]])
        self.assertEqual(who({"field": "total_spent", "op": "lte", "value": 20}), [small["id"]])
        self.assertEqual(who({"field": "orders_count", "op": "gte", "value": 2}), [big["id"]])
        self.assertEqual(who({"field": "orders_count", "op": "eq", "value": 0}), [quiet["id"]])
        self.assertEqual(who({"field": "last_order_at", "op": "within_days", "value": 30}), [big["id"]])
        self.assertEqual(who({"field": "last_order_at", "op": "not_within_days", "value": 90}),
                         sorted([small["id"], quiet["id"]]))  # never ordered counts as "not in the last 90 days"
        self.assertEqual(who({"field": "last_order_at", "op": "never"}), [quiet["id"]])
        self.assertEqual(who({"field": "created_at", "op": "within_days", "value": 1}),
                         sorted([big["id"], small["id"], quiet["id"]]))
        self.assertEqual(who({"field": "created_at", "op": "not_within_days", "value": 365}), [])

    def test_people_are_picked_by_tags_type_status_consent_and_owner(self):
        first, second = self.tag_name("first"), self.tag_name("second")
        both = self.customer(marketing_consent=True)
        one = self.customer(marketing_consent=True)
        nobody = self.customer(marketing_consent=False)
        ids = self.tag(both["id"], first, second)
        self.tag(one["id"], first)
        self.tag(nobody["id"], first)
        self.poke(both["id"], owner_id=None)
        self.poke(nobody["id"], owner_id=None)
        self.poke(one["id"], customer_type="vip", source="etsy", status="inactive",
                  owner_id=self.marketing["id"])
        first_rule = {"field": "tags", "op": "has_any", "value": [ids[first]]}

        def who(rule: dict) -> list[int]:
            return sorted(self.matched(self.make_segment({"rules": [first_rule, rule]})["id"]))

        self.assertEqual(who({"field": "tags", "op": "has_all", "value": [ids[first], ids[second]]}), [both["id"]])
        self.assertEqual(who({"field": "tags", "op": "has_none", "value": [ids[second]]}),
                         sorted([one["id"], nobody["id"]]))
        self.assertEqual(who({"field": "customer_type", "op": "in", "value": ["vip"]}), [one["id"]])
        # "is none of" includes the customers whose type was never set
        self.assertEqual(who({"field": "customer_type", "op": "not_in", "value": ["vip"]}),
                         sorted([both["id"], nobody["id"]]))
        self.assertEqual(who({"field": "source", "op": "in", "value": ["etsy"]}), [one["id"]])
        self.assertEqual(who({"field": "status", "op": "is", "value": "inactive"}), [one["id"]])
        self.assertEqual(who({"field": "marketing_consent", "op": "is", "value": False}), [nobody["id"]])
        self.assertEqual(who({"field": "owner_id", "op": "in", "value": [self.marketing["id"]]}), [one["id"]])
        self.assertEqual(who({"field": "owner_id", "op": "none"}), sorted([both["id"], nobody["id"]]))

    def test_any_matches_one_rule_or_the_other(self):
        how = self.tag_name("either")
        tagged = self.customer(marketing_consent=True)
        mine = self.customer(marketing_consent=True)
        self.customer(marketing_consent=True)  # neither tagged nor owned by us
        tag_id = self.tag(tagged["id"], how)[how]
        self.poke(mine["id"], owner_id=self.marketing["id"])
        rules = [{"field": "tags", "op": "has_any", "value": [tag_id]},
                 {"field": "owner_id", "op": "in", "value": [self.marketing["id"]]}]

        either = self.make_segment({"match": "any", "rules": rules})
        self.assertEqual(sorted(self.matched(either["id"])), sorted([tagged["id"], mine["id"]]))

        both = self.make_segment({"match": "all", "rules": rules})
        self.assertEqual(self.matched(both["id"]), [])  # nothing is both tagged and ours yet
        self.poke(tagged["id"], owner_id=self.marketing["id"])
        self.assertEqual(self.matched(both["id"]), [tagged["id"]])

    # ---- what the audience says about its members ----------------------------------------------
    def test_the_members_listing_is_the_audience_right_now(self):
        how = self.tag_name("listing")
        ada = self.customer(first_name="Ada", last_name="Lovelace", company="Analytical Engines",
                            marketing_consent=True)
        gary = self.customer(first_name="Gary", marketing_consent=True)
        mute = self.customer(first_name="Bo", marketing_consent=True)
        blocked = self.customer(first_name="Cass", marketing_consent=True)
        tags = self.tag(ada["id"], how)
        for person in (gary, mute, blocked):
            self.tag(person["id"], how)
        made = self.make_segment({"rules": [{"field": "tags", "op": "has_any", "value": [tags[how]]}]})

        self.consent(mute["id"], False)  # agreed, then unsubscribed
        self.suppress(blocked["email"])  # on the suppression list

        page = self.members(made["id"])
        self.assertEqual(page["total"], 4)
        self.assertEqual([m["customer_id"] for m in page["items"]], [ada["id"], mute["id"], blocked["id"], gary["id"]])
        who = {m["customer_id"]: m for m in page["items"]}
        self.assertTrue(who[ada["id"]]["reachable"])
        self.assertIsNone(who[ada["id"]]["added_at"])
        self.assertTrue(who[mute["id"]]["unsubscribed"])
        self.assertFalse(who[mute["id"]]["reachable"])
        self.assertTrue(who[blocked["id"]]["suppressed"])
        self.assertFalse(who[blocked["id"]]["reachable"])
        self.assertTrue(who[gary["id"]]["reachable"])
        self.assertEqual((self.get_segment(made["id"])["members"], self.get_segment(made["id"])["reachable"]),
                         (4, 2))

        self.assertEqual([m["customer_id"] for m in self.members(made["id"], q="lovelace")["items"]], [ada["id"]])
        self.assertEqual([m["customer_id"] for m in self.members(made["id"], q="analytical")["items"]], [ada["id"]])
        self.assertEqual(self.members(made["id"], q="nobody")["total"], 0)

    # ---- what a segment refuses ----------------------------------------------------------------
    def test_a_segment_refuses_members_and_a_static_list_refuses_rules(self):
        how = self.tag_name("byhand")
        person = self.customer(marketing_consent=True)
        tag_id = self.tag(person["id"], how)[how]
        made = self.make_segment({"rules": [{"field": "tags", "op": "has_any", "value": [tag_id]}]})

        res = self.w.client.post(f"{API}/campaigns/lists/{made['id']}/members", headers=self.marketing_h,
                                 json={"customer_ids": [person["id"]]})
        self.assertEqual(res.status_code, 422, res.text)
        res = self.w.client.delete(f"{API}/campaigns/lists/{made['id']}/members/{person['id']}",
                                   headers=self.marketing_h)
        self.assertEqual(res.status_code, 422, res.text)

        # rewriting the rules is how a segment changes its mind
        res = self.w.client.patch(f"{API}/campaigns/lists/{made['id']}", headers=self.marketing_h, json={"rules": {
            "match": "all", "rules": [{"field": "tags", "op": "has_any", "value": [tag_id]},
                                      {"field": "orders_count", "op": "gte", "value": 99}]}})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.matched(made["id"]), [])
        res = self.w.client.patch(f"{API}/campaigns/lists/{made['id']}", headers=self.marketing_h,
                                  json={"rules": None})
        self.assertEqual(res.status_code, 422, res.text)  # a segment always says something

        plain = self.w.client.post(f"{API}/campaigns/lists", headers=self.marketing_h,
                                   json={"name": self.name("plain")}).json()
        res = self.w.client.post(f"{API}/campaigns/lists/{plain['id']}/members", headers=self.marketing_h,
                                 json={"customer_ids": [person["id"]]})
        self.assertEqual(res.status_code, 200, res.text)

    def test_rules_are_checked_when_the_segment_is_saved(self):
        def save(**data):
            data.setdefault("name", self.name("segment"))
            data.setdefault("kind", "segment")
            return self.w.client.post(f"{API}/campaigns/lists", headers=self.marketing_h, json=data)

        self.assertEqual(save().status_code, 422)  # a segment with no rules: not allowed
        self.assertEqual(save(rules={"rules": []}).status_code, 422)
        self.assertEqual(save(rules={"rules": [{"field": "orders", "op": "gte", "value": 2}]}).status_code, 422)
        self.assertEqual(save(rules={"rules": [{"field": "orders_count", "op": "is", "value": "many"}]}).status_code,
                         422)
        self.assertEqual(save(rules={"rules": [{"field": "orders_count", "op": "gte", "value": 2}] * 21}).status_code,
                         422)
        # the same request without the mistake is saved
        self.assertEqual(save(rules={"rules": [{"field": "orders_count", "op": "gte", "value": 2}]}).status_code, 201)

        fields = self.w.client.get(f"{API}/campaigns/segment-fields", headers=self.ro_h)
        self.assertEqual(fields.status_code, 200, fields.text)
        vocabulary = {field["field"]: field for field in fields.json()}
        self.assertIn("orders_count", vocabulary)
        self.assertEqual(vocabulary["tags"]["value_kind"], "tags")
        self.assertTrue(vocabulary["owner_id"]["ops"])
        self.assertEqual(self.w.client.get(f"{API}/campaigns/segment-fields", headers=self.sales_h).status_code, 403)
