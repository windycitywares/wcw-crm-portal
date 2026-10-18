"""Admin → the mailboxes the CRM reads (SPEC §3.9): setup, the encrypted password, permissions, and the
"can we reach it?" test. Reading the mail itself is the next batch."""

import asyncio
import unittest
from unittest import mock

from tests.support import API, World, reset_limits, run, skip_unless_db


class FakeMailbox:
    """Stands in for a real mailbox: the interface, not the protocol. It records what it was told."""

    def __init__(self, config, *, status=None, error=None):
        self.config, self.status, self.error = config, status, error

    async def check(self):
        if self.error is not None:
            raise self.error
        return self.status


class MailboxConfigTests(unittest.TestCase):
    """How a saved row becomes something that can be dialled — and what the IMAP client does with the
    server's answer. No database and no network: imaplib is stubbed out."""

    def _account(self, **overrides):
        from app.modules.inbox.models import EmailAccount

        values = {"address": "support@windycitywares.com", "imap_host": "imap.example.com", "imap_port": 993,
                  "imap_security": "ssl", "imap_user": None, "folder": "INBOX"}
        return EmailAccount(**{**values, **overrides})

    def test_a_mailbox_without_its_own_username_is_read_as_its_address(self):
        from app.modules.inbox.service import config_for

        config = config_for(self._account(), password="s3cret-pass")
        self.assertEqual((config.host, config.port, config.security, config.username, config.folder),
                         ("imap.example.com", 993, "ssl", "support@windycitywares.com", "INBOX"))
        self.assertEqual(config_for(self._account(imap_user="crm-reader"), password="x").username, "crm-reader")

    def test_check_reads_the_folder_and_leaves_it_alone(self):
        from app.integrations.email.inbound import ImapInboundMailbox, MailboxConfig

        client = mock.MagicMock()
        client.select.return_value = ("OK", [b"57"])
        client.search.return_value = ("OK", [b"1 2 3"])
        config = MailboxConfig(host="imap.example.com", username="me@example.com", password="p")
        with mock.patch("app.integrations.email.inbound.imaplib.IMAP4_SSL", return_value=client) as connect:
            status = asyncio.run(ImapInboundMailbox(config).check())
        self.assertEqual((status.folder, status.messages, status.unseen), ("INBOX", 57, 3))
        connect.assert_called_once_with("imap.example.com", 993, ssl_context=mock.ANY, timeout=20)
        client.login.assert_called_once_with("me@example.com", "p")
        client.select.assert_called_once_with("INBOX", readonly=True)
        client.search.assert_called_once_with(None, "UNSEEN")
        client.logout.assert_called_once_with()

    def test_an_unreachable_server_says_which_one(self):
        from app.integrations.email.inbound import ImapInboundMailbox, MailboxConfig, MailboxError

        config = MailboxConfig(host="imap.example.com", port=993)
        with mock.patch("app.integrations.email.inbound.imaplib.IMAP4_SSL",
                        side_effect=OSError("Connection refused")):
            with self.assertRaises(MailboxError) as caught:
                asyncio.run(ImapInboundMailbox(config).check())
        self.assertIn("imap.example.com:993", str(caught.exception))
        self.assertIn("Connection refused", str(caught.exception))

    def test_a_refused_login_and_a_closed_folder_are_readable(self):
        import imaplib

        from app.integrations.email.inbound import ImapInboundMailbox, MailboxConfig, MailboxError

        config = MailboxConfig(host="imap.example.com", username="me@example.com", password="wrong")
        client = mock.MagicMock()
        client.login.side_effect = imaplib.IMAP4.error("LOGIN failed: authentication failed")
        with mock.patch("app.integrations.email.inbound.imaplib.IMAP4_SSL", return_value=client):
            with self.assertRaises(MailboxError) as caught:
                asyncio.run(ImapInboundMailbox(config).check())
        self.assertIn("authentication failed", str(caught.exception))

        client = mock.MagicMock()
        client.select.return_value = ("NO", [b"[NONEXISTENT] Mailbox doesn't exist"])
        with mock.patch("app.integrations.email.inbound.imaplib.IMAP4_SSL", return_value=client):
            with self.assertRaises(MailboxError) as caught:
                asyncio.run(ImapInboundMailbox(MailboxConfig(host="h", folder="Nope")).check())
        self.assertIn("Nope", str(caught.exception))
        client.logout.assert_called_once_with()  # a failure still says goodbye


