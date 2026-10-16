"""Sign-in, profile, password change and password reset against PostgreSQL."""

import re
import time
import unittest

from tests.support import API, World, reset_limits, skip_unless_db


@skip_unless_db
class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()

    def setUp(self):
        reset_limits()

    def test_login_returns_token_and_permissions(self):
        user = self.w.make_user("sales")
        res = self.w.client.post(f"{API}/auth/login", json={"email": user["email"].upper(), "password": user["password"]})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["user"]["role"], "sales")
        self.assertIn("sales:edit_own", body["user"]["permissions"])
        self.assertNotIn("users:manage", body["user"]["permissions"])
        me = self.w.client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        self.assertEqual(me.json()["email"], user["email"])

    def test_wrong_password_unknown_email_and_inactive_all_look_the_same(self):
        user = self.w.make_user("support")
        inactive = self.w.make_user("support", is_active=False)
        for email, pw in ((user["email"], "wrong-password-1"), (self.w.email("nobody"), "whatever-123"),
                          (inactive["email"], inactive["password"])):
            res = self.w.client.post(f"{API}/auth/login", json={"email": email, "password": pw})
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json()["detail"], "Wrong email or password")

    def test_repeated_failures_are_rate_limited(self):
        user = self.w.make_user("sales")
        codes = [self.w.client.post(f"{API}/auth/login", json={"email": user["email"], "password": "nope-nope-1"}).status_code
                 for _ in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)

    def test_requests_without_or_with_bad_token_are_rejected(self):
        self.assertEqual(self.w.client.get(f"{API}/auth/me").status_code, 401)
        bad = self.w.client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nonsense"})
        self.assertEqual(bad.status_code, 401)

    def test_update_profile(self):
        _, headers = self.w.user_with_token("marketing")
        res = self.w.client.patch(f"{API}/auth/me", headers=headers, json={"full_name": "Mia Marketing", "title": "Lead"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["full_name"], "Mia Marketing")
        self.assertEqual(res.json()["title"], "Lead")

    def test_change_password_invalidates_old_tokens(self):
        user, old = self.w.user_with_token("sales")
        bad = self.w.client.post(f"{API}/auth/change-password", headers=old,
                                 json={"current_password": "wrong-one-123", "new_password": "brand-new-pass-1"})
        self.assertEqual(bad.status_code, 422)
        short = self.w.client.post(f"{API}/auth/change-password", headers=old,
                                   json={"current_password": user["password"], "new_password": "short"})
        self.assertEqual(short.status_code, 422)
        time.sleep(1.1)  # tokens carry whole seconds
        res = self.w.client.post(f"{API}/auth/change-password", headers=old,
                                 json={"current_password": user["password"], "new_password": "brand-new-pass-1"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.w.client.get(f"{API}/auth/me", headers=old).status_code, 401)
        fresh = {"Authorization": f"Bearer {res.json()['access_token']}"}
        self.assertEqual(self.w.client.get(f"{API}/auth/me", headers=fresh).status_code, 200)
        self.w.login(user["email"], "brand-new-pass-1")

    def test_forgot_and_reset_password(self):
        user, old = self.w.user_with_token("support")
        self.w.mail.sent.clear()
        unknown = self.w.client.post(f"{API}/auth/forgot-password", json={"email": self.w.email("ghost")})
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(self.w.mail.sent, [])

        res = self.w.client.post(f"{API}/auth/forgot-password", json={"email": user["email"]})
        self.assertEqual(res.status_code, 202)
        self.assertEqual(len(self.w.mail.sent), 1)
        token = re.search(r"token=([\w-]+)", self.w.mail.sent[0].text).group(1)

        time.sleep(1.1)
        done = self.w.client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "after-reset-pass-1"})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(self.w.client.get(f"{API}/auth/me", headers=old).status_code, 401)
        again = self.w.client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "another-pass-12"})
        self.assertEqual(again.status_code, 422)
        self.w.login(user["email"], "after-reset-pass-1")

    def test_reset_with_unknown_token_fails(self):
        res = self.w.client.post(f"{API}/auth/reset-password", json={"token": "x" * 40, "new_password": "whatever-pass-1"})
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
