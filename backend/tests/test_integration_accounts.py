"""Accounts API: organisations, their types, own-vs-any, and the contacts at an account."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class AccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.other, cls.other_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    def create(self, headers=None, **data):
        data.setdefault("name", f"Acme {self.w.email('acct').split('@')[0]}")
        data.setdefault("account_type", "supplier")
        res = self.w.client.post(f"{API}/accounts", headers=headers or self.sales_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_create_read_and_type_check(self):
        a = self.create(website="https://acme.example", email="Sales@Acme.example", industry="  Textiles ")
        self.assertEqual(a["status"], "active")
        self.assertEqual(a["owner_id"], self.sales["id"])
        self.assertEqual(a["email"], "sales@acme.example")
        self.assertEqual(a["industry"], "Textiles")
        self.assertEqual(a["contacts_count"], 0)
        got = self.w.client.get(f"{API}/accounts/{a['id']}", headers=self.ro_h)
        self.assertEqual(got.status_code, 200)
        bad = self.w.client.post(f"{API}/accounts", headers=self.sales_h, json={"name": "X", "account_type": "nope"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.w.client.post(f"{API}/accounts", headers=self.ro_h,
                                            json={"name": "X", "account_type": "supplier"}).status_code, 403)

    def test_list_filters_and_options(self):
        sup = self.create(name=f"Zeta supply {self.w.sfx if hasattr(self.w, 'sfx') else ''}".strip())
        cust = self.create(account_type="customer")
        page = self.w.client.get(f"{API}/accounts", headers=self.ro_h, params={"type": "supplier"}).json()
        ids = {x["id"] for x in page["items"]}
        self.assertIn(sup["id"], ids)
        self.assertNotIn(cust["id"], ids)
        opts = self.w.client.get(f"{API}/accounts/options", headers=self.ro_h,
                                 params={"type": "supplier", "q": sup["name"]}).json()
        self.assertEqual([o["id"] for o in opts], [sup["id"]])

    def test_own_vs_any(self):
        a = self.create()
        self.assertEqual(self.w.client.patch(f"{API}/accounts/{a['id']}", headers=self.other_h,
                                             json={"name": "Taken"}).status_code, 403)
        ok = self.w.client.patch(f"{API}/accounts/{a['id']}", headers=self.manager_h, json={"phone": "555 0101"})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["phone"], "555 0101")
        self.assertEqual(self.w.client.delete(f"{API}/accounts/{a['id']}", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/accounts/{a['id']}", headers=self.manager_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/accounts/{a['id']}", headers=self.ro_h).status_code, 404)

    def test_contacts_at_an_account(self):
        a = self.create()
        res = self.w.client.post(f"{API}/contacts", headers=self.sales_h, json={
            "first_name": "Irha", "email": self.w.email("irha"), "types": ["vendor"], "account_id": a["id"]})
        self.assertEqual(res.status_code, 201, res.text)
        contact = res.json()
        self.assertEqual(contact["account_id"], a["id"])
        self.assertEqual(contact["account_name"], a["name"])
        listed = self.w.client.get(f"{API}/accounts/{a['id']}/contacts", headers=self.ro_h).json()
        self.assertEqual([c["id"] for c in listed["items"]], [contact["id"]])
        self.assertEqual(self.w.client.get(f"{API}/accounts/{a['id']}", headers=self.ro_h).json()["contacts_count"], 1)
        filtered = self.w.client.get(f"{API}/contacts", headers=self.ro_h, params={"account_id": a["id"]}).json()
        self.assertEqual(filtered["total"], 1)
        missing = self.w.client.patch(f"{API}/contacts/{contact['id']}", headers=self.sales_h,
                                      json={"account_id": 999999999})
        self.assertEqual(missing.status_code, 422)

    def test_notes_and_timeline_attach(self):
        a = self.create()
        note = self.w.client.post(f"{API}/entities/account/{a['id']}/notes", headers=self.sales_h,
                                  json={"body": "Ships from Lahore"})
        self.assertIn(note.status_code, (200, 201), note.text)