@skip_unless_db
class InboxAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = World()
        reset_limits()
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.ro, cls.ro_h = cls.w.user_with_token("read_only")

    def setUp(self):
        reset_limits()

    def account(self, **data):
        data.setdefault("address", self.w.email("support"))
        data.setdefault("imap_host", "imap.example.com")
        data.setdefault("imap_password", "s3cret-pass")
        res = self.w.client.post(f"{API}/inbox/accounts", headers=self.admin_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_only_admin_and_manager_set_mailboxes_up(self):
        # support lives in the inbox; the credentials are not theirs to change
        self.assertEqual(self.w.client.get(f"{API}/inbox/accounts", headers=self.support_h).status_code, 403)
        self.assertEqual(self.w.client.post(f"{API}/inbox/accounts", headers=self.ro_h, json={
            "address": "reader@example.com", "imap_host": "imap.example.com", "imap_password": "x",
        }).status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/inbox/accounts", headers=self.manager_h).status_code, 200)

    def test_setup_validates_and_never_echoes_the_password(self):
        address = self.w.email("hello")
        made = self.account(address=address, display_name="Windy City Wares Support", folder="INBOX")
        self.assertEqual((made["address"], made["display_name"], made["imap_security"], made["is_active"]),
                         (address, "Windy City Wares Support", "ssl", True))
        self.assertNotIn("imap_password", made)
        self.assertNotIn("s3cret", str(made))

        # the same mailbox twice, however it is typed
        self.assertEqual(self.w.client.post(f"{API}/inbox/accounts", headers=self.admin_h, json={
            "address": address.upper(), "imap_host": "imap.example.com", "imap_password": "x"}).status_code, 422)
        for bad in ({"imap_password": ""}, {"imap_security": "carrier-pigeon"}, {"imap_port": 0},
                    {"imap_host": "   "}):
            res = self.w.client.post(f"{API}/inbox/accounts", headers=self.admin_h,
                                     json={"address": self.w.email("bad"), "imap_host": "imap.example.com",
                                           "imap_password": "x", **bad})
            self.assertEqual(res.status_code, 422, f"{bad} -> {res.status_code}")

        listed = self.w.client.get(f"{API}/inbox/accounts", headers=self.admin_h).json()
        self.assertIn(address, [a["address"] for a in listed])
        self.assertEqual(self.w.client.get(f"{API}/inbox/accounts/{made['id']}", headers=self.admin_h).status_code, 200)
        self.assertEqual(self.w.client.get(f"{API}/inbox/accounts/99999999", headers=self.admin_h).status_code, 404)

    def test_the_password_is_encrypted_and_a_blank_one_keeps_it(self):
        from sqlalchemy import select

        from app.core.security import SecretBox
        from app.modules.inbox.models import EmailAccount

        made = self.account()
        stored = run(lambda s: s.scalar(select(EmailAccount.imap_password_enc)
                                        .where(EmailAccount.id == made["id"])))
        self.assertNotIn("s3cret", stored)
        self.assertEqual(SecretBox().decrypt(stored), "s3cret-pass")

        # a patch without a password (or with a blank one) keeps the stored secret
        kept = self.w.client.patch(f"{API}/inbox/accounts/{made['id']}", headers=self.admin_h,
                                   json={"display_name": "Support", "imap_password": ""})
        self.assertEqual(kept.status_code, 200, kept.text)
        self.assertEqual(kept.json()["display_name"], "Support")
        self.assertEqual(SecretBox().decrypt(run(lambda s: s.scalar(
            select(EmailAccount.imap_password_enc).where(EmailAccount.id == made["id"])))), "s3cret-pass")

        changed = self.w.client.patch(f"{API}/inbox/accounts/{made['id']}", headers=self.admin_h,
                                      json={"imap_password": "new-pass-99", "is_active": False})
        self.assertEqual(changed.json()["is_active"], False)
        self.assertEqual(SecretBox().decrypt(run(lambda s: s.scalar(
            select(EmailAccount.imap_password_enc).where(EmailAccount.id == made["id"])))), "new-pass-99")

        audit = self.w.client.get(f"{API}/audit", headers=self.admin_h,
                                  params={"action": "inbox.account_update"}).json()["items"]
        changed_secret = [row for row in audit if "imap_password" in (row.get("changes") or {})]
        self.assertTrue(changed_secret)
        self.assertNotIn("new-pass-99", str(audit))
        self.assertNotIn("s3cret", str(audit))

    def test_the_connection_test_reports_what_the_mailbox_says(self):
        from app.integrations.email.inbound import MailboxError, MailboxStatus

        made = self.account()
        seen = {}

        def fake(config):
            seen.update(config=config)
            return FakeMailbox(config, status=MailboxStatus(folder="INBOX", messages=1234, unseen=7))

        with mock.patch("app.modules.inbox.service.mailbox_for", fake):
            res = self.w.client.post(f"{API}/inbox/accounts/{made['id']}/test", headers=self.admin_h)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual({k: res.json()[k] for k in ("ok", "folder", "messages", "unseen")},
                         {"ok": True, "folder": "INBOX", "messages": 1234, "unseen": 7})
        self.assertIn("1,234 messages", res.json()["detail"])
        # the CRM logs in as the mailbox itself, with the password it stored
        self.assertEqual((seen["config"].host, seen["config"].username, seen["config"].password),
                         ("imap.example.com", made["address"], "s3cret-pass"))

        for error in (MailboxError("The mailbox refused us (authentication failed)"), OSError("broken")):
            with self.subTest(error=type(error).__name__):
                with mock.patch("app.modules.inbox.service.mailbox_for",
                                lambda config, e=error: FakeMailbox(config, error=e)):
                    res = self.w.client.post(f"{API}/inbox/accounts/{made['id']}/test", headers=self.admin_h)
                self.assertEqual(res.status_code, 200, res.text)  # a failed test is an answer, not an API error
                self.assertFalse(res.json()["ok"])
                self.assertIn("broken" if isinstance(error, OSError) else "refused", res.json()["detail"])

        self.assertEqual(self.w.client.post(f"{API}/inbox/accounts/99999999/test",
                                            headers=self.admin_h).status_code, 404)

    def test_deleting_a_mailbox_takes_its_secret_with_it(self):
        from sqlalchemy import func, select

        from app.modules.inbox.models import EmailAccount

        made = self.account()
        self.assertEqual(self.w.client.delete(f"{API}/inbox/accounts/{made['id']}",
                                              headers=self.admin_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/inbox/accounts/{made['id']}",
                                           headers=self.admin_h).status_code, 404)
        left = run(lambda s: s.scalar(select(func.count()).select_from(EmailAccount)
                                      .where(EmailAccount.address == made["address"])))
        self.assertEqual(left, 0)  # deleted, not archived: nothing is left holding a password


if __name__ == "__main__":
    unittest.main()
