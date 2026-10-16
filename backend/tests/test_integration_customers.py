"""Customers API: create/duplicates, search & filters, own-vs-any editing, lookups and custom fields,
soft delete/restore, timeline and tags through the shared record features."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class CustomerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.sales2, cls.sales2_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")

    def setUp(self):
        reset_limits()

    def create(self, headers=None, **data):
        data.setdefault("first_name", "Ann")
        data.setdefault("email", self.w.email("cust"))
        res = self.w.client.post(f"{API}/customers", headers=headers or self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_create_defaults_and_duplicate_email(self):
        c = self.create(last_name="Smith", customer_type="vip", source="etsy", marketing_consent=True,
                        address={"city": "Chicago", "line1": ""})
        self.assertEqual(c["owner_id"], self.sales["id"])
        self.assertEqual(c["display_name"], "Ann Smith")
        self.assertEqual(c["status"], "active")
        self.assertEqual(c["address"], {"city": "Chicago"})
        self.assertTrue(c["marketing_consent"])
        self.assertIsNotNone(c["consent_at"])
        dup = self.w.client.post(f"{API}/customers", headers=self.sales_h, json={"first_name": "B", "email": c["email"].upper()})
        self.assertEqual(dup.status_code, 409)
        check = self.w.client.get(f"{API}/customers/check-email", headers=self.ro_h, params={"email": c["email"]}).json()
        self.assertEqual(check["customer_id"], c["id"])

    def test_validation(self):
        empty = self.w.client.post(f"{API}/customers", headers=self.sales_h, json={})
        self.assertEqual(empty.status_code, 422)
        bad_type = self.w.client.post(f"{API}/customers", headers=self.sales_h, json={"first_name": "X", "customer_type": "royalty"})
        self.assertEqual(bad_type.status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/customers", headers=self.ro_h, json={"first_name": "X"}).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/customers", headers=self.marketing_h, json={"first_name": "X"}).status_code, 403)

    def test_own_vs_any(self):
        mine = self.create()
        other = self.w.client.patch(f"{API}/customers/{mine['id']}", headers=self.sales2_h, json={"phone": "555"})
        self.assertEqual(other.status_code, 403)
        ok = self.w.client.patch(f"{API}/customers/{mine['id']}", headers=self.sales_h, json={"phone": " 555 0100 "})
        self.assertEqual(ok.json()["phone"], "555 0100")
        handoff = self.w.client.patch(f"{API}/customers/{mine['id']}", headers=self.sales_h, json={"owner_id": self.sales2["id"]})
        self.assertEqual(handoff.status_code, 403)
        managed = self.w.client.patch(f"{API}/customers/{mine['id']}", headers=self.manager_h, json={"owner_id": self.sales2["id"]})
        self.assertEqual(managed.json()["owner_id"], self.sales2["id"])
        # notes on any visible customer; tags only by someone who may edit it
        self.assertEqual(self.w.client.post(f"{API}/entities/customer/{mine['id']}/notes", headers=self.ro_h, json={"body": "hi"}).status_code, 201)
        self.assertEqual(self.w.client.put(f"{API}/entities/customer/{mine['id']}/tags", headers=self.sales_h, json={"names": ["x"]}).status_code, 403)
        self.assertEqual(self.w.client.put(f"{API}/entities/customer/{mine['id']}/tags", headers=self.sales2_h, json={"names": ["Gift buyer"]}).status_code, 200)

    def test_search_filters_and_tags(self):
        sfx = self.w.sfx
        a = self.create(first_name=f"Zelda{sfx}", company="Lake Co", customer_type="wholesale")
        b = self.create(first_name=f"Zed{sfx}", headers=self.sales2_h)
        self.w.client.put(f"{API}/entities/customer/{b['id']}/tags", headers=self.sales2_h, json={"names": [f"Repeat {sfx}"]})
        res = self.w.client.get(f"{API}/customers", headers=self.ro_h, params={"q": f"zelda{sfx} lake"}).json()
        self.assertEqual([c["id"] for c in res["items"]], [a["id"]])
        res = self.w.client.get(f"{API}/customers", headers=self.ro_h, params={"q": sfx, "type": "wholesale"}).json()
        self.assertEqual([c["id"] for c in res["items"]], [a["id"]])
        mine = self.w.client.get(f"{API}/customers", headers=self.sales2_h, params={"q": sfx, "owner": "me"}).json()
        self.assertEqual([c["id"] for c in mine["items"]], [b["id"]])
        tag_id = mine["items"][0]["tags"][0]["id"]
        tagged = self.w.client.get(f"{API}/customers", headers=self.ro_h, params={"tag_id": tag_id}).json()
        self.assertEqual([c["id"] for c in tagged["items"]], [b["id"]])
        by_name = self.w.client.get(f"{API}/customers", headers=self.ro_h, params={"q": sfx, "sort": "name"}).json()
        self.assertEqual([c["id"] for c in by_name["items"]], [b["id"], a["id"]] if f"Zed{sfx}" < f"Zelda{sfx}" else [a["id"], b["id"]])
        self.assertEqual(self.w.client.get(f"{API}/customers", headers=self.ro_h, params={"sort": "bogus"}).status_code, 422)

    def test_custom_fields_and_timeline(self):
        sfx = self.w.sfx
        field = self.w.client.post(f"{API}/custom-fields/customer", headers=self.manager_h,
                                   json={"label": f"Ring size {sfx}", "field_type": "number"}).json()
        key = field["key"]
        c = self.create(custom_fields={key: "7"})
        self.assertEqual(c["custom_fields"], {key: 7})
        bad = self.w.client.patch(f"{API}/customers/{c['id']}", headers=self.sales_h, json={"custom_fields": {key: "big"}})
        self.assertEqual(bad.status_code, 422)
        self.w.client.patch(f"{API}/customers/{c['id']}", headers=self.sales_h, json={"status": "inactive", "customer_type": "vip"})
        tl = self.w.client.get(f"{API}/entities/customer/{c['id']}/timeline", headers=self.ro_h).json()["items"]
        self.assertEqual(tl[0]["kind"], "customer.updated")
        self.assertIn("status", tl[0]["title"])
        self.assertEqual(tl[-1]["kind"], "customer.created")

    def test_delete_and_restore(self):
        c = self.create()
        self.assertEqual(self.w.client.delete(f"{API}/customers/{c['id']}", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/customers/{c['id']}", headers=self.manager_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/customers/{c['id']}", headers=self.ro_h).status_code, 404)
        deleted = self.w.client.get(f"{API}/customers", headers=self.ro_h, params={"deleted": True, "q": c["email"]}).json()
        self.assertEqual([x["id"] for x in deleted["items"]], [c["id"]])
        # email is free again while deleted …
        twin = self.create(email=c["email"])
        blocked = self.w.client.post(f"{API}/customers/{c['id']}/restore", headers=self.manager_h)
        self.assertEqual(blocked.status_code, 409)  # … so restoring would duplicate it
        self.w.client.delete(f"{API}/customers/{twin['id']}", headers=self.manager_h)
        restored = self.w.client.post(f"{API}/customers/{c['id']}/restore", headers=self.manager_h)
        self.assertEqual(restored.status_code, 200)
        self.assertIsNone(restored.json()["deleted_at"])


if __name__ == "__main__":
    unittest.main()
