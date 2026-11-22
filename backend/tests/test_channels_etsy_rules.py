"""Etsy rules with no database or network: profit, statuses, OAuth, parsing Etsy's JSON, attention, payments."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.channels.etsy import profit as p
from app.modules.channels.etsy import status as s


class ProfitTests(unittest.TestCase):
    def test_revenue_excludes_tax_and_subtracts_discounts(self):
        self.assertEqual(p.revenue("30.00", "5.00", "2.50"), Decimal("32.50"))

    def test_net_and_margin(self):
        r = p.compute(items_total=30, shipping_charged=5, discounts=0, purchase_cost=12, shipping_cost=4, etsy_fees=3.5)
        self.assertEqual(r.total_cost, Decimal("19.50"))
        self.assertEqual(r.net_profit, Decimal("15.50"))
        self.assertEqual(r.margin_pct, Decimal("44.29"))
        self.assertEqual(r.missing, ())

    def test_missing_figures_are_reported_not_guessed(self):
        r = p.compute(items_total=20, shipping_charged=0, discounts=0, purchase_cost=8)
        self.assertEqual(r.missing, ("shipping_cost", "etsy_fees"))
        self.assertEqual(r.net_profit, Decimal("12.00"))

    def test_replacements_and_refunds_reduce_profit(self):
        r = p.compute(items_total=20, shipping_charged=0, discounts=0, purchase_cost=8, shipping_cost=3, etsy_fees=2, extra_costs=11)
        self.assertEqual(r.net_profit, Decimal("-4.00"))

    def test_zero_revenue_has_no_margin(self):
        self.assertIsNone(p.compute(items_total=0, shipping_charged=0, discounts=0).margin_pct)

    def test_days_to_ship(self):
        a = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.assertEqual(p.days_to_ship(a, datetime(2026, 11, 4, 5, tzinfo=timezone.utc)), 3)
        self.assertIsNone(p.days_to_ship(a, None))


class StatusTests(unittest.TestCase):
    def test_implied(self):
        self.assertEqual(s.etsy_status(canceled=False, shipped=False, delivered=False), s.NEW)
        self.assertEqual(s.etsy_status(canceled=False, shipped=True, delivered=False), s.SHIPPED)
        self.assertEqual(s.etsy_status(canceled=False, shipped=True, delivered=True), s.DELIVERED)
        self.assertEqual(s.etsy_status(canceled=True, shipped=True, delivered=True), s.CANCELLED)

    def test_sync_moves_forward_only(self):
        self.assertEqual(s.sync_target(s.NEW, s.SHIPPED), s.SHIPPED)
        self.assertEqual(s.sync_target(s.PURCHASED, s.NEW), s.PURCHASED)
        self.assertEqual(s.sync_target(s.DELIVERED, s.SHIPPED), s.DELIVERED)

    def test_sync_leaves_team_exceptions_alone(self):
        self.assertEqual(s.sync_target(s.ISSUE, s.SHIPPED), s.ISSUE)
        self.assertEqual(s.sync_target(s.REFUNDED, s.CANCELLED), s.REFUNDED)

    def test_cancel_wins_on_open_order(self):
        self.assertEqual(s.sync_target(s.PURCHASED, s.CANCELLED), s.CANCELLED)

    def test_team_rules(self):
        self.assertTrue(s.can_set_by_team(s.NEW, s.PURCHASED))
        self.assertFalse(s.can_set_by_team(s.NEW, s.NEW))
        self.assertFalse(s.can_set_by_team(s.NEW, "bogus"))


if __name__ == "__main__":
    unittest.main()


class OAuthTests(unittest.TestCase):
    def test_pkce_challenge_matches_the_rfc_example(self):
        from app.modules.channels.etsy import oauth as o

        self.assertEqual(o.challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_authorize_url_carries_state_and_scopes(self):
        from app.modules.channels.etsy import oauth as o

        url = o.authorize_url(client_id="abc", redirect_uri="https://x.test/cb", state="st", verifier="v" * 50)
        self.assertIn("client_id=abc", url)
        self.assertIn("state=st", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("transactions_w", url)

    def test_user_id_from_token(self):
        from app.modules.channels.etsy import oauth as o

        self.assertEqual(o.user_id_from_token("12345.abcdef"), 12345)
        self.assertIsNone(o.user_id_from_token("nope"))


class ListingParseTests(unittest.TestCase):
    def test_parse(self):
        from app.modules.channels.etsy import listing as l

        raw = {
            "listing_id": 77, "title": " Mug ", "state": "active", "quantity": 4, "tags": ["mug"],
            "price": {"amount": 1999, "divisor": 100, "currency_code": "USD"}, "last_modified_timestamp": 1760000000,
            "images": [{"url_fullxfull": "https://i.etsystatic.com/a.jpg"}],
            "inventory": {"products": [{"sku": "MUG-S", "property_values": [{"property_name": "Size", "values": ["S"]}],
                                        "offerings": [{"price": {"amount": 1999, "divisor": 100, "currency_code": "USD"}, "quantity": 4, "is_enabled": True}]}]},
        }
        out = l.parse(raw)
        self.assertEqual(out["title"], "Mug")
        self.assertEqual(out["price"], Decimal("19.99"))
        self.assertEqual(out["skus"], ["MUG-S"])
        self.assertEqual(out["variations"][0]["options"], {"Size": "S"})
        self.assertEqual(out["images"], ["https://i.etsystatic.com/a.jpg"])
        self.assertEqual(out["etsy_updated_at"].year, 2025)

    def test_unknown_state_and_missing_money(self):
        from app.modules.channels.etsy import listing as l

        out = l.parse({"listing_id": 1, "state": "weird"})
        self.assertEqual(out["state"], "inactive")
        self.assertIsNone(out["price"])
        self.assertEqual(out["currency"], "USD")


class ReceiptParseTests(unittest.TestCase):
    RAW = {
        "receipt_id": 555, "status": "Paid", "is_paid": True, "is_shipped": False, "name": "Sam Buyer", "buyer_user_id": 9,
        "first_line": "1 Main St", "city": "Chicago", "state": "IL", "zip": "60601", "country_iso": "US",
        "created_timestamp": 1760000000, "message_from_buyer": "Please hurry",
        "grandtotal": {"amount": 3550, "divisor": 100, "currency_code": "USD"},
        "total_shipping_cost": {"amount": 500, "divisor": 100, "currency_code": "USD"},
        "discount_amt": {"amount": 200, "divisor": 100, "currency_code": "USD"},
        "total_tax_cost": {"amount": 250, "divisor": 100, "currency_code": "USD"},
        "transactions": [
            {"transaction_id": 1, "listing_id": 77, "title": "Mug", "quantity": 2, "price": {"amount": 1500, "divisor": 100, "currency_code": "USD"},
             "expected_ship_date": 1760500000, "variations": [{"formatted_name": "Size", "formatted_value": "L"}]},
        ],
    }

    def test_money_and_items(self):
        from app.modules.channels.etsy import receipt as r

        out = r.parse(self.RAW)
        o = out["order"]
        self.assertEqual(o["items_total"], Decimal("30.00"))
        self.assertEqual(o["shipping_charged"], Decimal("5.00"))
        self.assertEqual(o["discounts"], Decimal("2.00"))
        self.assertEqual(o["tax"], Decimal("2.50"))
        self.assertEqual(o["implied_status"], "new")
        self.assertIsNotNone(o["paid_at"])
        self.assertEqual(out["items"][0]["quantity"], 2)
        self.assertEqual(out["items"][0]["variations"], [{"name": "Size", "value": "L"}])
        self.assertEqual(o["ship_address"]["city"], "Chicago")
        self.assertIsNone(o["buyer_email"])

    def test_shipped_and_tracking(self):
        from app.modules.channels.etsy import receipt as r

        raw = {**self.RAW, "is_shipped": True, "shipments": [{"tracking_code": "9400", "carrier_name": "usps"}]}
        o = r.parse(raw)["order"]
        self.assertEqual(o["implied_status"], "shipped")
        self.assertEqual((o["etsy_tracking"], o["etsy_carrier"]), ("9400", "usps"))

    def test_refund_on_etsy_does_not_cancel(self):
        from app.modules.channels.etsy import receipt as r

        self.assertEqual(r.parse({**self.RAW, "status": "Fully Refunded"})["order"]["implied_status"], "new")

    def test_paid_and_shipped_times_come_from_etsy(self):
        from app.modules.channels.etsy import receipt as r

        t = dict(self.RAW["transactions"][0], paid_timestamp=1760000100, shipped_timestamp=1760200000)
        o = r.parse({**self.RAW, "transactions": [t]})["order"]
        self.assertEqual(int(o["paid_at"].timestamp()), 1760000100)
        self.assertEqual(int(o["etsy_shipped_at"].timestamp()), 1760200000)

    def test_canceled(self):
        from app.modules.channels.etsy import receipt as r

        self.assertEqual(r.parse({**self.RAW, "status": "Canceled"})["order"]["implied_status"], "cancelled")


class AttentionTests(unittest.TestCase):
    NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    def facts(self, **over):
        from app.modules.channels.etsy.attention import OrderFacts

        base = dict(status="new", paid_at=self.NOW, ship_by=None, purchase_cost=Decimal("5"), shipping_cost=None,
                    etsy_fees=None, items_total=Decimal("20"), shipping_charged=Decimal("0"), discounts=Decimal("0"))
        base.update(over)
        return OrderFacts(**base)

    def test_fresh_order_with_cost_is_fine(self):
        from app.modules.channels.etsy.attention import reasons

        self.assertEqual(reasons(self.facts(), self.NOW), [])

    def test_each_reason(self):
        from datetime import timedelta

        from app.modules.channels.etsy.attention import reasons

        day = timedelta(days=1)
        self.assertEqual(reasons(self.facts(paid_at=self.NOW - 2 * day), self.NOW), ["not_purchased"])
        self.assertIn("late", reasons(self.facts(status="purchased", ship_by=self.NOW - day), self.NOW))
        self.assertEqual(reasons(self.facts(purchase_cost=None), self.NOW), ["cost_missing"])
        self.assertEqual(reasons(self.facts(status="shipped"), self.NOW), ["shipping_cost_missing"])
        self.assertEqual(reasons(self.facts(purchase_cost=Decimal("25")), self.NOW), ["negative_profit"])
        self.assertEqual(reasons(self.facts(status="cancelled", purchase_cost=None), self.NOW), [])
        self.assertEqual(reasons(self.facts(status="shipped", purchase_cost=None, past_order=True), self.NOW), [])


class SupplierPaymentRuleTests(unittest.TestCase):
    def test_owed_and_status(self):
        from app.modules.channels.etsy import payments as p

        self.assertEqual(p.owed(Decimal("10"), Decimal("4.5")), Decimal("14.50"))
        self.assertEqual(p.owed(Decimal("10"), None), Decimal("10.00"))
        self.assertIsNone(p.owed(None, Decimal("4")))
        self.assertEqual(p.status(order_status="new", purchase_cost=None, paid=False), p.COST_MISSING)
        self.assertEqual(p.status(order_status="new", purchase_cost=Decimal("1"), paid=False), p.PENDING)
        self.assertEqual(p.status(order_status="cancelled", purchase_cost=Decimal("1"), paid=False), p.NOT_DUE)
        self.assertEqual(p.status(order_status="cancelled", purchase_cost=Decimal("1"), paid=True), p.SETTLED)
