"""Admin → Users and the audit log, against PostgreSQL."""

import unittest

from tests.support import API, World, reset_limits, skip_unless_db


@skip_unless_db
class UserAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")

    def setUp(self):
        reset_limits()

    def test_only_admins_manage_users(self):
        self.assertEqual(self.w.client.get(f"{API}/users", headers=self.manager_h).status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/users", headers=self.admin_h).status_code, 200)
        roles = self.w.client.get(f"{API}/users/roles", headers=self.manager_h).json()
        self.assertEqual([r["key"] for r in roles], ["admin", "manager", "sales", "support", "marketing", "read_only"])

    def test_create_search_update_and_set_password(self):
        email = self.w.email("new-hire")
        res = self.w.client.post(f"{API}/users", headers=self.admin_h, json={
            "email": email, "full_name": "Nina New", "role": "support", "password": "first-pass-123"})
        self.assertEqual(res.status_code, 201, res.text)
        uid = res.json()["id"]
        dup = self.w.client.post(f"{API}/users", headers=self.admin_h, json={
            "email": email.upper(), "full_name": "Dup", "role": "sales", "password": "first-pass-123"})
        self.assertEqual(dup.status_code, 409)

        found = self.w.client.get(f"{API}/users", headers=self.admin_h, params={"q": "nina new", "role": "support"}).json()
        self.assertEqual([u["id"] for u in found["items"]], [uid])

        upd = self.w.client.patch(f"{API}/users/{uid}", headers=self.admin_h, json={"role": "sales", "title": "Rep"})
        self.assertEqual(upd.json()["role"], "sales")
        self.assertEqual(upd.json()["title"], "Rep")

        pw = self.w.client.post(f"{API}/users/{uid}/password", headers=self.admin_h, json={"new_password": "set-by-admin-1"})
        self.assertEqual(pw.status_code, 200)
        self.w.login(email, "set-by-admin-1")

        audit = self.w.client.get(f"{API}/audit", headers=self.admin_h,
                                  params={"entity_type": "user", "entity_id": uid}).json()
        actions = [a["action"] for a in audit["items"]]
        self.assertIn("user.create", actions)
        self.assertIn("user.update", actions)
        self.assertIn("user.password_set", actions)
        update = next(a for a in audit["items"] if a["action"] == "user.update")
        self.assertEqual(update["changes"]["role"], ["support", "sales"])

    def test_role_change_signs_the_user_out(self):
        user, headers = self.w.user_with_token("sales")
        self.w.client.patch(f"{API}/users/{user['id']}", headers=self.admin_h, json={"role": "read_only"})
        self.assertEqual(self.w.client.get(f"{API}/auth/me", headers=headers).status_code, 401)

    def test_deactivated_user_is_signed_out(self):
        user, headers = self.w.user_with_token("support")
        self.w.client.patch(f"{API}/users/{user['id']}", headers=self.admin_h, json={"is_active": False})
        self.assertEqual(self.w.client.get(f"{API}/auth/me", headers=headers).status_code, 401)

    def test_admin_cannot_demote_or_deactivate_self(self):
        for change in ({"role": "manager"}, {"is_active": False}):
            res = self.w.client.patch(f"{API}/users/{self.admin['id']}", headers=self.admin_h, json=change)
            self.assertEqual(res.status_code, 422, change)

    def test_audit_needs_permission(self):
        _, sales_h = self.w.user_with_token("sales")
        self.assertEqual(self.w.client.get(f"{API}/audit", headers=sales_h).status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/audit", headers=self.manager_h).status_code, 200)


if __name__ == "__main__":
    unittest.main()
