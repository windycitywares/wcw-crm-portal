"""Custom field definitions API and the service other modules use to validate values."""

import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class CustomFieldApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core.entities import EntityType, register_entity
        from app.core.permissions import Permission

        async def exists(_s, _id):
            return True

        cls.etype = "gizmo"
        register_entity(EntityType(key=cls.etype, label="Gizmo", view=(Permission.CUSTOMERS_VIEW,),
                                   edit=(Permission.CUSTOMERS_EDIT_ANY,), exists=exists))
        cls.w = World()
        reset_limits()
        cls.manager, cls.h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    @classmethod
    def tearDownClass(cls):
        from app.core.entities import unregister_entity

        unregister_entity(cls.etype)

    def setUp(self):
        reset_limits()

    def test_lifecycle(self):
        base = f"{API}/custom-fields/{self.etype}"
        types = self.w.client.get(f"{API}/custom-fields/types", headers=self.sales_h).json()
        self.assertIn("multiselect", [t["key"] for t in types])
        self.assertIn(self.etype, [r["key"] for r in self.w.client.get(f"{API}/custom-fields/record-types", headers=self.sales_h).json()])

        no_opts = self.w.client.post(base, headers=self.h, json={"label": "Size", "field_type": "select"})
        self.assertEqual(no_opts.status_code, 422)
        bad_type = self.w.client.post(base, headers=self.h, json={"label": "Size", "field_type": "colour"})
        self.assertEqual(bad_type.status_code, 422)
        self.assertEqual(self.w.client.post(base, headers=self.sales_h, json={"label": "X", "field_type": "text"}).status_code, 403)

        size = self.w.client.post(base, headers=self.h, json={"label": "Size", "field_type": "select",
                                                              "options": ["Small", "small", "Large"], "required": True})
        self.assertEqual(size.status_code, 201, size.text)
        self.assertEqual(size.json()["key"], "size")
        self.assertEqual(size.json()["options"], ["Small", "Large"])
        self.assertEqual(self.w.client.post(base, headers=self.h, json={"label": "Size", "field_type": "text"}).status_code, 409)
        year = self.w.client.post(base, headers=self.h, json={"label": "2025 spend", "field_type": "number"}).json()
        self.assertEqual(year["key"], "f_2025_spend")

        upd = self.w.client.patch(f"{base}/{size.json()['id']}", headers=self.h,
                                  json={"label": "Shirt size", "options": ["Small", "Large", "XL"]})
        self.assertEqual(upd.json()["options"], ["Small", "Large", "XL"])
        order = self.w.client.put(f"{base}/order", headers=self.h, json={"ids": [year["id"], size.json()["id"]]})
        self.assertEqual([f["key"] for f in order.json()], ["f_2025_spend", "size"])

        from app.core.exceptions import ValidationFailedError
        from app.modules.customfields.service import CustomFieldService

        stored = run(lambda s: CustomFieldService(s).validate(self.etype, {"size": "XL", "f_2025_spend": "99"}))
        self.assertEqual(stored, {"size": "XL", "f_2025_spend": 99})
        with self.assertRaises(ValidationFailedError):
            run(lambda s: CustomFieldService(s).validate(self.etype, {"f_2025_spend": "1"}))  # size is required

        self.w.client.patch(f"{base}/{size.json()['id']}", headers=self.h, json={"is_active": False})
        active = self.w.client.get(base, headers=self.sales_h, params={"active_only": True}).json()
        self.assertEqual([f["key"] for f in active], ["f_2025_spend"])

    def test_unknown_record_type(self):
        self.assertEqual(self.w.client.get(f"{API}/custom-fields/nothing", headers=self.h).status_code, 404)


if __name__ == "__main__":
    unittest.main()
