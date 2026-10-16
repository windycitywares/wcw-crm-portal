"""RBAC map: every role resolves, admin has everything, read-only can't change anything."""

import unittest

from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Permission, Role, has_permission, permissions_for


class PermissionMapTests(unittest.TestCase):
    def test_every_role_has_a_permission_set_and_label(self):
        for role in Role:
            self.assertIn(role, ROLE_PERMISSIONS)
            self.assertIn(role, ROLE_LABELS)

    def test_admin_has_every_permission(self):
        self.assertEqual(ROLE_PERMISSIONS[Role.ADMIN], frozenset(Permission))

    def test_read_only_only_views(self):
        for perm in ROLE_PERMISSIONS[Role.READ_ONLY]:
            self.assertTrue(perm.value.endswith(":view"), perm)

    def test_only_admin_manages_users_and_settings(self):
        for role in Role:
            expected = role is Role.ADMIN
            self.assertEqual(has_permission(role, Permission.USERS_MANAGE), expected, role)
            self.assertEqual(has_permission(role, Permission.SETTINGS_MANAGE), expected, role)

    def test_manager_is_superset_of_team_roles(self):
        manager = ROLE_PERMISSIONS[Role.MANAGER]
        for role in (Role.SALES, Role.SUPPORT, Role.MARKETING, Role.READ_ONLY):
            self.assertLessEqual(ROLE_PERMISSIONS[role], manager, role)

    def test_role_scopes(self):
        self.assertTrue(has_permission("sales", Permission.SALES_EDIT_OWN))
        self.assertFalse(has_permission("sales", Permission.SALES_EDIT_ANY))
        self.assertTrue(has_permission("support", Permission.TICKETS_EDIT))
        self.assertFalse(has_permission("support", Permission.CAMPAIGNS_SEND))
        self.assertTrue(has_permission("marketing", Permission.CAMPAIGNS_SEND))
        self.assertFalse(has_permission("marketing", Permission.TICKETS_EDIT))

    def test_unknown_role_has_nothing(self):
        self.assertEqual(permissions_for("ghost"), frozenset())
        self.assertFalse(has_permission("ghost", Permission.CUSTOMERS_VIEW))


if __name__ == "__main__":
    unittest.main()
