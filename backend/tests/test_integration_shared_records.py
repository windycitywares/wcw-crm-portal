"""Notes, tags and timeline on a registered record type (a throwaway "widget" type stands in for
customers/tickets until those modules exist)."""

import unittest

from tests.support import API, World, reset_limits, skip_unless_db


@skip_unless_db
class SharedRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core.entities import EntityType, register_entity
        from app.core.permissions import Permission

        async def exists(_session, entity_id):  # widgets 1..100 exist
            return 1 <= entity_id <= 100

        async def can_edit(_session, user, entity_id):  # sales may only change even-numbered widgets
            return user.role != "sales" or entity_id % 2 == 0

        register_entity(EntityType(
            key="widget", label="Widget",
            view=(Permission.CUSTOMERS_VIEW,), edit=(Permission.CUSTOMERS_EDIT_OWN, Permission.CUSTOMERS_EDIT_ANY),
            exists=exists, can_edit=can_edit,
        ))
        cls.w = World()
        reset_limits()
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    @classmethod
    def tearDownClass(cls):
        from app.core.entities import unregister_entity

        unregister_entity("widget")

    def setUp(self):
        reset_limits()

    def url(self, wid, part):
        return f"{API}/entities/widget/{wid}/{part}"

    # ---- tags -----------------------------------------------------------
    def test_set_tags_creates_names_and_dedupes(self):
        sfx = self.w.sfx
        res = self.w.client.put(self.url(2, "tags"), headers=self.sales_h,
                                json={"names": [f"VIP {sfx}", f"vip  {sfx}", f"Gift {sfx}"]})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(sorted(t["name"] for t in res.json()), sorted([f"Gift {sfx}", f"VIP {sfx}"]))
        res = self.w.client.put(self.url(2, "tags"), headers=self.sales_h, json={"names": [f"Gift {sfx}"]})
        self.assertEqual([t["name"] for t in res.json()], [f"Gift {sfx}"])
        found = self.w.client.get(f"{API}/tags", headers=self.ro_h, params={"q": f"gift {sfx}"}).json()
        self.assertEqual([(t["name"], t["uses"]) for t in found], [(f"Gift {sfx}", 1)])

    def test_tag_permissions(self):
        self.assertEqual(self.w.client.put(self.url(3, "tags"), headers=self.sales_h, json={"names": ["x"]}).status_code, 403)
        self.assertEqual(self.w.client.put(self.url(2, "tags"), headers=self.ro_h, json={"names": ["x"]}).status_code, 403)
        self.assertEqual(self.w.client.get(self.url(2, "tags"), headers=self.ro_h).status_code, 200)
        self.assertEqual(self.w.client.get(self.url(999, "tags"), headers=self.ro_h).status_code, 404)
        self.assertEqual(self.w.client.get(f"{API}/entities/gadget/1/tags", headers=self.ro_h).status_code, 404)

    def test_manage_tags(self):
        sfx = self.w.sfx
        created = self.w.client.post(f"{API}/tags", headers=self.manager_h, json={"name": f"Wholesale {sfx}", "color": "info"})
        self.assertEqual(created.status_code, 201, created.text)
        tid = created.json()["id"]
        self.assertEqual(self.w.client.post(f"{API}/tags", headers=self.manager_h, json={"name": f"wholesale {sfx}"}).status_code, 409)
        self.assertEqual(self.w.client.post(f"{API}/tags", headers=self.sales_h, json={"name": "nope"}).status_code, 403)
        renamed = self.w.client.patch(f"{API}/tags/{tid}", headers=self.manager_h, json={"name": f"Trade {sfx}"})
        self.assertEqual(renamed.json()["name"], f"Trade {sfx}")
        self.w.client.put(self.url(4, "tags"), headers=self.manager_h, json={"names": [f"Trade {sfx}"]})
        self.assertEqual(self.w.client.delete(f"{API}/tags/{tid}", headers=self.manager_h).status_code, 204)
        self.assertEqual(self.w.client.get(self.url(4, "tags"), headers=self.manager_h).json(), [])

    # ---- notes + timeline -----------------------------------------------
    def test_notes_and_timeline(self):
        res = self.w.client.post(self.url(10, "notes"), headers=self.marketing_h, json={"body": "Called — wants a quote"})
        self.assertEqual(res.status_code, 201, res.text)
        note = res.json()
        pinned = self.w.client.post(self.url(10, "notes"), headers=self.sales_h, json={"body": "Prefers email", "pinned": True}).json()
        notes = self.w.client.get(self.url(10, "notes"), headers=self.ro_h).json()
        self.assertEqual([n["id"] for n in notes][:2], [pinned["id"], note["id"]])

        # only the author (or a manager) can change a note
        self.assertEqual(self.w.client.patch(f"{API}/notes/{note['id']}", headers=self.sales_h, json={"body": "x"}).status_code, 403)
        edited = self.w.client.patch(f"{API}/notes/{note['id']}", headers=self.marketing_h, json={"body": "Called — sent quote"})
        self.assertEqual(edited.json()["body"], "Called — sent quote")
        self.assertEqual(self.w.client.delete(f"{API}/notes/{pinned['id']}", headers=self.manager_h).status_code, 204)
        self.assertNotIn(pinned["id"], [n["id"] for n in self.w.client.get(self.url(10, "notes"), headers=self.ro_h).json()])

        tl = self.w.client.get(self.url(10, "timeline"), headers=self.ro_h).json()
        kinds = [a["kind"] for a in tl["items"]]
        self.assertEqual(kinds[:3], ["note.deleted", "note.added", "note.added"])
        only_added = self.w.client.get(self.url(10, "timeline"), headers=self.ro_h, params={"kind": "note.added"}).json()
        self.assertTrue(all(a["kind"] == "note.added" for a in only_added["items"]))

    def test_note_validation_and_unknown_record(self):
        self.assertEqual(self.w.client.post(self.url(500, "notes"), headers=self.ro_h, json={"body": "hi"}).status_code, 404)
        self.assertEqual(self.w.client.post(self.url(5, "notes"), headers=self.ro_h, json={"body": "   "}).status_code, 422)

if __name__ == "__main__":
    unittest.main()
