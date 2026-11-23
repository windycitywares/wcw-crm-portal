"""Sales channels: the Etsy connection, with Etsy itself replaced — credentials, "Allow access", who may do what."""

import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from tests.support import API, World, reset_limits, skip_unless_db


@skip_unless_db
class EtsyConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    def test_team_sees_status_only_admin_changes_it(self):
        c = self.w.client
        self.assertEqual(c.get(f"{API}/channels/etsy/connection", headers=self.support_h).status_code, 200)
        self.assertEqual(c.get(f"{API}/channels/etsy/connection", headers=self.ro_h).status_code, 403)
        self.assertEqual(c.put(f"{API}/channels/etsy/credentials", headers=self.manager_h,
                               json={"client_id": "x"}).status_code, 403)
        self.assertEqual(c.post(f"{API}/channels/etsy/connect", headers=self.manager_h).status_code, 403)
        listed = c.get(f"{API}/channels", headers=self.support_h).json()["items"]
        self.assertEqual([x["key"] for x in listed], ["etsy", "amazon", "walmart"])
        self.assertFalse(next(x for x in listed if x["key"] == "amazon")["available"])

    def test_secret_is_never_returned_and_allow_access_round_trip(self):
        c = self.w.client
        r = c.put(f"{API}/channels/etsy/credentials", headers=self.admin_h,
                  json={"client_id": "keystring123", "client_secret": "s3cret-value"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["client_id"], r.json()["secret_set"]), ("keystring123", True))
        self.assertNotIn("s3cret-value", r.text)
        self.assertTrue(r.json()["redirect_uri"].endswith("/channels/etsy/callback"))

        url = c.post(f"{API}/channels/etsy/connect", headers=self.admin_h).json()["url"]
        q = parse_qs(urlparse(url).query)
        self.assertEqual(q["client_id"], ["keystring123"])
        self.assertEqual(q["code_challenge_method"], ["S256"])
        state = q["state"][0]

        tokens = {"access_token": "4242.tok", "refresh_token": "4242.ref", "expires_in": 3600}
        shops = {"shop_id": 99, "shop_name": "WindyCityWaresUS"}
        with mock.patch("app.modules.channels.etsy.client.exchange_code", mock.AsyncMock(return_value=tokens)), \
                mock.patch("app.modules.channels.etsy.client.get", mock.AsyncMock(return_value=shops)):
            def back(value):
                res = c.get(f"{API}/channels/etsy/callback", params={"state": value, "code": "c"},
                            follow_redirects=False)
                self.assertEqual(res.status_code, 307, res.text)
                return res.headers["location"]

            self.assertIn("etsy=failed", back("wrong"))
            self.assertIn("etsy=connected", back(state))
            self.assertIn("etsy=failed", back(state))  # the state works once

        status = c.get(f"{API}/channels/etsy/connection", headers=self.admin_h)
        self.assertTrue(status.json()["connected"])
        self.assertEqual(status.json()["shop_name"], "WindyCityWaresUS")
        self.assertNotIn("4242.tok", status.text)
        listed = c.get(f"{API}/channels", headers=self.support_h).json()["items"]
        self.assertTrue(next(x for x in listed if x["key"] == "etsy")["connected"])

        self.assertFalse(c.post(f"{API}/channels/etsy/disconnect", headers=self.admin_h).json()["connected"])


if __name__ == "__main__":
    unittest.main()


def connect_etsy_for_tests(session):
    """A connected Etsy row, without Etsy: sealed tokens that won't expire for a day."""
    from datetime import datetime, timedelta, timezone

    from app.core.security import SecretBox
    from app.modules.channels.models import ChannelConnection

    async def go():
        row = await session.get(ChannelConnection, "etsy") or ChannelConnection(channel="etsy")
        box = SecretBox()
        row.client_id, row.client_secret_enc = "k", box.encrypt("s")
        row.access_token_enc, row.refresh_token_enc = box.encrypt("1.tok"), box.encrypt("1.ref")
        row.external_shop_id, row.shop_name = 5, "Test shop"
        row.token_expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        row.listings_synced_at = None
        session.add(row)
    return go()


def _raw(i, title, state="active"):
    return {"listing_id": i, "title": title, "state": state, "quantity": 3,
            "price": {"amount": 1500, "divisor": 100, "currency_code": "USD"}, "skus": [f"SKU-{i}"]}


