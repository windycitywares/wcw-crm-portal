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
