"""Order costs from SKUs: supplier prices on the order's date, extras (+/-, %, per piece / order, supplier's or
ours), one-off adjustments, hand-typed costs left alone, and what the supplier is owed."""

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class OrderCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.admin, cls.h = cls.w.user_with_token("admin")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        types = cls.w.client.get(f"{API}/lookups/supplier_type", headers=cls.h).json()
        cls.supplier = cls.w.client.post(f"{API}/suppliers", headers=cls.h, json={
            "name": cls.w.email("cost-sup"), "supplier_type": next(t["key"] for t in types if t["is_active"])}).json()
        cls.listing_ext = int(cls.w.sfx, 16) % 10_000_000 * 100 + 8_000_000_000

        async def listing(session):
            from app.modules.channels.models import ChannelListing

            session.add(ChannelListing(channel="etsy", external_id=cls.listing_ext, title="Moon Urn - Brass", variations=[
                {"options": {"Size": "10 inch Large"}}, {"options": {"Size": "Set of 4 Keepsakes (3 inch)"}}]))
            await session.commit()

        run(listing)
        c = cls.w.client
        c.post(f"{API}/urns/setup", headers=cls.support_h)

        async def urn_id(session):
            from sqlalchemy import select

            from app.modules.channels.models import ChannelListing
            from app.modules.urns.models import Urn

            return (await session.execute(select(Urn.id).join(ChannelListing, ChannelListing.id == Urn.listing_id)
                                          .where(ChannelListing.external_id == cls.listing_ext))).scalar_one()

        cls.urn_id = run(urn_id)
        c.patch(f"{API}/urns/{cls.urn_id}", headers=cls.support_h, json={"supplier_id": cls.supplier["id"]})
        c.post(f"{API}/urns/approve", headers=cls.support_h, json={"urn_ids": [cls.urn_id]})
        old = str(date.today() - timedelta(days=60))
        for size, amount, on in (("10", "30.00", old), ("10", "40.00", None), ("3", "8.00", old)):
            c.post(f"{API}/urns/{cls.urn_id}/prices", headers=cls.h,
                   json={"size_code": size, "amount": amount} | ({"effective_from": on} if on else {}))
        for extra in (
            {"urn_id": cls.urn_id, "name": "Supplier discount", "mode": "percent", "value": "-10", "party": "supplier"},
            {"urn_id": cls.urn_id, "name": "Pouch", "value": "0.50", "size_code": "3", "party": "supplier"},
            {"urn_id": cls.urn_id, "name": "Gift box", "value": "4.00", "applies": "order", "party": "ours"},
        ):
            res = c.post(f"{API}/urns/extras", headers=cls.h, json=extra)
            assert res.status_code == 201, res.text

    def setUp(self):
        reset_limits()

    def order(self, size_value, qty=1, days_ago=1):
        n = int(self.w.sfx, 16) % 1_000_000 * 1000 + 9_000_000_000 + self._next()
        when = datetime.now(timezone.utc) - timedelta(days=days_ago)

        async def go(session):
            from app.modules.channels.models import ChannelOrder, ChannelOrderItem

            o = ChannelOrder(channel="etsy", external_id=n, ordered_at=when, paid_at=when, items_total=Decimal("200"))
            session.add(o)
            await session.flush()
            session.add(ChannelOrderItem(order_id=o.id, external_id=n, listing_external_id=self.listing_ext, title="Moon Urn",
                                         variations=[{"name": "Size", "value": size_value}], quantity=qty))
            await session.commit()
            return o.id

        return run(go)

    _n = 0

    @classmethod
    def _next(cls):
        cls._n += 1
        return cls._n

    def test_costs_extras_adjustments_and_owed(self):
        c = self.w.client
        oid = self.order("Set of 4 Keepsakes (3 inch)", qty=2)
        res = c.post(f"{API}/channels/etsy/orders/{oid}/costs/recalculate", headers=self.support_h)
        self.assertEqual(res.status_code, 200, res.text)
        live = res.json()["live"]
        # 8 pieces × $8 = 64; discount −10% = −6.40; pouch 8 × 0.50 = 4 → supplier 61.60; gift box (ours) 4.00.
        self.assertEqual((live["supplier"], live["ours"]), ("61.60", "4.00"))
        o = c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h).json()
        self.assertEqual((o["purchase_cost"], o["other_costs"], o["cost_source"]), ("61.60", "4.00", "sku"))
        self.assertEqual(o["supplier_owed"], "61.60")
        # A supplier refund lowers what they're owed; our own extra only profit.
        res = c.post(f"{API}/channels/etsy/orders/{oid}/adjustments", headers=self.support_h,
                     json={"label": "Refund for chipped lid", "amount": "-10.00", "party": "supplier", "note": "photo sent"})
        self.assertEqual(res.status_code, 200, res.text)
        adj = res.json()["adjustments"][0]
        self.assertEqual(c.post(f"{API}/channels/etsy/orders/{oid}/adjustments", headers=self.support_h,
                                json={"label": "x", "amount": "1", "note": " "}).status_code, 422)
        o = c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h).json()
        self.assertEqual(o["purchase_cost"], "51.60")
        c.delete(f"{API}/channels/etsy/orders/{oid}/adjustments/{adj['id']}", headers=self.support_h)
        self.assertEqual(c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h).json()["purchase_cost"], "61.60")

    def test_price_on_the_order_date_and_hand_typed_cost(self):
        c = self.w.client
        old = self.order("10 inch Large", days_ago=40)   # the $30 price was in force then
        new = self.order("10 inch Large", days_ago=0)
        for oid in (old, new):
            c.post(f"{API}/channels/etsy/orders/{oid}/costs/recalculate", headers=self.support_h)
        get = lambda oid: c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h).json()  # noqa: E731
        self.assertEqual(get(old)["purchase_cost"], "27.00")   # 30 − 10%
        self.assertEqual(get(new)["purchase_cost"], "36.00")   # 40 − 10%
        # A typed cost stays; the bulk preview leaves it out; adjustments wait for SKU costs.
        c.patch(f"{API}/channels/etsy/orders/{new}", headers=self.support_h, json={"purchase_cost": "33.00"})
        self.assertEqual(get(new)["cost_source"], "manual")
        preview = c.get(f"{API}/channels/etsy/costs/recalculate", headers=self.h).json()["items"]
        self.assertNotIn(new, [p["order_id"] for p in preview])
        self.assertEqual(c.post(f"{API}/channels/etsy/orders/{new}/adjustments", headers=self.support_h, json={
            "label": "x", "amount": "1", "note": "y"}).status_code, 422)
        self.assertEqual(c.get(f"{API}/channels/etsy/costs/recalculate", headers=self.support_h).status_code, 403)

    def test_unmatched_line_is_never_half_costed(self):
        c = self.w.client
        oid = self.order("Purple dragon")
        res = c.post(f"{API}/channels/etsy/orders/{oid}/costs/recalculate", headers=self.support_h)
        self.assertEqual(res.status_code, 422)
        self.assertIn("isn't matched", res.json()["detail"])
        self.assertIsNone(c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h).json()["purchase_cost"])