@skip_unless_db
class EtsyListingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService
        from tests.support import run

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")

    def setUp(self):
        from tests.support import run

        reset_limits()
        run(connect_etsy_for_tests)

    def _sync(self, pages):
        from app.modules.channels.listings import EtsyListingSync
        from tests.support import run

        async def fake_get(path, **kw):
            return {"results": pages.get(kw["params"]["state"], [])}

        async def go(session):
            with mock.patch("app.modules.channels.etsy.client.get", fake_get):
                return await EtsyListingSync(session).run(force=True)

        return run(go)

    def test_sync_keeps_team_fields_and_marks_removed(self):
        c = self.w.client
        base = 9_000_000 + int(self.w.sfx[:5], 16) % 100_000
        first = self._sync({"active": [_raw(base, "Mug"), _raw(base + 1, "Tee")]})
        self.assertGreaterEqual(first["created"] + first["updated"], 2, first)

        rows = c.get(f"{API}/channels/etsy/listings", headers=self.sales_h, params={"q": f"SKU-{base}"}).json()["items"]
        mug = next(r for r in rows if r["external_id"] == base)
        supplier = c.post(f"{API}/accounts", headers=self.manager_h,
                          json={"name": f"Acme {self.w.sfx}", "account_type": "supplier"}).json()
        self.assertEqual(c.patch(f"{API}/channels/etsy/listings/{mug['id']}", headers=self.sales_h,
                                 json={"purchase_cost": "1"}).status_code, 403)
        patched = c.patch(f"{API}/channels/etsy/listings/{mug['id']}", headers=self.support_h,
                          json={"supplier_account_id": supplier["id"], "purchase_cost": "6.50"})
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["supplier_name"], supplier["name"])

        # Etsy renames the mug and drops the tee; the team's fields stay
        second = self._sync({"active": [_raw(base, "Mug v2")]})
        self.assertGreaterEqual(second["removed"], 1)
        mug2 = next(r for r in c.get(f"{API}/channels/etsy/listings", headers=self.sales_h,
                                     params={"supplier": str(supplier["id"])}).json()["items"])
        self.assertEqual((mug2["title"], mug2["supplier_account_id"], str(mug2["purchase_cost"])),
                         ("Mug v2", supplier["id"], "6.50"))
        tee = c.get(f"{API}/channels/etsy/listings", headers=self.sales_h, params={"q": f"SKU-{base + 1}"}).json()["items"]
        self.assertEqual(tee[0]["state"], "removed")


def _money(cents):
    return {"amount": cents, "divisor": 100, "currency_code": "USD"}


def receipt(rid, listing_id, **over):
    base = {
        "receipt_id": rid, "status": "Paid", "is_paid": True, "is_shipped": False, "name": "Sam Buyer", "buyer_user_id": 42,
        "city": "Chicago", "country_iso": "US", "created_timestamp": 1760000000, "message_from_buyer": "Thanks!",
        "grandtotal": _money(3300), "total_shipping_cost": _money(500), "discount_amt": _money(0),
        "total_tax_cost": _money(300),
        "transactions": [{"transaction_id": rid * 10, "listing_id": listing_id, "title": "Mug", "quantity": 2,
                          "price": _money(1250), "expected_ship_date": 1760400000}],
    }
    base.update(over)
    return base


