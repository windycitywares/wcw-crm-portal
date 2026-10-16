"""Admin → Settings: defaults, validation, encrypted SMTP password, permissions, test email."""

import unittest
from unittest import mock

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.h = cls.w.user_with_token("admin")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")

    def setUp(self):
        reset_limits()

    def test_groups_and_permissions(self):
        self.assertEqual(self.w.client.get(f"{API}/settings", headers=self.manager_h).status_code, 403)
        keys = [g["key"] for g in self.w.client.get(f"{API}/settings", headers=self.h).json()]
        self.assertEqual(keys[:2], ["email", "business_hours"])  # modules may add more (e.g. "shop")
        self.assertEqual(self.w.client.get(f"{API}/settings/nope", headers=self.h).status_code, 404)

    def test_business_hours_defaults_and_validation(self):
        body = self.w.client.get(f"{API}/settings/business_hours", headers=self.h).json()["values"]
        self.assertEqual(body["timezone"], "America/Chicago")
        self.assertEqual(body["days"]["mon"], {"open": "09:00", "close": "17:00"})
        self.assertIsNone(body["days"]["sun"])
        bad = self.w.client.put(f"{API}/settings/business_hours", headers=self.h, json={"timezone": "Mars/Base"})
        self.assertEqual(bad.status_code, 422)
        self.assertIn("time zone", bad.json()["detail"])
        bad = self.w.client.put(f"{API}/settings/business_hours", headers=self.h,
                                json={"days": {"mon": {"open": "18:00", "close": "09:00"}}})
        self.assertEqual(bad.status_code, 422)
        ok = self.w.client.put(f"{API}/settings/business_hours", headers=self.h,
                               json={"days": {"sat": {"open": "10:00", "close": "14:00"}}, "holidays": ["2026-12-25"]})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["values"]["days"]["sat"], {"open": "10:00", "close": "14:00"})
        self.assertIsNone(ok.json()["values"]["days"]["mon"])  # days is replaced as a whole

    def test_email_secret_is_encrypted_and_never_returned(self):
        res = self.w.client.put(f"{API}/settings/email", headers=self.h, json={"enabled": True, "smtp_host": ""})
        self.assertEqual(res.status_code, 422)
        self.assertIn("SMTP host", res.json()["detail"])
        res = self.w.client.put(f"{API}/settings/email", headers=self.h, json={
            "enabled": True, "smtp_host": "mail.example.com", "smtp_user": "crm@example.com",
            "smtp_password": "s3cret-pass", "from_address": "crm@example.com", "daily_limit": 200})
        self.assertEqual(res.status_code, 200, res.text)
        values = res.json()["values"]
        self.assertNotIn("smtp_password", values)
        self.assertTrue(values["smtp_password_set"])

        from sqlalchemy import select

        from app.modules.settings.models import AppSetting
        from app.modules.settings.service import SettingsService

        raw = run(lambda s: s.scalar(select(AppSetting.value).where(AppSetting.key == "email")))
        self.assertTrue(raw["smtp_password"].startswith("enc:"))
        self.assertNotIn("s3cret", raw["smtp_password"])
        self.assertEqual(run(lambda s: SettingsService(s).get_model("email")).smtp_password, "s3cret-pass")

        # saving without a password keeps the stored one
        self.w.client.put(f"{API}/settings/email", headers=self.h, json={"from_name": "WCW Team", "smtp_password": ""})
        self.assertEqual(run(lambda s: SettingsService(s).get_model("email")).smtp_password, "s3cret-pass")

        audit = self.w.client.get(f"{API}/audit", headers=self.h, params={"action": "settings.email"}).json()["items"]
        self.assertTrue(audit)
        self.assertNotIn("s3cret", str(audit))

    def test_send_test_email_reports_result(self):
        self.w.client.put(f"{API}/settings/email", headers=self.h, json={
            "smtp_host": "mail.example.com", "from_address": "crm@example.com", "smtp_password": "x-pass-123"})
        with mock.patch("app.modules.settings.router.SmtpEmailSender.send", side_effect=OSError("connection refused")):
            res = self.w.client.post(f"{API}/settings/email/test", headers=self.h, json={"to": "me@example.com"})
        self.assertEqual(res.json(), {"ok": False, "detail": "OSError: connection refused"})
        with mock.patch("app.modules.settings.router.SmtpEmailSender.send", new=mock.AsyncMock()) as sent:
            res = self.w.client.post(f"{API}/settings/email/test", headers=self.h, json={"to": "me@example.com"})
        self.assertTrue(res.json()["ok"])
        mail = sent.call_args.args[0]
        self.assertEqual(mail.to, "me@example.com")


if __name__ == "__main__":
    unittest.main()
