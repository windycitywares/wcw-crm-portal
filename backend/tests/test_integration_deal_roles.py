"""The people on a deal and the part each plays (decision maker, signer…)."""

import unittest

from tests.support import API, World, ensure_pipeline, reset_limits, run, skip_unless_db


@skip_unless_db
class DealRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.sales, cls.h = cls.w.user_with_token("sales")
        cls.other, cls.other_h = cls.w.user_with_token("sales")
        ensure_pipeline(cls.w)

    def setUp(self):
        reset_limits()

    def person(self, name):
        res = self.w.client.post(f"{API}/contacts", headers=self.h,
                                 json={"first_name": name, "email": self.w.email(name.lower()), "types": ["vendor"]})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_buying_committee(self):
        deal = self.w.client.post(f"{API}/sales/deals", headers=self.h, json={"title": "Committee deal"}).json()
        ann, bob = self.person("Ann"), self.person("Bob")
        base = f"{API}/sales/deals/{deal['id']}/contacts"
        a = self.w.client.post(base, headers=self.h, json={"contact_id": ann["id"], "role": "decision_maker",
                                                           "is_primary": True})
        self.assertEqual(a.status_code, 201, a.text)
        b = self.w.client.post(base, headers=self.h, json={"contact_id": bob["id"], "role": "signer"})
        self.assertEqual(b.status_code, 201, b.text)
        self.assertEqual(self.w.client.post(base, headers=self.h, json={"contact_id": bob["id"]}).status_code, 422)
        self.assertEqual(self.w.client.post(base, headers=self.h,
                                            json={"contact_id": ann["id"], "role": "no_such_role"}).status_code, 422)
        self.assertEqual(self.w.client.post(base, headers=self.other_h, json={"contact_id": ann["id"]}).status_code, 403)
        rows = self.w.client.get(base, headers=self.other_h).json()
        self.assertEqual([(r["contact_id"], r["role"], r["is_primary"]) for r in rows],
                         [(ann["id"], "decision_maker", True), (bob["id"], "signer", False)])
        # Making Bob the main contact takes it off Ann.
        res = self.w.client.patch(f"{base}/{b.json()['id']}", headers=self.h, json={"is_primary": True})
        self.assertEqual(res.status_code, 200, res.text)
        rows = self.w.client.get(base, headers=self.h).json()
        self.assertEqual([(r["contact_id"], r["is_primary"]) for r in rows], [(bob["id"], True), (ann["id"], False)])
        mine = self.w.client.get(f"{API}/sales/contact-deals", headers=self.h, params={"contact_id": bob["id"]}).json()
        self.assertEqual([(m["deal_id"], m["role"]) for m in mine], [(deal["id"], "signer")])
        self.assertEqual(self.w.client.delete(f"{base}/{a.json()['id']}", headers=self.h).status_code, 204)
        self.assertEqual(len(self.w.client.get(base, headers=self.h).json()), 1)