@skip_unless_db
class EtsyOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService
        from tests.support import run

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")

    def setUp(self):
        from tests.support import run

        reset_limits()
        run(connect_etsy_for_tests)
        self.base = 7_000_000 + int(self.w.sfx[:6], 16) % 900_000 * 10

    def sync(self, receipts, listings=None):
        from app.modules.channels.listings import EtsyListingSync
        from app.modules.channels.orders_sync import EtsyOrderSync
        from tests.support import run

        async def fake_get(path, **kw):
            if path.endswith("/listings"):
                return {"results": (listings or []) if kw["params"]["state"] == "active" else []}
            return {"results": receipts if kw["params"]["offset"] == 0 else []}

        async def go(session):
            with mock.patch("app.modules.channels.etsy.client.get", fake_get):
                if listings is not None:
                    await EtsyListingSync(session).run(force=True)
                return await EtsyOrderSync(session).run(force=True)

        return run(go)

    def find(self, rid, headers=None, **params):
        res = self.w.client.get(f"{API}/channels/etsy/orders", headers=headers or self.sales_h,
                                params={"q": str(rid), **params})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def test_paid_order_arrives_once_with_the_listing_cost_and_supplier(self):
        c = self.w.client
        rid, lid = self.base, self.base + 1
        self.sync([], listings=[{"listing_id": lid, "title": "Mug", "state": "active", "price": _money(1250)}])
        listing = c.get(f"{API}/channels/etsy/listings", headers=self.sales_h, params={"q": "Mug"}).json()["items"]
        listing = next(x for x in listing if x["external_id"] == lid)
        supplier = c.post(f"{API}/accounts", headers=self.manager_h,
                          json={"name": f"Acme {self.w.sfx}", "account_type": "supplier"}).json()
        c.patch(f"{API}/channels/etsy/listings/{listing['id']}", headers=self.support_h,
                json={"supplier_account_id": supplier["id"], "purchase_cost": "4.00"})

        self.assertGreaterEqual(self.sync([receipt(rid, lid)])["created"], 1)
        self.sync([receipt(rid, lid)])  # a second pass adds nothing
        page = self.find(rid)
        self.assertEqual(page["total"], 1)
        order = c.get(f"{API}/channels/etsy/orders/{page['items'][0]['id']}", headers=self.sales_h).json()
        self.assertEqual((order["status"], str(order["items_total"]), str(order["purchase_cost"])), ("new", "25.00", "8.00"))
        self.assertTrue(order["costs_prefilled"])
        self.assertEqual((order["supplier_account_id"], order["supplier_name"]), (supplier["id"], supplier["name"]))
        self.assertEqual(order["buyer_note"], "Thanks!")
        self.assertEqual(len(order["line_items"]), 1)
        self.assertEqual([h["kind"] for h in order["history"]], ["created"])
        self.assertEqual(c.get(f"{API}/channels/etsy/orders", headers=self.ro_h).status_code, 403)

    def test_unpaid_order_is_not_created(self):
        rid = self.base + 2
        self.sync([receipt(rid, None, status="Open", is_paid=False)])
        self.assertEqual(self.find(rid)["total"], 0)

    def test_team_work_survives_etsy_and_status_only_moves_forward(self):
        c = self.w.client
        rid = self.base + 3
        self.sync([receipt(rid, None)])
        oid = self.find(rid)["items"][0]["id"]
        self.assertEqual(c.patch(f"{API}/channels/etsy/orders/{oid}", headers=self.sales_h,
                                 json={"purchase_cost": "9.99"}).status_code, 403)
        patched = c.patch(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h,
                          json={"purchase_cost": "9.99", "notes": "bought from Acme"})
        self.assertEqual(patched.status_code, 200, patched.text)
        moved = c.post(f"{API}/channels/etsy/orders/{oid}/status", headers=self.support_h,
                       json={"status": "purchased", "note": "ordered"})
        self.assertEqual((moved.status_code, moved.json()["status"]), (200, "purchased"))

        self.sync([receipt(rid, None, is_shipped=True, name="Sam B. Buyer",
                           shipments=[{"tracking_code": "9400111", "carrier_name": "usps"}])])
        order = c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.sales_h).json()
        self.assertEqual((order["status"], str(order["purchase_cost"]), order["notes"]), ("shipped", "9.99", "bought from Acme"))
        self.assertEqual((order["buyer_name"], order["tracking_number"]), ("Sam B. Buyer", "9400111"))
        kinds = [(h["kind"], h["source"]) for h in order["history"]]
        for expected in (("status", "etsy"), ("tracking", "etsy"), ("costs", "team"), ("status", "team")):
            self.assertIn(expected, kinds)

        # parked on an exception by the team: Etsy leaves it there
        c.post(f"{API}/channels/etsy/orders/{oid}/status", headers=self.support_h, json={"status": "issue"})
        self.sync([receipt(rid, None, is_shipped=True, status="Completed")])
        self.assertEqual(c.get(f"{API}/channels/etsy/orders/{oid}", headers=self.sales_h).json()["status"], "issue")

    def test_already_shipped_on_arrival_never_needs_attention(self):
        rid = self.base + 6
        self.sync([receipt(rid, None, is_shipped=True)])
        item = self.find(rid)["items"][0]
        self.assertTrue(item["past_order"])
        self.assertEqual(item["attention"], [])
        self.assertEqual(self.find(rid, attention="true")["total"], 0)
        fresh = self.base + 7
        self.sync([receipt(fresh, None)])
        self.assertIn("cost_missing", self.find(fresh)["items"][0]["attention"])

    def test_supplier_payments_pending_settled_undo_and_exports(self):
        c = self.w.client
        supplier = c.post(f"{API}/accounts", headers=self.manager_h,
                          json={"name": f"Payee {self.w.sfx}", "account_type": "supplier"}).json()
        ids = []
        for n in (11, 12):
            self.sync([receipt(self.base + n, None)])
            oid = self.find(self.base + n)["items"][0]["id"]
            c.patch(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h,
                    json={"purchase_cost": "10.00", "shipping_cost": "2.50", "supplier_account_id": supplier["id"]})
            ids.append(oid)
        sid = str(supplier["id"])
        pending = c.get(f"{API}/channels/etsy/supplier-payments", headers=self.sales_h,
                        params={"supplier": sid}).json()
        self.assertEqual(pending["total"], 2)
        self.assertEqual(str(pending["items"][0]["owed"]), "12.50")
        overview = c.get(f"{API}/channels/etsy/supplier-payments/overview", headers=self.sales_h,
                         params={"supplier": sid}).json()
        self.assertEqual((overview["pending_count"], str(overview["pending_amount"])), (2, "25.00"))

        self.assertEqual(c.post(f"{API}/channels/etsy/supplier-payments/settle", headers=self.support_h,
                                json={"order_ids": ids}).status_code, 403)
        done = c.post(f"{API}/channels/etsy/supplier-payments/settle", headers=self.admin_h,
                      json={"order_ids": ids, "reference": "INV-7"})
        self.assertEqual((done.status_code, done.json()["settled"]), (200, 2), done.text)
        settled = c.get(f"{API}/channels/etsy/supplier-payments", headers=self.sales_h,
                        params={"supplier": sid, "state": "settled"}).json()
        self.assertEqual({r["payment_ref"] for r in settled["items"]}, {"INV-7"})
        order = c.get(f"{API}/channels/etsy/orders/{ids[0]}", headers=self.sales_h).json()
        self.assertEqual(order["supplier_payment"], "settled")
        self.assertIn("payment", [h["kind"] for h in order["history"]])

        self.assertEqual(c.post(f"{API}/channels/etsy/supplier-payments/{ids[0]}/undo", headers=self.admin_h,
                                json={"reason": "wrong invoice"}).status_code, 200)
        self.assertEqual(c.get(f"{API}/channels/etsy/orders/{ids[0]}", headers=self.sales_h).json()["supplier_payment"],
                         "pending")

        csv = c.get(f"{API}/channels/etsy/supplier-payments/export", headers=self.sales_h,
                    params={"supplier": sid, "state": "all"})
        self.assertEqual(csv.status_code, 200)
        self.assertIn("Etsy order", csv.content.decode("utf-8-sig").splitlines()[0])
        xlsx = c.get(f"{API}/channels/etsy/supplier-payments/export", headers=self.sales_h,
                     params={"supplier": sid, "format": "xlsx"})
        self.assertEqual((xlsx.status_code, xlsx.content[:2]), (200, b"PK"))

    def test_dashboard_answers_for_a_period(self):
        c = self.w.client
        self.sync([receipt(self.base + 21, None, created_timestamp=1767225600)])  # 2026-01-01
        board = c.get(f"{API}/channels/etsy/dashboard", headers=self.sales_h,
                      params={"start": "2025-12-25", "end": "2026-01-07"})
        self.assertEqual(board.status_code, 200, board.text)
        body = board.json()
        self.assertGreaterEqual(body["totals"]["orders"], 1)
        self.assertEqual(body["range"]["granularity"], "day")
        self.assertEqual(len(body["series"]), 14)
        self.assertEqual([k["key"] for k in body["kpis"]][:3], ["orders", "items", "revenue"])
        self.assertEqual(c.get(f"{API}/channels/etsy/dashboard", headers=self.sales_h,
                               params={"start": "2026-02-01", "end": "2026-01-01"}).status_code, 422)

    def test_supplier_portal_sees_only_their_own_orders(self):
        c = self.w.client
        mine = c.post(f"{API}/accounts", headers=self.manager_h,
                      json={"name": f"Maker {self.w.sfx}", "account_type": "supplier"}).json()
        other = c.post(f"{API}/accounts", headers=self.manager_h,
                       json={"name": f"Other {self.w.sfx}", "account_type": "supplier"}).json()
        ids = {}
        for n, account in ((31, mine), (32, other)):
            self.sync([receipt(self.base + n, None)])
            oid = self.find(self.base + n)["items"][0]["id"]
            c.patch(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h,
                    json={"purchase_cost": "7.00", "supplier_account_id": account["id"], "notes": "team only"})
            ids[n] = oid

        email, password = self.w.email("maker"), "maker-pass-123"
        self.assertEqual(c.post(f"{API}/supplier-portal/logins", headers=self.manager_h, json={
            "email": email, "password": password, "full_name": "Mia Maker", "account_id": mine["id"]}).status_code, 403)
        made = c.post(f"{API}/supplier-portal/logins", headers=self.admin_h, json={
            "email": email, "password": password, "full_name": "Mia Maker", "account_id": mine["id"],
            "channels": ["etsy"]})
        self.assertEqual(made.status_code, 201, made.text)
        self.assertEqual(made.json()["supplier_name"], mine["name"])
        people = c.get(f"{API}/accounts/{mine['id']}/contacts", headers=self.manager_h).json()
        self.assertIn(email, [p["email"] for p in people["items"]])
        self.assertEqual(c.post(f"{API}/supplier-portal/logins", headers=self.admin_h, json={
            "email": self.w.email("x"), "password": password, "full_name": "X", "account_id": mine["id"],
            "channels": ["ebay"]}).status_code, 422)

        h = self.w.login(email, password)
        self.assertEqual(c.get(f"{API}/channels/etsy/orders", headers=h).status_code, 403)
        me = c.get(f"{API}/supplier-portal/me", headers=h).json()
        self.assertEqual((me["supplier_name"], me["channels"]), (mine["name"], ["etsy"]))
        listed = c.get(f"{API}/supplier-portal/etsy/orders", headers=h, params={"view": "all"}).json()
        self.assertIn(ids[31], [o["id"] for o in listed["items"]])
        self.assertNotIn(ids[32], [o["id"] for o in listed["items"]])
        self.assertEqual(c.get(f"{API}/supplier-portal/etsy/orders/{ids[32]}", headers=h).status_code, 404)
        detail = c.get(f"{API}/supplier-portal/etsy/orders/{ids[31]}", headers=h).json()
        self.assertNotIn("notes", detail)
        self.assertNotIn("buyer_email", detail)
        self.assertEqual(str(detail["owed"]), "7.00")

        shipped = c.post(f"{API}/supplier-portal/etsy/orders/{ids[31]}/shipped", headers=h,
                         json={"carrier": "USPS", "tracking_number": "9400 1"})
        self.assertEqual((shipped.status_code, shipped.json()["status"]), (200, "shipped"), shipped.text)
        team_view = c.get(f"{API}/channels/etsy/orders/{ids[31]}", headers=self.sales_h).json()
        self.assertEqual(team_view["tracking_number"], "9400 1")
        self.assertIn("supplier", {h["source"] for h in team_view["history"]})
        pay = c.get(f"{API}/supplier-portal/etsy/payments", headers=h, params={"state": "all"}).json()
        self.assertEqual({r["id"] for r in pay["items"]}, {ids[31]})

    def test_supplier_stats_for_the_supplier_page(self):
        c = self.w.client
        acct = c.post(f"{API}/accounts", headers=self.manager_h,
                      json={"name": f"Stats {self.w.sfx}", "account_type": "supplier"}).json()
        self.sync([receipt(self.base + 51, None)])
        oid = self.find(self.base + 51)["items"][0]["id"]
        c.patch(f"{API}/channels/etsy/orders/{oid}", headers=self.support_h,
                json={"purchase_cost": "8.00", "shipping_cost": "2.00", "supplier_account_id": acct["id"]})
        stats = c.get(f"{API}/channels/etsy/supplier-stats/{acct['id']}", headers=self.sales_h).json()
        self.assertEqual((stats["orders"], stats["to_ship"], stats["owed_orders"], str(stats["owed"])), (1, 1, 1, "10.00"))
