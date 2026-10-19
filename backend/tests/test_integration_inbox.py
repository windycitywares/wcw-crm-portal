"""The unified inbox (SPEC §3.9): the mailboxes the CRM reads — setting one up, the encrypted password,
the "can we reach it?" test — and the `inbox` job turning the mail it finds (and whatever came with it)
into tickets.

The mailbox itself is never real here: the `InboundMailbox` interface is stubbed (the protocol in the
pure tests, the whole mailbox in the job's), so nothing in this file opens a socket.
"""

import asyncio
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from mimetypes import guess_type
from unittest import mock

from tests.support import API, World, reset_limits, run, skip_unless_db


def mail_bytes(*, sender: str = "Jane Doe <jane@example.com>", to: str = "support@windycitywares.com",
               subject: str = "Where is my order?", body: str = "My parcel hasn't arrived.",
               message_id: str | None = None, in_reply_to: str | None = None,
               references: tuple[str, ...] = (), auto_submitted: str | None = None,
               when: datetime | None = None,
               attachments: tuple[tuple[str, bytes], ...] = ()) -> bytes:
    """A real RFC 822 message, so what the tests read is what a mail client would have written.

    An attachment is `(filename, its bytes)`; the type comes from the name, as a mail client would say it.
    """
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = message_id or make_msgid(domain="example.com")
    if when is not None:
        msg["Date"] = format_datetime(when)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)
    if auto_submitted:
        msg["Auto-Submitted"] = auto_submitted
    msg.set_content(body)
    for name, data in attachments:
        maintype, subtype = (guess_type(name)[0] or "application/octet-stream").split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return msg.as_bytes()


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


class InboundMailTests(unittest.TestCase):
    """Reading mail: what the parser makes of a message, and what the IMAP client takes from the server.
    No database and no network — imaplib is stubbed out."""

    def test_a_plain_message_reads_as_itself(self):
        from app.integrations.email import parse_message

        raw = mail_bytes(sender="Jane Doe <JANE@Example.com>", subject="Where is my order?",
                         body="My parcel hasn't arrived.\n\nJane", message_id="<m-1@example.com>",
                         when=datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc))
        message = parse_message("7", raw)
        self.assertEqual(message.uid, "7")
        self.assertEqual(message.message_id, "m-1@example.com")  # brackets off: that is what we store
        self.assertEqual(message.subject, "Where is my order?")
        self.assertEqual((message.from_email, message.from_name), ("jane@example.com", "Jane Doe"))
        self.assertEqual(message.to_email, "support@windycitywares.com")
        self.assertIn("parcel hasn't arrived", message.text)
        self.assertEqual(message.date, datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc))
        self.assertIsNone(message.in_reply_to)

    def test_a_reply_knows_what_it_answers(self):
        from app.integrations.email import parse_message

        raw = mail_bytes(message_id="<m-2@example.com>", in_reply_to="<m-1@example.com>",
                         references=("<id-a@x.com>", "<m-1@example.com>"), subject="Re: Where is my order?")
        message = parse_message("8", raw)
        self.assertEqual(message.in_reply_to, "m-1@example.com")
        self.assertEqual(message.references, ("id-a@x.com", "m-1@example.com"))

    def test_html_mail_is_read_as_text(self):
        from app.integrations.email import parse_message

        msg = EmailMessage()
        msg["From"] = "jane@example.com"
        msg["To"] = "support@windycitywares.com"
        msg["Subject"] = "Where is my order?"
        msg["Message-ID"] = "<html@example.com>"
        msg.set_content("<html><body><p>My parcel <b>hasn't</b> arrived.</p>"
                        "<script>track()</script></body></html>", subtype="html")
        message = parse_message("9", msg.as_bytes())
        self.assertEqual(message.text, "My parcel hasn't arrived.")
        self.assertNotIn("track", message.text)

    def test_a_message_with_no_id_and_nothing_but_an_attachment_still_reads(self):
        from email.mime.application import MIMEApplication

        from app.integrations.email.inbound import NO_TEXT, parse_message

        msg = EmailMessage()
        msg["From"] = "jane@example.com"
        msg["To"] = "support@windycitywares.com"
        msg["Subject"] = "My receipt"
        msg["Auto-Submitted"] = "auto-replied"
        msg.set_type("multipart/mixed")
        msg.attach(MIMEApplication(b"%PDF-1.4", _subtype="pdf", name="receipt.pdf"))
        message = parse_message("10", msg.as_bytes())
        self.assertIsNone(message.message_id)  # the client forgot to say — the job makes one up
        self.assertEqual(message.auto_submitted, "auto-replied")
        self.assertEqual(message.text, NO_TEXT)

    def test_a_file_that_came_with_a_message_is_read_with_it(self):
        from app.integrations.email import parse_message

        raw = mail_bytes(body="Here is the damage.", attachments=(("damage.jpg", b"\xff\xd8\xffjpeg-bytes"),))
        message = parse_message("11", raw)
        self.assertIn("damage", message.text)
        self.assertEqual([(f.filename, f.content_type, f.data) for f in message.attachments],
                         [("damage.jpg", "image/jpeg", b"\xff\xd8\xffjpeg-bytes")])

    def test_only_named_parts_are_files(self):
        """An image a message's HTML points at is part of the message, not a file beside it."""
        from app.integrations.email import parse_message

        msg = EmailMessage()
        msg["From"] = "jane@example.com"
        msg["To"] = "support@windycitywares.com"
        msg["Subject"] = "Look at this"
        msg.set_content("<p>See the picture</p>", subtype="html")
        msg.add_related(b"\x89PNG-pixels", maintype="image", subtype="png", cid="<shot@example.com>")  # no name
        message = parse_message("12", msg.as_bytes())
        self.assertIn("See the picture", message.text)
        self.assertEqual(message.attachments, ())

    def test_an_empty_part_is_not_worth_a_file(self):
        from app.integrations.email import parse_message

        raw = mail_bytes(attachments=(("nothing.txt", b""),))
        self.assertEqual(parse_message("13", raw).attachments, ())

    def test_the_client_takes_unread_mail_and_marks_what_it_took(self):
        from app.integrations.email.inbound import ImapInboundMailbox, MailboxConfig

        raw = mail_bytes(message_id="<one@example.com>")
        client = mock.MagicMock()
        client.select.return_value = ("OK", [b"2"])

        def uid(command, *args):
            if command == "SEARCH":
                return "OK", [b"11 12"]
            if command == "FETCH" and args[0] == b"11":
                return "OK", [(b"11 (RFC822 {9}", raw), b")"]
            if command == "FETCH":
                return "OK", [b")"]  # a message the server wouldn't hand over
            return "OK", []

        client.uid.side_effect = uid
        mailbox = ImapInboundMailbox(MailboxConfig(host="h", username="me@x.com", password="p"))
        with mock.patch("app.integrations.email.inbound.imaplib.IMAP4_SSL", return_value=client):
            messages = asyncio.run(mailbox.unseen(limit=5))
            asyncio.run(mailbox.mark_seen(["11"]))
        self.assertEqual([m.uid for m in messages], ["11"])  # the unreadable one was left for next time
        self.assertEqual(messages[0].message_id, "one@example.com")
        client.select.assert_called_with("INBOX", readonly=False)  # writable: we mark what we take
        client.uid.assert_any_call("STORE", "11", "+FLAGS", "(\\Seen)")
        client.logout.assert_called()


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


