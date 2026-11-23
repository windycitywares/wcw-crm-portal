"""The Trash: delete moves a record there, it can be restored, a parent with live children can't be deleted, and
the job empties what waited longer than the retention period."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class TrashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    def setUp(self):
        reset_limits()

    def customer(self):
        res = self.w.client.post(f"{API}/customers", headers=self.manager_h,
                                 json={"first_name": "Tess", "email": self.w.email("tess")})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def account(self):
        res = self.w.client.post(f"{API}/accounts", headers=self.manager_h,
                                 json={"name": f"Bin {self.w.email('bin')}", "account_type": "customer"})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def in_trash(self, type_, id_):
        page = self.w.client.get(f"{API}/trash", headers=self.manager_h, params={"type": type_, "page_size": 200})
        self.assertEqual(page.status_code, 200, page.text)
        return next((i for i in page.json()["items"] if i["id"] == id_), None)

    def test_delete_restore_and_permissions(self):
        a = self.account()
        self.assertEqual(self.w.client.delete(f"{API}/accounts/{a['id']}", headers=self.manager_h).status_code, 204)
        item = self.in_trash("account", a["id"])
        self.assertIsNotNone(item)
        self.assertEqual(item["title"], a["name"])
        self.assertEqual(self.w.client.get(f"{API}/trash", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/trash/account/{a['id']}/restore", headers=self.sales_h).status_code, 403)
        res = self.w.client.post(f"{API}/trash/account/{a['id']}/restore", headers=self.manager_h)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.w.client.get(f"{API}/accounts/{a['id']}", headers=self.manager_h).status_code, 200)
        self.assertIsNone(self.in_trash("account", a["id"]))

    def test_parent_with_children_cant_be_deleted(self):
        c = self.customer()
        deal = self.w.client.post(f"{API}/sales/deals", headers=self.manager_h,
                                  json={"title": "Bin deal", "customer_id": c["id"]})
        self.assertEqual(deal.status_code, 201, deal.text)
        blockers = self.w.client.get(f"{API}/trash/blockers/customer/{c['id']}", headers=self.sales_h).json()
        self.assertEqual(blockers, ["1 deal"])
        res = self.w.client.delete(f"{API}/customers/{c['id']}", headers=self.manager_h)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertIn("1 deal", res.json()["detail"])
        # The child can go on its own; then the parent can.
        self.assertEqual(self.w.client.delete(f"{API}/sales/deals/{deal.json()['id']}", headers=self.manager_h).status_code, 204)
        self.assertEqual(self.w.client.delete(f"{API}/customers/{c['id']}", headers=self.manager_h).status_code, 204)
        self.assertIsNotNone(self.in_trash("customer", c["id"]))

    def test_account_with_people_cant_be_deleted(self):
        a = self.account()
        p = self.w.client.post(f"{API}/contacts", headers=self.manager_h, json={
            "first_name": "Kit", "email": self.w.email("kit"), "types": ["vendor"], "account_id": a["id"]})
        self.assertEqual(p.status_code, 201, p.text)
        res = self.w.client.delete(f"{API}/accounts/{a['id']}", headers=self.manager_h)
        self.assertEqual(res.status_code, 409)
        self.assertIn("1 person", res.json()["detail"])

    def test_purge_now_is_admin_only_and_final(self):
        a = self.account()
        self.w.client.delete(f"{API}/accounts/{a['id']}", headers=self.manager_h)
        self.assertEqual(self.w.client.delete(f"{API}/trash/account/{a['id']}", headers=self.manager_h).status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/trash/account/{a['id']}", headers=self.admin_h).status_code, 204)
        self.assertIsNone(self.in_trash("account", a["id"]))
        self.assertEqual(self.w.client.post(f"{API}/trash/account/{a['id']}/restore", headers=self.admin_h).status_code, 404)

    def test_job_empties_what_waited_too_long(self):
        from app.modules.accounts.models import Account
        from app.modules.trash.service import TrashService

        old, fresh = self.account(), self.account()
        for a in (old, fresh):
            self.w.client.delete(f"{API}/accounts/{a['id']}", headers=self.manager_h)

        async def age(session):
            row = await session.get(Account, old["id"])
            row.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
            await session.commit()

        run(age)
        line = run(lambda s: TrashService(s).empty_expired())
        self.assertIn("removed", line or "")
        self.assertIsNone(self.in_trash("account", old["id"]))
        self.assertIsNotNone(self.in_trash("account", fresh["id"]))
