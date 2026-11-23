"""Accounts API: organisations, their types, own-vs-any, and the contacts at an account."""

import unittest

from tests.support import API, World, ensure_pipeline, reset_limits, run, skip_unless_db


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


@skip_unless_db
class AccountPeopleTests(unittest.TestCase):
    """A person at several organisations, with a role and dates; moving company keeps the history."""

    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.sales, cls.h = cls.w.user_with_token("sales")
        cls.other, cls.other_h = cls.w.user_with_token("sales")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    def account(self, **data):
        data.setdefault("name", f"Org {self.w.email('org').split('@')[0]}")
        data.setdefault("account_type", "customer")
        res = self.w.client.post(f"{API}/accounts", headers=self.h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def person(self, account_id=None):
        body = {"first_name": "Sam", "email": self.w.email("sam"), "types": ["vendor"]}
        if account_id:
            body["account_id"] = account_id
        res = self.w.client.post(f"{API}/contacts", headers=self.h, json=body)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def people(self, account_id, **params):
        res = self.w.client.get(f"{API}/accounts/{account_id}/people", headers=self.ro_h, params=params)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def test_a_new_contact_gets_a_main_link(self):
        a = self.account()
        c = self.person(a["id"])
        rows = self.people(a["id"])
        self.assertEqual([(r["contact_id"], r["is_primary"], r["active"]) for r in rows], [(c["id"], True, True)])

    def test_moving_company_ends_the_old_link(self):
        a, b = self.account(), self.account()
        c = self.person(a["id"])
        res = self.w.client.patch(f"{API}/contacts/{c['id']}", headers=self.h, json={"account_id": b["id"]})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.people(a["id"]), [])
        past = self.people(a["id"], include_ended="true")
        self.assertEqual(len(past), 1)
        self.assertFalse(past[0]["active"])
        self.assertIsNotNone(past[0]["ended_on"])
        self.assertTrue(self.people(b["id"])[0]["is_primary"])
        mine = self.w.client.get(f"{API}/accounts/links", headers=self.ro_h, params={"contact_id": c["id"]}).json()
        self.assertEqual([(m["account_id"], m["active"]) for m in mine], [(b["id"], True), (a["id"], False)])

    def test_several_accounts_with_roles(self):
        a, b = self.account(), self.account(account_type="partner")
        c = self.person(a["id"])
        res = self.w.client.post(f"{API}/accounts/{b['id']}/people", headers=self.h,
                                 json={"contact_id": c["id"], "role": "Board advisor"})
        self.assertEqual(res.status_code, 201, res.text)
        link = res.json()
        self.assertEqual((link["role"], link["is_primary"]), ("Board advisor", False))
        dup = self.w.client.post(f"{API}/accounts/{b['id']}/people", headers=self.h, json={"contact_id": c["id"]})
        self.assertEqual(dup.status_code, 422)
        # Both accounts count and list them; the main account stays A.
        self.assertEqual(self.w.client.get(f"{API}/accounts/{b['id']}", headers=self.ro_h).json()["contacts_count"], 1)
        listed = self.w.client.get(f"{API}/accounts/{b['id']}/contacts", headers=self.ro_h).json()
        self.assertEqual([x["id"] for x in listed["items"]], [c["id"]])
        self.assertEqual(self.w.client.get(f"{API}/contacts/{c['id']}", headers=self.ro_h).json()["account_id"], a["id"])
        # Make B the main account: A stays a current link, just not the main one.
        res = self.w.client.patch(f"{API}/accounts/links/{link['id']}", headers=self.h, json={"is_primary": True})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["is_primary"])
        self.assertEqual(self.w.client.get(f"{API}/contacts/{c['id']}", headers=self.ro_h).json()["account_id"], b["id"])
        a_rows = self.people(a["id"])
        self.assertEqual([(r["active"], r["is_primary"]) for r in a_rows], [(True, False)])
        # Ending the main link hands "main" to the other current one.
        self.assertEqual(self.w.client.delete(f"{API}/accounts/links/{link['id']}", headers=self.h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/contacts/{c['id']}", headers=self.ro_h).json()["account_id"], a["id"])
        self.assertTrue(self.people(a["id"])[0]["is_primary"])
        self.assertEqual(self.people(b["id"]), [])
        self.assertEqual(len(self.people(b["id"], include_ended="true")), 1)

    def test_first_link_becomes_main_and_permissions(self):
        a = self.account()
        c = self.person()
        self.assertEqual(self.w.client.post(f"{API}/accounts/{a['id']}/people", headers=self.other_h,
                                            json={"contact_id": c["id"]}).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/accounts/{a['id']}/people", headers=self.ro_h,
                                            json={"contact_id": c["id"]}).status_code, 403)
        res = self.w.client.post(f"{API}/accounts/{a['id']}/people", headers=self.h,
                                 json={"contact_id": c["id"], "role": "Buyer"})
        self.assertEqual(res.status_code, 201, res.text)
        self.assertTrue(res.json()["is_primary"])
        self.assertEqual(self.w.client.get(f"{API}/contacts/{c['id']}", headers=self.ro_h).json()["account_id"], a["id"])
        bad = self.w.client.patch(f"{API}/accounts/links/{res.json()['id']}", headers=self.h,
                                  json={"ended_on": "2000-01-01"})
        self.assertEqual(bad.status_code, 422)


@skip_unless_db
class AccountGroupTests(unittest.TestCase):
    """Parent and child accounts: no cycles, a group view, and totals rolled up from the sub-accounts."""

    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.mgr, cls.h = cls.w.user_with_token("manager")
        ensure_pipeline(cls.w)

    def setUp(self):
        reset_limits()

    def account(self, **data):
        data.setdefault("name", f"Grp {self.w.email('g').split('@')[0]}")
        data.setdefault("account_type", "customer")
        res = self.w.client.post(f"{API}/accounts", headers=self.h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_group_rollup_and_cycles(self):
        top = self.account()
        mid = self.account(parent_id=top["id"])
        leaf = self.account(parent_id=mid["id"])
        self.assertEqual((mid["parent_id"], mid["parent_name"]), (top["id"], top["name"]))
        self.assertEqual(self.w.client.get(f"{API}/accounts/{top['id']}", headers=self.h).json()["children_count"], 1)
        # People and an open deal under the leaf roll up to the top.
        p = self.w.client.post(f"{API}/contacts", headers=self.h, json={
            "first_name": "Ana", "email": self.w.email("ana"), "types": ["vendor"], "account_id": leaf["id"]})
        self.assertEqual(p.status_code, 201, p.text)
        d = self.w.client.post(f"{API}/sales/deals", headers=self.h,
                               json={"title": "Group deal", "account_id": leaf["id"], "value": "250.00"})
        self.assertEqual(d.status_code, 201, d.text)
        g = self.w.client.get(f"{API}/accounts/{top['id']}/group", headers=self.h).json()
        self.assertEqual([(n["id"], n["depth"]) for n in g["tree"]], [(top["id"], 0), (mid["id"], 1), (leaf["id"], 2)])
        self.assertEqual((g["accounts"], g["people"], g["open_deals"], g["open_value"]), (3, 1, 1, 250.0))
        self.assertEqual([a["id"] for a in self.w.client.get(f"{API}/accounts/{leaf['id']}/group",
                                                             headers=self.h).json()["ancestors"]], [top["id"], mid["id"]])
        # No cycles: the top can't go under its own grandchild, nor under itself.
        for bad in (leaf["id"], top["id"]):
            res = self.w.client.patch(f"{API}/accounts/{top['id']}", headers=self.h, json={"parent_id": bad})
            self.assertEqual(res.status_code, 422, res.text)
        listed = self.w.client.get(f"{API}/accounts", headers=self.h, params={"parent_id": top["id"]}).json()
        self.assertEqual([a["id"] for a in listed["items"]], [mid["id"]])
        # A parent with a live sub-account can't be deleted; detaching it frees the parent.
        self.assertEqual(self.w.client.delete(f"{API}/accounts/{top['id']}", headers=self.h).status_code, 409)
        res = self.w.client.patch(f"{API}/accounts/{mid['id']}", headers=self.h, json={"parent_id": None})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIsNone(res.json()["parent_id"])
        self.assertEqual(self.w.client.delete(f"{API}/accounts/{top['id']}", headers=self.h).status_code, 204)