@skip_unless_db
class InboxPollTests(unittest.TestCase):
    """The `inbox` job: what arrives on a mailbox becomes a conversation in the CRM. The mailbox is faked
    (the protocol is exercised above); only the address under test has any mail waiting in it."""

    cabinet: dict[str, list] = {}     # mailbox address -> what is waiting in it
    seen: dict[str, list[str]] = {}   # mailbox address -> the uids that were marked read
    boom: set[str] = set()            # mailbox addresses that refuse to be read

    class FakeInbox:
        """One mailbox, as the job sees it."""

        def __init__(self, config):
            self.config = config
            self.address = config.username or ""

        async def check(self):
            from app.integrations.email import MailboxStatus

            return MailboxStatus(folder=self.config.folder, messages=0, unseen=0)

        async def unseen(self, limit=50):
            from app.integrations.email import MailboxError

            if self.address in InboxPollTests.boom:
                raise MailboxError("The mailbox refused us (LOGIN failed)")
            return InboxPollTests.cabinet.get(self.address, [])[:limit]

        async def mark_seen(self, uids):
            InboxPollTests.seen.setdefault(self.address, []).extend(uids)

    @classmethod
    def setUpClass(cls):
        import tempfile

        from app.integrations.email import set_mailbox_factory
        from app.integrations.files import LocalFileStore, set_store_factory
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        set_mailbox_factory(cls.FakeInbox)
        # The files a message brings are kept on a disk: a throwaway directory stands in for the server's.
        cls.files_dir = tempfile.mkdtemp(prefix="wcw-crm-files-")
        set_store_factory(lambda: LocalFileStore(cls.files_dir))

    @classmethod
    def tearDownClass(cls):
        import shutil

        from app.integrations.email import set_mailbox_factory
        from app.integrations.files import set_store_factory

        set_mailbox_factory(None)
        set_store_factory(None)
        shutil.rmtree(cls.files_dir, ignore_errors=True)

    def setUp(self):
        reset_limits()
        InboxPollTests.cabinet = {}
        InboxPollTests.seen = {}
        InboxPollTests.boom = set()

    # ---- helpers ---------------------------------------------------------------------------------
    def mailbox(self, **data):
        """A mailbox for the CRM to read, set up the way an admin would."""
        data.setdefault("address", self.w.email("inbox"))
        data.setdefault("imap_host", "imap.example.com")
        data.setdefault("imap_password", "s3cret-pass")
        res = self.w.client.post(f"{API}/inbox/accounts", headers=self.manager_h, json=data)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def deliver(self, address, *raw):
        """Put mail into a mailbox, parsed by the real parser, so a test sees what the job sees."""
        from app.integrations.email import parse_message

        self.cabinet[address] = [parse_message(str(i + 1), body) for i, body in enumerate(raw)]

    def poll(self):
        from app.modules.inbox.poller import InboxPoller

        return run(lambda s: InboxPoller(s).poll())

    def tickets(self, subject):
        return self.w.client.get(f"{API}/tickets", headers=self.support_h,
                                 params={"channel": "email", "state": "all", "q": subject}).json()["items"]

    def messages(self, ticket_id):
        return self.w.client.get(f"{API}/tickets/{ticket_id}/messages", headers=self.support_h).json()

    def attachments(self, ticket_id):
        res = self.w.client.get(f"{API}/entities/ticket/{ticket_id}/attachments", headers=self.support_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    # ---- tests -----------------------------------------------------------------------------------
    def test_mail_opens_a_ticket_with_its_customer_and_its_own_time(self):
        account = self.mailbox()
        address, subject = account["address"], f"Where is my order {self.w.sfx}?"
        jane = self.w.email("jane")
        self.deliver(address, mail_bytes(sender=f"Jane Doe <{jane}>", to=address, subject=subject,
                                         body="My parcel hasn't arrived.", message_id="<m-1@example.com>",
                                         when=datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)))

        line = self.poll()
        self.assertIn("filed 1 (1 new)", line)

        found = self.tickets(subject)
        self.assertEqual(len(found), 1, found)
        ticket = found[0]
        self.assertEqual((ticket["channel"], ticket["subject"], ticket["status"]), ("email", subject, "new"))
        self.assertIsNone(ticket["assignee_id"])  # the system opened it, so nobody owns it yet
        self.assertTrue(ticket["created_at"].startswith("2026-10-14"))  # the mail's time, not ours

        customer = self.w.client.get(f"{API}/customers/{ticket['customer_id']}",
                                     headers=self.manager_h).json()
        self.assertEqual((customer["email"], customer["first_name"], customer["last_name"]), (jane, "Jane", "Doe"))
        self.assertEqual([(m["direction"], m["from_email"], m["to_email"]) for m in self.messages(ticket["id"])],
                         [("inbound", jane, address)])
        timeline = self.w.client.get(f"{API}/entities/customer/{ticket['customer_id']}/timeline",
                                     headers=self.manager_h).json()["items"]
        self.assertTrue(any("added from email" in row["title"] for row in timeline), timeline)

        # the id is stored (one of a kind), what was stored was marked read, and the poll was noted
        from sqlalchemy import select

        from app.modules.tickets.models import TicketMessage

        stored = run(lambda s: s.scalar(select(TicketMessage.external_id)
                                        .where(TicketMessage.ticket_id == ticket["id"])))
        self.assertEqual(stored, "m-1@example.com")
        self.assertEqual(self.seen[address], ["1"])
        after = self.w.client.get(f"{API}/inbox/accounts/{account['id']}", headers=self.manager_h).json()
        self.assertIsNotNone(after["last_polled_at"])
        self.assertIsNone(after["last_error"])

    def test_what_came_with_the_message_is_kept_with_its_ticket(self):
        """A photo of the damage is part of the conversation: it is kept, and it can be read back."""
        from app.integrations.email.inbound import NO_TEXT

        account = self.mailbox()
        address, subject = account["address"], f"Damage photo {self.w.sfx}"
        jane = self.w.email("jane")
        self.deliver(address, mail_bytes(sender=f"Jane <{jane}>", to=address, subject=subject, body="",
                                         message_id="<p-1@example.com>",
                                         attachments=(("damage.jpg", b"jpeg-bytes"), ("receipt.pdf", b"%PDF-1.4"))))

        self.assertIn("files 2", self.poll())

        ticket = self.tickets(subject)[0]
        kept = self.attachments(ticket["id"])
        self.assertEqual([(a["filename"], a["content_type"], a["size"], a["source"]) for a in kept],
                         [("damage.jpg", "image/jpeg", 10, "email"), ("receipt.pdf", "application/pdf", 8, "email")])
        # each file says which message it came with, so the conversation can point back to it
        message_id = self.messages(ticket["id"])[0]["id"]
        self.assertEqual([a["message_id"] for a in kept], [message_id, message_id])
        # nothing to read, so the message says what it was rather than looking empty
        self.assertEqual(self.messages(ticket["id"])[0]["body"], NO_TEXT)

        got = self.w.client.get(f"{API}/attachments/{kept[0]['id']}", headers=self.support_h)
        self.assertEqual(got.content, b"jpeg-bytes")
        self.assertEqual(got.headers["content-disposition"],
                         'attachment; filename="damage.jpg"; filename*=UTF-8\'\'damage.jpg')

    def test_files_on_an_answer_join_the_ticket_it_answers(self):
        account = self.mailbox()
        address, subject = account["address"], f"Follow-up {self.w.sfx}"
        jane = self.w.email("jane")
        self.deliver(address, mail_bytes(sender=f"Jane <{jane}>", to=address, subject=subject,
                                         message_id="<f-1@example.com>"))
        self.poll()
        ticket = self.tickets(subject)[0]
        self.deliver(address, mail_bytes(sender=f"Jane <{jane}>", to=address, subject=f"Re: {subject}",
                                         body="The second one:", message_id="<f-2@example.com>",
                                         in_reply_to="<f-1@example.com>",
                                         attachments=(("second.jpg", b"more-bytes"),)))

        self.assertIn("filed 1 (0 new)", self.poll())

        self.assertEqual([a["filename"] for a in self.attachments(ticket["id"])], ["second.jpg"])
        # the file belongs to the answer that carried it, not to the message that opened the ticket
        self.assertEqual([a["message_id"] for a in self.attachments(ticket["id"])],
                         [self.messages(ticket["id"])[-1]["id"]])
        self.assertEqual(len(self.tickets(subject)), 1)  # it joined the thread, it didn't open a ticket

    def test_a_file_too_big_to_keep_is_counted_not_lost(self):
        """The message says what was left behind instead of arriving with a photo quietly missing."""
        account = self.mailbox()
        address, subject = account["address"], f"Two photos {self.w.sfx}"
        self.deliver(address, mail_bytes(to=address, subject=subject, body="Here they are.",
                                         message_id="<b-1@example.com>",
                                         attachments=(("huge.jpg", b"x" * 20), ("small.jpg", b"ok"))))

        with mock.patch("app.modules.inbox.filing.MAX_FILE_BYTES", 4):
            line = self.poll()

        self.assertIn("filed 1 (1 new)", line)
        self.assertIn("files 1", line)
        ticket = self.tickets(subject)[0]
        self.assertEqual([a["filename"] for a in self.attachments(ticket["id"])], ["small.jpg"])
        self.assertEqual(self.messages(ticket["id"])[0]["body"],
                         "Here they are.\n\n(1 file came with this message and couldn't be kept)")

    def test_our_reply_carries_its_own_id_and_the_answer_joins_the_thread(self):
        account = self.mailbox()
        address, subject = account["address"], f"Damaged box {self.w.sfx}"
        jane = self.w.email("jane")
        self.deliver(address, mail_bytes(sender=f"Jane Doe <{jane}>", to=address, subject=subject,
                                         message_id="<q-1@example.com>"))
        self.poll()
        ticket = self.tickets(subject)[0]

        # a reply of ours goes out with an id of its own, answering the customer's message
        before = len(self.w.mail.sent)
        sent = self.w.client.post(f"{API}/tickets/{ticket['id']}/messages", headers=self.support_h,
                                 json={"body": "A new one is on its way.", "kind": "reply"})
        self.assertEqual(sent.status_code, 201, sent.text)
        self.assertEqual(len(self.w.mail.sent), before + 1)
        reply = self.w.mail.sent[-1]
        ours = reply.headers["Message-ID"].strip("<>")
        self.assertTrue(ours.startswith(ticket["number"]), ours)
        self.assertEqual(reply.headers["In-Reply-To"], "<q-1@example.com>")
        self.assertEqual(reply.headers["References"], "<q-1@example.com>")

        # the customer answers: same ticket, reopened, and no second ticket made
        self.assertEqual(self.w.client.patch(f"{API}/tickets/{ticket['id']}", headers=self.support_h,
                                             json={"status": "resolved"}).status_code, 200)
        self.deliver(address, mail_bytes(sender=f"Jane Doe <{jane}>", to=address, subject=f"Re: {subject}",
                                         message_id="<q-2@example.com>", in_reply_to=f"<{ours}>",
                                         references=("<q-1@example.com>", f"<{ours}>")))
        self.assertIn("filed 1 (0 new)", self.poll())
        self.assertEqual(len(self.tickets(subject)), 1)
        back = self.w.client.get(f"{API}/tickets/{ticket['id']}", headers=self.support_h).json()
        self.assertEqual((back["status"], back["resolved_at"]), ("open", None))
        self.assertEqual([m["direction"] for m in self.messages(ticket["id"])],
                         ["inbound", "outbound", "inbound"])

    def test_the_same_message_is_never_stored_twice(self):
        account = self.mailbox()
        address, subject = account["address"], f"Repeat {self.w.sfx}"
        self.deliver(address, mail_bytes(to=address, subject=subject, message_id="<dupe@example.com>"))
        self.assertIn("filed 1 (1 new)", self.poll())

        # the mailbox still has it (a crash between storing and marking read looks exactly like this)
        self.assertIn("skipped 1", self.poll())
        self.assertEqual(len(self.tickets(subject)), 1)
        self.assertEqual(len(self.messages(self.tickets(subject)[0]["id"])), 1)

    def test_a_subject_line_says_which_ticket_a_message_belongs_to(self):
        account = self.mailbox()
        address, subject = account["address"], f"Wrong size {self.w.sfx}"
        jane = self.w.email("jane")
        self.deliver(address, mail_bytes(sender=jane, to=address, subject=subject, message_id="<s-1@example.com>"))
        self.poll()
        ticket = self.tickets(subject)[0]

        # a client that lost the headers still writes our ticket number into the subject
        self.deliver(address, mail_bytes(sender=jane, to=address, subject=f"Re: [{ticket['number']}] {subject}",
                                        message_id="<s-2@example.com>"))
        self.assertIn("filed 1 (0 new)", self.poll())
        self.assertEqual(len(self.tickets(subject)), 1)
        self.assertEqual(len(self.messages(ticket["id"])), 2)

    def test_a_machine_writing_to_a_machine_is_left_alone(self):
        account = self.mailbox()
        address, subject = account["address"], f"Out of office {self.w.sfx}"
        self.deliver(address, mail_bytes(to=address, subject=subject, message_id="<auto@example.com>",
                                         auto_submitted="auto-replied"))

        line = self.poll()
        self.assertIn("filed 0 (0 new)", line)
        self.assertIn("skipped 1", line)
        self.assertEqual(self.tickets(subject), [])
        self.assertEqual(self.seen[address], ["1"])  # but it is marked read: a robot must not come back

    def test_somebody_we_already_know_is_not_added_twice(self):
        kept = self.w.client.post(f"{API}/customers", headers=self.manager_h, json={
            "first_name": "Jane", "last_name": "Doe", "email": self.w.email("jane"),
            "alt_emails": [self.w.email("jane-old")]}).json()
        account = self.mailbox()
        address, subject = account["address"], f"Old address {self.w.sfx}"
        self.deliver(address, mail_bytes(sender=f"Jane Doe <{kept['alt_emails'][0]}>", to=address,
                                         subject=subject, message_id="<alt@example.com>"))
        self.poll()
        self.assertEqual(self.tickets(subject)[0]["customer_id"], kept["id"])

    def test_a_mailbox_that_won_t_open_says_why_then_clears_it(self):
        account = self.mailbox()
        address = account["address"]
        self.boom.add(address)
        self.assertIn("failed 1", self.poll())
        after = self.w.client.get(f"{API}/inbox/accounts/{account['id']}", headers=self.manager_h).json()
        self.assertIn("refused us", after["last_error"])
        self.assertIsNotNone(after["last_polled_at"])

        # and once it works, the note is cleared by the next good run
        self.boom.discard(address)
        self.deliver(address, mail_bytes(to=address, subject=f"Back {self.w.sfx}", message_id="<ok@example.com>"))
        self.poll()
        cleared = self.w.client.get(f"{API}/inbox/accounts/{account['id']}", headers=self.manager_h).json()
        self.assertIsNone(cleared["last_error"])

    def test_a_quiet_run_has_nothing_to_say(self):
        account = self.mailbox()
        self.assertIsNone(self.poll())  # nothing arrived: the job log stays quiet
        after = self.w.client.get(f"{API}/inbox/accounts/{account['id']}", headers=self.manager_h).json()
        self.assertIsNotNone(after["last_polled_at"])  # but it did look


if __name__ == "__main__":
    unittest.main()
