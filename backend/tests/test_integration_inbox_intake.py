"""Channels that aren't mailboxes (SPEC §3.9): a connector posts one signed message and it is filed
exactly like mail — the same customer, the same threading, the same ticket — carrying the channel it came
in on.

Nothing here opens a socket: the message is posted to the public route the way the shop's chat widget or
an Etsy poller would, signed with the secret both sides know (docs/INBOX_CHANNELS.md).
"""

import base64
import json
import time
import unittest
import uuid

from tests.support import API, World, reset_limits, run, skip_unless_db

SECRET = "c" * 48
INTAKE = f"{API}/inbox/messages"


class IntakePayloadTests(unittest.TestCase):
    """What a connector may post and what it may not: the schema, and the files it carries."""

    @staticmethod
    def parse(data):
        from app.modules.inbox.schemas import InboundMessageIn

        return InboundMessageIn.model_validate(data)

    @staticmethod
    def payload(**overrides):
        data = {"id": "chat-1", "channel": "live_chat", "body": "Do you ship to Canada?"}
        data.update(overrides)
        return data

    def test_the_sender_travels_as_from(self):
        message = self.parse(self.payload(**{"from": {"email": "jane@example.com", "name": "Jane Doe"}}))
        self.assertEqual(str(message.sender.email), "jane@example.com")
        self.assertEqual(message.sender.name, "Jane Doe")
        self.assertEqual(message.files, [])
        self.assertIsNone(message.thread)

    def test_a_message_from_nobody_the_crm_can_name_is_still_a_message(self):
        message = self.parse(self.payload())
        self.assertIsNone(message.sender.email)
        self.assertEqual(message.channel, "live_chat")

    def test_an_id_and_a_channel_are_required(self):
        from pydantic import ValidationError

        for data in ({}, {"id": "chat-1"}, {"channel": "live_chat"}):
            with self.assertRaises(ValidationError):
                self.parse(data)

    def test_more_files_than_a_message_may_bring_are_refused(self):
        from pydantic import ValidationError

        files = [{"filename": f"shot-{i}.png", "data": "aGk="} for i in range(11)]
        with self.assertRaises(ValidationError):
            self.parse(self.payload(files=files))

    def test_files_are_decoded_and_given_a_type(self):
        from app.modules.inbox.intake import InboxIntakeService

        message = self.parse(self.payload(files=[
            {"filename": "shot.png", "content_type": "image/png",
             "data": base64.b64encode(b"png-bytes").decode()},
            {"filename": "notes.txt", "data": base64.b64encode(b"hello").decode()},
        ]))
        files = InboxIntakeService._files(message)
        self.assertEqual([f.filename for f in files], ["shot.png", "notes.txt"])
        self.assertEqual((files[0].data, files[0].content_type), (b"png-bytes", "image/png"))
        self.assertEqual(files[1].content_type, "application/octet-stream")

    def test_a_file_that_is_not_base64_is_refused_not_guessed(self):
        from app.modules.inbox.intake import IntakeRejected, InboxIntakeService

        message = self.parse(self.payload(files=[{"filename": "shot.png", "data": "not base64!"}]))
        with self.assertRaises(IntakeRejected) as caught:
            InboxIntakeService._files(message)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("shot.png", caught.exception.detail)


