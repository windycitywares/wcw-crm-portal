"""Urns: set up from Etsy listings, sizes read from variations, SKUs from the template, dated prices, extras."""

import unittest
from datetime import date, timedelta

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class UrnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.admin, cls.h = cls.w.user_with_token("admin")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        types = cls.w.client.get(f"{API}/lookups/supplier_type", headers=cls.h).json()
        cls.supplier = cls.w.client.post(f"{API}/suppliers", headers=cls.h, json={
            "name": cls.w.email("urn-sup"), "supplier_type": next(t["key"] for t in types if t["is_active"])}).json()
        cls.base = int(cls.w.sfx, 16) % 10_000_000 * 100 + 7_000_000_000

        async def listings(session):
            from app.modules.channels.models import ChannelListing

            session.add(ChannelListing(channel="etsy", external_id=cls.base + 1, title="Ocean Wave Urn - Hand painted",
                                       variations=[
                                           {"sku": None, "options": {"Size": "10 inch Large"}},
                                           {"sku": "OLD-1", "options": {"Size": "Set of 4 Keepsakes (3 inch)"}},
                                           {"sku": None, "options": {"Size": "Gift box"}},
                                       ]))
            session.add(ChannelListing(channel="etsy", external_id=cls.base + 2, title="Rose Keepsake, 3 inch",
                                       variations=[]))
            await session.commit()

        run(listings)

    def setUp(self):
        reset_limits()

    def urn_for(self, external_id):
        from sqlalchemy import select

        async def go(session):
            from app.modules.channels.models import ChannelListing
            from app.modules.urns.models import Urn

            return (await session.execute(select(Urn.id).join(ChannelListing, ChannelListing.id == Urn.listing_id)
                                          .where(ChannelListing.external_id == external_id))).scalar_one()

        return run(go)

    def test_setup_review_skus_and_prices(self):
        c, h = self.w.client, self.h
        res = c.post(f"{API}/urns/setup", headers=self.support_h)
        self.assertEqual(res.status_code, 200, res.text)
        again = c.post(f"{API}/urns/setup", headers=self.support_h).json()
        self.assertEqual(again["created"], 0)  # safe to run again
        urn_id = self.urn_for(self.base + 1)
        urn = c.get(f"{API}/urns/{urn_id}", headers=self.sales_h).json()
        self.assertEqual(urn["name"], "Ocean Wave Urn")
        by_label = {v["label"]: v for v in urn["variations"]}
        self.assertEqual(by_label["10 inch Large"]["quantities"], {"10": 1})
        self.assertEqual(by_label["Set of 4 Keepsakes (3 inch)"]["quantities"], {"3": 4})
        self.assertEqual(by_label["Set of 4 Keepsakes (3 inch)"]["etsy_sku"], "OLD-1")
        self.assertEqual(by_label["Gift box"]["state"], "unclear")
        # No SKU without a supplier and an approval.
        self.assertTrue(all(v["sku"] is None for v in urn["variations"]))
        self.assertEqual(c.patch(f"{API}/urns/{urn_id}", headers=self.sales_h, json={"name": "x"}).status_code, 403)
        c.patch(f"{API}/urns/{urn_id}", headers=self.support_h, json={"supplier_id": self.supplier["id"]})
        approved = c.post(f"{API}/urns/approve", headers=self.support_h, json={"urn_ids": [urn_id]}).json()
        self.assertEqual(approved["approved"], 2)  # never the unclear one
        gift = by_label["Gift box"]
        res = c.put(f"{API}/urns/{urn_id}/variations/{gift['id']}", headers=self.support_h,
                    json={"quantities": {"10": 1, "3": 2}})
        self.assertEqual(res.status_code, 200, res.text)
        sup = str(self.supplier["id"]).zfill(3)
        num = str(urn_id).zfill(4)
        self.assertEqual(res.json()["sku"], f"WCW-{sup}-{num}-10x1-3x2")
        self.assertEqual(c.put(f"{API}/urns/{urn_id}/variations/{gift['id']}", headers=self.support_h,
                               json={"quantities": {"7": 1}}).status_code, 422)
        preview = {p["label"]: p for p in c.get(f"{API}/urns/sku-preview", headers=self.sales_h).json()["items"]
                   if p["urn_id"] == urn_id}
        self.assertEqual(preview["Set of 4 Keepsakes (3 inch)"]["status"], "different")
        self.assertEqual(preview["10 inch Large"]["crm_sku"], f"WCW-{sup}-{num}-10x1")
        # Writing to Etsy is switched off.
        res = c.post(f"{API}/urns/sku-preview/apply", headers=h)
        self.assertEqual(res.status_code, 409)
        self.assertIn("switched off", res.json()["detail"])
        # Prices are dated and need the owner's right.
        self.assertEqual(c.post(f"{API}/urns/{urn_id}/prices", headers=self.support_h,
                                json={"size_code": "10", "amount": "40.00"}).status_code, 403)
        last_month = str(date.today() - timedelta(days=30))
        for amount, on in (("38.00", last_month), ("40.00", None)):
            body = {"size_code": "10", "amount": amount} | ({"effective_from": on} if on else {})
            self.assertEqual(c.post(f"{API}/urns/{urn_id}/prices", headers=h, json=body).status_code, 204)
        urn = c.get(f"{API}/urns/{urn_id}", headers=self.sales_h).json()
        self.assertEqual(urn["prices"]["10"], "40.00")
        self.assertEqual(len(urn["price_history"]), 2)
        # A different template changes the CRM's SKUs (and only those).
        bad = c.post(f"{API}/urns/sku-format/check", headers=h, json={"template": "WCW-{urn:4}"}).json()
        self.assertTrue(bad["problems"])
        self.assertEqual(c.put(f"{API}/urns/sku-format", headers=h, json={"template": "WCW-{urn:4}"}).status_code, 422)
        res = c.put(f"{API}/urns/sku-format", headers=h, json={"template": "U{product:5}-S{supplier:4}-{sizes}{-option}"})
        self.assertEqual(res.status_code, 200, res.text)
        urn = c.get(f"{API}/urns/{urn_id}", headers=self.sales_h).json()
        large = next(v for v in urn["variations"] if v["label"] == "10 inch Large")
        self.assertEqual(large["sku"], f"U{str(urn_id).zfill(5)}-S{str(self.supplier['id']).zfill(4)}-10x1")
        c.put(f"{API}/urns/sku-format", headers=h, json={"template": "WCW-{supplier:3}-{product:4}-{sizes}{-option}"})

    def test_listing_without_variations_and_extras(self):
        c, h = self.w.client, self.h
        c.post(f"{API}/urns/setup", headers=self.support_h)
        urn_id = self.urn_for(self.base + 2)
        urn = c.get(f"{API}/urns/{urn_id}", headers=self.sales_h).json()
        self.assertEqual([(v["label"], v["quantities"]) for v in urn["variations"]], [("(no variations)", {"3": 1})])
        res = c.post(f"{API}/urns/extras", headers=h, json={"urn_id": urn_id, "name": "Supplier discount", "mode": "percent",
                                                          "value": "-5", "applies": "piece", "party": "supplier"})
        self.assertEqual(res.status_code, 201, res.text)
        self.assertEqual(c.post(f"{API}/urns/extras", headers=h, json={
            "name": "Bad", "mode": "percent", "value": "5", "applies": "order"}).status_code, 422)
        extra = res.json()
        self.assertEqual(c.post(f"{API}/urns/extras/{extra['id']}/end", headers=h, json={}).status_code, 204)
        urn = c.get(f"{API}/urns/{urn_id}", headers=self.sales_h).json()
        self.assertEqual([e["name"] for e in urn["extras"]], ["Supplier discount"])
        summary = c.get(f"{API}/urns/summary", headers=self.sales_h).json()
        self.assertGreaterEqual(summary["no_supplier"], 1)
        listed = c.get(f"{API}/urns", headers=self.sales_h, params={"needs": "supplier", "q": "Rose"}).json()
        self.assertIn(urn_id, [u["id"] for u in listed["items"]])
