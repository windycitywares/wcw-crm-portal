"""Type lists (lookups): seed, list, create, rename/deactivate, reorder, permissions, validation helper."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class LookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    def setUp(self):
        reset_limits()

    def test_seeded_kinds_are_listed(self):
        kinds = self.w.client.get(f"{API}/lookups", headers=self.sales_h).json()
        by_key = {k["key"]: k for k in kinds}
        self.assertIn("customer_type", by_key)
        labels = [v["label"] for v in by_key["ticket_priority"]["values"]]
        self.assertEqual(labels[:4], ["Low", "Normal", "High", "Urgent"])
        keys = [v["key"] for v in by_key["customer_type"]["values"]]
        self.assertIn("vip", keys)

    def test_seed_is_idempotent(self):
        from app.modules.lookups.service import LookupService

        self.assertEqual(run(lambda s: LookupService(s).seed()), "type lists already set up")

    def test_unknown_kind_is_404(self):
        self.assertEqual(self.w.client.get(f"{API}/lookups/nope", headers=self.sales_h).status_code, 404)

    def test_manage_create_update_reorder(self):
        h = self.manager_h
        label = f"Trade {self.w.sfx}"
        res = self.w.client.post(f"{API}/lookups/supplier_type", headers=h, json={"label": label, "color": "info"})
        self.assertEqual(res.status_code, 201, res.text)
        created = res.json()
        self.assertEqual(created["key"], f"trade_{self.w.sfx}")
        dup = self.w.client.post(f"{API}/lookups/supplier_type", headers=h, json={"label": label})
        self.assertEqual(dup.status_code, 409)
        bad = self.w.client.post(f"{API}/lookups/supplier_type", headers=h, json={"label": "X", "color": "pink"})
        self.assertEqual(bad.status_code, 422)

        upd = self.w.client.patch(f"{API}/lookups/supplier_type/{created['id']}", headers=h,
                                  json={"label": "Trade partner", "is_active": False})
        self.assertEqual(upd.json()["label"], "Trade partner")
        self.assertFalse(upd.json()["is_active"])
        active = self.w.client.get(f"{API}/lookups/supplier_type", headers=h, params={"active_only": True}).json()
        self.assertNotIn(created["id"], [v["id"] for v in active])

        ids = [v["id"] for v in self.w.client.get(f"{API}/lookups/supplier_type", headers=h).json()]
        order = list(reversed(ids))
        res = self.w.client.put(f"{API}/lookups/supplier_type/order", headers=h, json={"ids": order})
        self.assertEqual([v["id"] for v in res.json()], order)
        partial = self.w.client.put(f"{API}/lookups/supplier_type/order", headers=h, json={"ids": order[:1]})
        self.assertEqual(partial.status_code, 422)

    def test_only_managers_and_admins_edit(self):
        res = self.w.client.post(f"{API}/lookups/task_type", headers=self.sales_h, json={"label": "Nope"})
        self.assertEqual(res.status_code, 403)

    def test_require_helper(self):
        from app.core.exceptions import ValidationFailedError
        from app.modules.lookups.service import LookupService

        self.assertEqual(run(lambda s: LookupService(s).require("task_type", "call")), "call")
        self.assertIsNone(run(lambda s: LookupService(s).require("task_type", None)))
        with self.assertRaises(ValidationFailedError):
            run(lambda s: LookupService(s).require("task_type", "teleport"))


class SlugTests(unittest.TestCase):
    def test_slugify(self):
        try:
            from app.modules.lookups.service import slugify
        except ImportError:  # pragma: no cover - sqlalchemy missing
            self.skipTest("sqlalchemy not installed")
        self.assertEqual(slugify("Marketplace (Etsy/Amazon)"), "marketplace_etsy_amazon")
        self.assertEqual(slugify("Return / exchange"), "return_exchange")
        self.assertEqual(slugify("Café déco"), "cafe_deco")
        self.assertEqual(slugify("!!!"), "value")


if __name__ == "__main__":
    unittest.main()