@skip_unless_db
class InboxChannelTests(unittest.TestCase):
    """A connector posting a message: what it takes to be let in, and what the CRM makes of it."""

    @classmethod
    def setUpClass(cls):
        import tempfile

        from app.integrations.files import LocalFileStore, set_store_factory
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.admin, cls.admin_h = cls.w.user_with_token("admin")
        # The files a message brings are kept on a disk: a throwaway directory stands in for the server's.
        cls.files_dir = tempfile.mkdtemp(prefix="wcw-crm-files-")
        set_store_factory(lambda: LocalFileStore(cls.files_dir))
        cls.open_the_door()

    @classmethod
    def tearDownClass(cls):
        import shutil

        from app.integrations.files import set_store_factory

        set_store_factory(None)
        shutil.rmtree(cls.files_dir, ignore_errors=True)

    @classmethod
    def open_the_door(cls):
        """Switch the channels on, the way an admin does in Settings → Integrations."""
        res = cls.w.client.put(f"{API}/settings/inbox", headers=cls.admin_h,
                               json={"enabled": True, "ingest_secret": SECRET})
        assert res.status_code == 200, res.text

    def setUp(self):
        reset_limits()

    # ---- helpers ---------------------------------------------------------------------------------
    def send(self, payload, *, secret=SECRET, ts=None, raw=None):
        from app.integrations.signing import sign

        body = raw if raw is not None else json.dumps(payload).encode()
        stamp = int(time.time()) if ts is None else ts
        return self.w.client.post(INTAKE, content=body, headers={
            "content-type": "application/json", "x-wcw-timestamp": str(stamp),
            "x-wcw-signature": sign(secret, stamp, body)})

    def message(self, **overrides):
        payload = {"id": uuid.uuid4().hex, "channel": "live_chat", "body": "Do you ship to Canada?",
                   "at": "2026-10-14T09:30:00Z", "from": {"email": self.w.email("chat"), "name": "Nia Rowe"}}
        payload.update(overrides)
        return payload

    def ticket(self, ticket_id):
        res = self.w.client.get(f"{API}/tickets/{ticket_id}", headers=self.support_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def messages(self, ticket_id):
        return self.w.client.get(f"{API}/tickets/{ticket_id}/messages", headers=self.support_h).json()

    def attachments(self, ticket_id):
        res = self.w.client.get(f"{API}/entities/ticket/{ticket_id}/attachments", headers=self.support_h)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    # ---- tests -----------------------------------------------------------------------------------
    def test_a_chat_message_opens_a_ticket_of_its_own(self):
        email = self.w.email("chat")
        res = self.send(self.message(**{"from": {"email": email, "name": "Nia Rowe"}}))
        self.assertEqual(res.status_code, 201, res.text)
        body = res.json()
        self.assertEqual((body["status"], body["files"]), ("filed", 0))
        self.assertIsInstance(body["ticket_id"], int)

        ticket = self.ticket(body["ticket_id"])
        self.assertEqual((ticket["channel"], ticket["status"]), ("live_chat", "new"))
        self.assertEqual(ticket["subject"], "Live chat: Do you ship to Canada?")
        self.assertIsNone(ticket["assignee_id"])            # the system filed it, so nobody owns it yet
        self.assertTrue(ticket["created_at"].startswith("2026-10-14"))  # when it was sent, not read
        customer = self.w.client.get(f"{API}/customers/{ticket['customer_id']}",
                                     headers=self.support_h).json()
        self.assertEqual((customer["email"], customer["first_name"], customer["last_name"]),
                         (email, "Nia", "Rowe"))
        self.assertEqual([(m["direction"], m["from_email"]) for m in self.messages(ticket["id"])],
                         [("inbound", email)])
        timeline = self.w.client.get(f"{API}/entities/customer/{ticket['customer_id']}/timeline",
                                     headers=self.support_h).json()["items"]
        self.assertTrue(any("added from live chat" in row["title"] for row in timeline), timeline)

    def test_an_answer_joins_the_ticket_it_answers(self):
        opener = self.message()
        first = self.send(opener).json()
        answer = {**self.message(body="Great, thanks!"), "thread": opener["id"], "from": opener["from"]}
        res = self.send(answer)
        self.assertEqual(res.status_code, 201, res.text)
        self.assertEqual(res.json()["ticket_id"], first["ticket_id"])
        self.assertEqual([m["body"] for m in self.messages(first["ticket_id"])],
                         ["Do you ship to Canada?", "Great, thanks!"])
        self.assertEqual(self.ticket(first["ticket_id"])["status"], "open")  # a customer writing reopens it

    def test_a_re_post_is_a_duplicate_not_a_second_ticket(self):
        payload = self.message()
        first = self.send(payload)
        self.assertEqual(first.status_code, 201)
        again = self.send(payload)
        self.assertEqual(again.status_code, 200, again.text)  # retrying is not an error
        self.assertEqual(again.json()["status"], "duplicate")
        self.assertEqual(again.json()["ticket_id"], first.json()["ticket_id"])
        self.assertEqual(len(self.messages(first.json()["ticket_id"])), 1)

    def test_the_signature_is_required(self):
        self.assertEqual(self.send(self.message(), secret="w" * 48).status_code, 401)
        self.assertEqual(self.send(self.message(), ts=int(time.time()) - 3600).status_code, 401)
        unsigned = self.w.client.post(INTAKE, content=b"{}", headers={"content-type": "application/json"})
        self.assertEqual(unsigned.status_code, 401)

    def test_a_message_that_is_not_a_message_is_refused(self):
        self.assertEqual(self.send(None, raw=b"not json").status_code, 400)
        self.assertEqual(self.send({}).status_code, 400)

    def test_a_channel_the_crm_does_not_know_is_refused(self):
        res = self.send(self.message(channel="carrier_pigeon"))
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("ticket channels", res.json()["detail"])

    def test_an_etsy_message_files_as_etsy(self):
        res = self.send(self.message(channel="etsy", subject="Order 1042"))
        self.assertEqual(res.status_code, 201, res.text)
        ticket = self.ticket(res.json()["ticket_id"])
        self.assertEqual((ticket["channel"], ticket["subject"]), ("etsy", "Order 1042"))

    def test_a_file_that_came_with_a_chat_is_kept_with_the_ticket(self):
        res = self.send(self.message(body="It arrived broken.", files=[
            {"filename": "damage.png", "content_type": "image/png",
             "data": base64.b64encode(b"png-bytes").decode()}]))
        self.assertEqual(res.status_code, 201, res.text)
        self.assertEqual(res.json()["files"], 1)
        kept = self.attachments(res.json()["ticket_id"])
        self.assertEqual([(a["filename"], a["content_type"], a["size"], a["source"]) for a in kept],
                         [("damage.png", "image/png", 9, "live_chat")])
        got = self.w.client.get(f"{API}/attachments/{kept[0]['id']}", headers=self.support_h)
        self.assertEqual(got.content, b"png-bytes")

    def test_a_chat_with_nothing_but_a_photo_says_so(self):
        from app.integrations.email.inbound import NO_TEXT

        res = self.send(self.message(body="", files=[
            {"filename": "shot.png", "data": base64.b64encode(b"png-bytes").decode()}]))
        self.assertEqual(self.messages(res.json()["ticket_id"])[0]["body"], NO_TEXT)

    def test_switched_off_says_so(self):
        off = self.w.client.put(f"{API}/settings/inbox", headers=self.admin_h, json={"enabled": False})
        self.assertEqual(off.status_code, 200, off.text)
        try:
            res = self.send(self.message())
            self.assertEqual(res.status_code, 503, res.text)
        finally:
            self.open_the_door()
