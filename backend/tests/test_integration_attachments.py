"""Attachments (SPEC §4.2): the files kept against a record, for every record type.

The shared block notes and the timeline use — `(entity_type, entity_id)` and the record's own
permissions — so this file is about two things: what a record's files look like over the API (and who
may see, read and drop them), and the disk behind it. The disk is a throwaway directory, never the
server's; the files the *inbox* keeps are exercised in `test_integration_inbox.py`.
"""

import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.support import API, World, reset_limits, run, skip_unless_db


def stored(root: str) -> list[Path]:
    """What is actually on the disk under a storage root (the files, not the directories)."""
    return [p for p in Path(root).rglob("*") if p.is_file()]


class LocalFileStoreTests(unittest.TestCase):
    """A file is kept under its own content, so the same file sent twice is stored once."""

    def setUp(self):
        from app.integrations.files import LocalFileStore

        self.dir = tempfile.mkdtemp(prefix="wcw-crm-files-")
        self.store = LocalFileStore(self.dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_file_is_kept_under_the_hash_of_its_own_bytes(self):
        key = asyncio.run(self.store.save(b"hello"))
        self.assertEqual(key, hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(asyncio.run(self.store.read(key)), b"hello")
        self.assertEqual(len(stored(self.dir)), 1)

    def test_the_same_bytes_twice_are_kept_once(self):
        first = asyncio.run(self.store.save(b"hello"))
        second = asyncio.run(self.store.save(b"hello"))
        self.assertEqual(first, second)
        self.assertEqual(len(stored(self.dir)), 1)

    def test_a_dropped_file_is_gone_and_dropping_it_twice_is_not_an_error(self):
        key = asyncio.run(self.store.save(b"hello"))
        asyncio.run(self.store.delete(key))
        self.assertEqual(stored(self.dir), [])
        asyncio.run(self.store.delete(key))  # already gone: the caller wanted it gone

    def test_a_file_that_is_not_on_the_disk_says_so(self):
        from app.integrations.files import FileStoreError

        with self.assertRaises(FileStoreError):
            asyncio.run(self.store.read(hashlib.sha256(b"never-written").hexdigest()))

    def test_a_key_that_is_not_a_key_is_refused(self):
        """A key comes from this module (a sha256), never from a caller: it can't point anywhere else."""
        from app.integrations.files import FileStoreError

        for bad in ("../etc/passwd", "not-a-hash", "", "../../secrets"):
            with self.assertRaises(FileStoreError):
                asyncio.run(self.store.read(bad))


class AttachmentRulesTests(unittest.TestCase):
    """The small rules about names, types and sizes — no database, no disk."""

    def test_what_a_stranger_called_a_file_is_never_a_path(self):
        from app.modules.attachments.service import safe_name

        self.assertEqual(safe_name("../../etc/passwd"), "passwd")
        self.assertEqual(safe_name("C:\\Users\\me\\holiday.jpg"), "holiday.jpg")
        self.assertEqual(safe_name("  my  photo\r\n.jpg "), "my photo .jpg")  # one line, no surprises
        self.assertEqual(safe_name(""), "file")
        self.assertEqual(safe_name("..."), "file")
        self.assertEqual(len(safe_name("x" * 400)), 255)  # the column is 255 wide

    def test_a_type_a_stranger_wrote_is_not_echoed_into_a_header(self):
        from app.modules.attachments.service import clean_type

        self.assertEqual(clean_type("image/png"), "image/png")
        self.assertEqual(clean_type("Image/PNG"), "image/png")
        for junk in (None, "", "no-slash", "text/html; charset=utf-8", 'x\r\nSet-Cookie: a=b'):
            self.assertEqual(clean_type(junk), "application/octet-stream")

    def test_an_empty_or_oversized_file_is_refused_before_it_is_stored(self):
        import shutil

        from app.core.exceptions import ValidationFailedError
        from app.integrations.files import LocalFileStore
        from app.modules.attachments import service as attachments

        root = tempfile.mkdtemp(prefix="wcw-crm-files-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        # The session is never reached: both of these are refused before anything is added or stored.
        keeper = attachments.AttachmentService(object(), store=LocalFileStore(root))
        with mock.patch.object(attachments, "MAX_BYTES", 4):
            with self.assertRaises(ValidationFailedError):
                asyncio.run(keeper.keep("ticket", 1, filename="huge.jpg", data=b"12345"))
        with self.assertRaises(ValidationFailedError):
            asyncio.run(keeper.keep("ticket", 1, filename="nothing.txt", data=b""))
        self.assertEqual(stored(root), [])


@skip_unless_db
class AttachmentApiTests(unittest.TestCase):
    """One shared block, every record type: the files on a record, who may read them and who may drop
    them. The bytes are kept in a throwaway directory, never on the server's disk."""

    @classmethod
    def setUpClass(cls):
        from app.integrations.files import LocalFileStore, set_store_factory
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.support, cls.support_h = cls.w.user_with_token("support")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")          # may see tickets, not change them
        cls.marketing, cls.marketing_h = cls.w.user_with_token("marketing")  # tickets are none of its business
        cls.files_dir = tempfile.mkdtemp(prefix="wcw-crm-files-")
        set_store_factory(lambda: LocalFileStore(cls.files_dir))

    @classmethod
    def tearDownClass(cls):
        import shutil

        from app.integrations.files import set_store_factory

        set_store_factory(None)
        shutil.rmtree(cls.files_dir, ignore_errors=True)

    def setUp(self):
        reset_limits()

    # ---- helpers ---------------------------------------------------------------------------------
    def ticket(self):
        res = self.w.client.post(f"{API}/tickets", headers=self.support_h, json={"subject": "Photos"})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def customer(self, first: str):
        res = self.w.client.post(f"{API}/customers", headers=self.manager_h,
                                 json={"first_name": first, "email": self.w.email(first.lower())})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def keep(self, entity_type: str, entity_id: int, *, filename: str = "damage.jpg", data: bytes = b"jpeg-bytes",
             content_type: str | None = "image/jpeg", source: str = "email"):
        """Put a file on a record the way the inbox job does, and hand back what was kept."""
        from app.modules.attachments.service import AttachmentService

        return run(lambda s: AttachmentService(s).keep(entity_type, entity_id, filename=filename, data=data,
                                                      content_type=content_type, source=source, commit=True))

    def list_for(self, entity_type: str, entity_id: int, headers):
        return self.w.client.get(f"{API}/entities/{entity_type}/{entity_id}/attachments", headers=headers)

    def put_file(self, entity_type: str, entity_id: int, *, filename: str = "notes.txt",
                 data: bytes = b"staff-file", content_type: str = "text/plain", headers=None):
        """Put a file on a record the way a member of staff does, over the API."""
        return self.w.client.post(
            f"{API}/entities/{entity_type}/{entity_id}/attachments",
            headers=self.support_h if headers is None else headers,
            files={"file": (filename, data, content_type)})

    # ---- tests -----------------------------------------------------------------------------------
    def test_a_record_s_files_are_listed_for_whoever_may_see_the_record(self):
        ticket = self.ticket()
        self.keep("ticket", ticket["id"])

        res = self.list_for("ticket", ticket["id"], self.support_h)
        self.assertEqual(res.status_code, 200, res.text)
        rows = res.json()
        self.assertEqual([(r["entity_type"], r["filename"], r["content_type"], r["size"], r["source"])
                          for r in rows], [("ticket", "damage.jpg", "image/jpeg", 10, "email")])
        self.assertIsNone(rows[0]["created_by"])  # the system filed it; the mail says who sent it

        # anybody who may see the ticket may see what came with it — reading isn't changing
        self.assertEqual(self.list_for("ticket", ticket["id"], self.sales_h).status_code, 200)
        # somebody with no business in tickets at all is not told the record exists
        self.assertEqual(self.list_for("ticket", ticket["id"], self.marketing_h).status_code, 403)
        # an unknown record type, and a record that isn't there, are both "not found"
        self.assertEqual(self.list_for("pigeon", 1, self.support_h).status_code, 404)
        self.assertEqual(self.list_for("ticket", 9_999_999, self.support_h).status_code, 404)

    def test_a_file_is_handed_over_as_a_download_with_the_name_it_arrived_with(self):
        ticket = self.ticket()
        row = self.keep("ticket", ticket["id"], filename="Rechnung Müller.pdf", data=b"%PDF-1.4",
                        content_type="application/pdf")

        got = self.w.client.get(f"{API}/attachments/{row.id}", headers=self.support_h)
        self.assertEqual(got.content, b"%PDF-1.4")
        self.assertEqual(got.headers["content-type"], "application/pdf")
        self.assertEqual(got.headers["content-disposition"],
                         'attachment; filename="Rechnung M_ller.pdf"; '
                         "filename*=UTF-8''Rechnung%20M%C3%BCller.pdf")
        self.assertEqual(got.headers["x-content-type-options"], "nosniff")

        # a file that says it is a page is still handed over as a file, and never sniffed into one
        page = self.keep("ticket", ticket["id"], filename="evil.html", data=b"<script>alert(1)</script>",
                         content_type="text/html")
        got = self.w.client.get(f"{API}/attachments/{page.id}", headers=self.support_h)
        self.assertEqual(got.headers["content-type"], "text/html")
        self.assertTrue(got.headers["content-disposition"].startswith("attachment;"))
        self.assertEqual(got.headers["x-content-type-options"], "nosniff")

    def test_a_file_goes_only_with_the_last_record_that_pointed_at_it(self):
        """Two rows may hold the same bytes (a customer sends the same photo twice); the disk copy is
        dropped with the last of them, and dropping one of two changes nothing for the other."""
        first, second = self.ticket(), self.ticket()
        a = self.keep("ticket", first["id"], data=b"same-photo")
        b = self.keep("ticket", second["id"], data=b"same-photo")
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(stored(self.files_dir)), 1)

        self.assertEqual(self.w.client.delete(f"{API}/attachments/{a.id}", headers=self.support_h).status_code, 204)
        self.assertEqual(len(stored(self.files_dir)), 1)  # still wanted by the other record
        self.assertEqual(self.w.client.get(f"{API}/attachments/{b.id}", headers=self.support_h).content,
                         b"same-photo")
        self.assertEqual(self.list_for("ticket", first["id"], self.support_h).json(), [])

        self.assertEqual(self.w.client.delete(f"{API}/attachments/{b.id}", headers=self.support_h).status_code, 204)
        self.assertEqual(stored(self.files_dir), [])  # nobody wants it now: the bytes are gone

    def test_dropping_a_file_is_changing_the_record_and_is_written_down(self):
        ticket = self.ticket()
        row = self.keep("ticket", ticket["id"])

        # whoever may read the record may read the file …
        self.assertEqual(self.w.client.get(f"{API}/attachments/{row.id}", headers=self.sales_h).status_code, 200)
        # … but dropping it changes the record, so it takes the right to change it
        self.assertEqual(self.w.client.delete(f"{API}/attachments/{row.id}", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.w.client.delete(f"{API}/attachments/{row.id}",
                                              headers=self.marketing_h).status_code, 403)
        self.assertEqual(self.w.client.get(f"{API}/attachments/{row.id}", headers=self.support_h).status_code, 200)

        self.assertEqual(self.w.client.delete(f"{API}/attachments/{row.id}", headers=self.support_h).status_code, 204)
        self.assertEqual(self.w.client.get(f"{API}/attachments/{row.id}", headers=self.support_h).status_code, 404)
        self.assertEqual(self.w.client.delete(f"{API}/attachments/{row.id}", headers=self.support_h).status_code, 404)

        timeline = self.w.client.get(f"{API}/entities/ticket/{ticket['id']}/timeline",
                                     headers=self.support_h).json()["items"]
        self.assertIn("attachment.deleted", [row["kind"] for row in timeline])
        audit = self.w.client.get(f"{API}/audit", headers=self.manager_h,
                                  params={"action": "attachment.delete"}).json()["items"]
        self.assertTrue(any(r["entity_type"] == "ticket" and r["entity_id"] == ticket["id"] for r in audit), audit)

    def test_a_member_of_staff_can_put_a_file_on_a_record(self):
        ticket = self.ticket()

        res = self.put_file("ticket", ticket["id"], filename="Receipt.pdf", data=b"%PDF-1.4",
                            content_type="application/pdf")
        self.assertEqual(res.status_code, 201, res.text)
        row = res.json()
        self.assertEqual((row["filename"], row["content_type"], row["size"], row["source"]),
                         ("Receipt.pdf", "application/pdf", 8, "upload"))
        self.assertEqual(row["created_by"], self.support["id"])  # staff know who added it
        self.assertIsNone(row["message_id"])                     # ... and an upload has no message to point at
        self.assertEqual([r["id"] for r in self.list_for("ticket", ticket["id"], self.support_h).json()],
                         [row["id"]])

        # the upload has no message to explain it, so the record says so itself
        timeline = self.w.client.get(f"{API}/entities/ticket/{ticket['id']}/timeline",
                                     headers=self.support_h).json()["items"]
        self.assertIn("attachment.added", [line["kind"] for line in timeline])
        audit = self.w.client.get(f"{API}/audit", headers=self.manager_h,
                                  params={"action": "attachment.upload"}).json()["items"]
        self.assertTrue(any(r["entity_type"] == "ticket" and r["entity_id"] == ticket["id"] for r in audit), audit)

    def test_adding_a_file_takes_the_right_to_change_the_record(self):
        ticket = self.ticket()
        # a ticket sales may see but not change: no upload …
        self.assertEqual(self.put_file("ticket", ticket["id"], headers=self.sales_h).status_code, 403)
        # … and no team at all: not told the record is there
        self.assertEqual(self.put_file("ticket", ticket["id"], headers=self.marketing_h).status_code, 403)
        # an unknown record type, and a record that isn't there, are both "not found"
        self.assertEqual(self.put_file("pigeon", 1, headers=self.support_h).status_code, 404)
        self.assertEqual(self.put_file("ticket", 9_999_999, headers=self.support_h).status_code, 404)

    def test_an_uploaded_name_is_never_a_path_and_a_bad_file_is_refused(self):
        from app.modules.attachments import service as attachments

        ticket = self.ticket()
        row = self.put_file("ticket", ticket["id"], filename="../../etc/passwd",
                            data=b"x", content_type="nonsense").json()
        self.assertEqual(row["filename"], "passwd")
        self.assertEqual(row["content_type"], "application/octet-stream")  # an unusable type isn't echoed

        # the same size rule as the inbox's, checked before a byte is stored
        with mock.patch.object(attachments, "MAX_BYTES", 4):
            self.assertEqual(self.put_file("ticket", ticket["id"], data=b"12345").status_code, 422)
        self.assertEqual(self.put_file("ticket", ticket["id"], data=b"").status_code, 422)

    def test_the_same_file_uploaded_twice_is_kept_once(self):
        first, second = self.ticket(), self.ticket()
        before = len(stored(self.files_dir))
        one = self.put_file("ticket", first["id"], filename="photo.jpg", data=b"duplicate-bytes",
                            content_type="image/jpeg").json()
        two = self.put_file("ticket", second["id"], filename="photo.jpg", data=b"duplicate-bytes",
                            content_type="image/jpeg").json()
        self.assertNotEqual(one["id"], two["id"])
        self.assertEqual(len(stored(self.files_dir)), before + 1)  # one copy of the bytes, two rows

    def test_files_follow_a_record_into_the_one_it_is_merged_with(self):
        keep, dup = self.customer("Kate"), self.customer("K.")
        row = self.keep("customer", dup["id"])

        res = self.w.client.post(f"{API}/customers/{keep['id']}/merge", headers=self.manager_h,
                                 json={"other_id": dup["id"]})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual([r["id"] for r in self.list_for("customer", keep["id"], self.manager_h).json()], [row.id])
        self.assertEqual(self.list_for("customer", dup["id"], self.manager_h).status_code, 404)

    def test_the_files_of_one_record_are_not_the_files_of_another(self):
        one, two = self.ticket(), self.ticket()
        self.keep("ticket", one["id"], filename="one.jpg", data=b"one")
        self.keep("ticket", two["id"], filename="two.jpg", data=b"two")

        self.assertEqual([r["filename"] for r in self.list_for("ticket", one["id"], self.support_h).json()],
                         ["one.jpg"])
        self.assertEqual([r["filename"] for r in self.list_for("ticket", two["id"], self.support_h).json()],
                         ["two.jpg"])
