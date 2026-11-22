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
