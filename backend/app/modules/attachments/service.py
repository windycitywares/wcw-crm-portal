"""Files kept against a record, for every record type (SPEC §4.2).

The same shared block as notes and the timeline: `(entity_type, entity_id)` says what a file hangs on
and `check_entity_access` says who may see it, so a feature that can hold a note can hold a file
without knowing anything about this module (`/entities/ticket/{id}/attachments`).

Reading a record's files asks for the record's *view* permission; adding or dropping one asks for its
*edit* permission — a file on a complaint changes the record either way, so it is a change, not a read.

The files themselves live behind `app.integrations.files`; here they are only ever kept by content, so
the same file sent twice is stored once, and the stored bytes are dropped with the last row that
pointed at them. A name that arrived with mail is written by a stranger: it is flattened to one line
for display and never used to find, open or write anything.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import check_entity_access
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.integrations.files import FileStore, FileStoreError, file_store
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService

from .models import Attachment
from .repository import AttachmentRepository
from .schemas import AttachmentOut

log = logging.getLogger("wcw.crm.attachments")

MAX_BYTES = 15 * 1024 * 1024  # one file: roomier than any photo or invoice a customer attaches
DEFAULT_TYPE = "application/octet-stream"  # what a file with no usable type of its own is handed back as
_TYPE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")


def safe_name(name: str) -> str:
    """What a file is called on screen: the last piece of whatever was given, on one line.

    A filename arrives from a mail client (or a browser) and is therefore written by a stranger; it is
    display text only — never a path, and never something to build a path from.
    """
    last = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
    flat = " ".join(last.split()).strip(".")
    return (flat[:255] or "file").strip() or "file"


def clean_type(value: str | None) -> str:
    """The type to hand a file back with. Anything that isn't a plain `type/subtype` is not echoed into
    a response header: it becomes the generic binary type."""
    cleaned = " ".join(str(value or "").split()).lower()
    return cleaned[:120] if _TYPE.match(cleaned) else DEFAULT_TYPE


class AttachmentService:
    def __init__(self, session: AsyncSession, *, store: FileStore | None = None):
        self.session = session
        self.repo = AttachmentRepository(session)
        self.timeline = TimelineService(session)
        self.audit = AuditService(session)
        self._store = store  # tests (and the jobs) may say where the bytes go; otherwise the disk

    @property
    def store(self) -> FileStore:
        return self._store if self._store is not None else file_store()

    async def keep(self, entity_type: str, entity_id: int, *, filename: str, data: bytes,
                   content_type: str | None = None, source: str = "upload", actor: Any = None,
                   message_id: int | None = None, commit: bool = False) -> AttachmentOut:
        """Keep one file against a record. The caller has already decided the record may hold it: the
        inbox job files what arrived on a mailbox, and an upload would have checked the record's own
        edit permission before calling this.

        `message_id` is the message that carried the file, when one did (a staff upload has none), so the
        conversation can point back to it.

        Raises `ValidationFailedError` for a file bigger than `MAX_BYTES` — the caller is expected to
        count those and carry on, not to lose the message they came with.
        """
        if not data:
            raise ValidationFailedError("An empty file isn't worth keeping")
        if len(data) > MAX_BYTES:
            raise ValidationFailedError(f"{safe_name(filename)} is larger than {MAX_BYTES // (1024 * 1024)} MB")
        key = await self.store.save(data)
        who = getattr(actor, "id", None)
        row = await self.repo.add(Attachment(
            entity_type=entity_type, entity_id=entity_id, message_id=message_id, filename=safe_name(filename),
            content_type=clean_type(content_type), size=len(data), sha256=key, source=source,
            created_by=who, updated_by=who,
        ))
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return AttachmentOut.model_validate(row)

    async def upload(self, user: Any, entity_type: str, entity_id: int, *, filename: str, data: bytes,
                     content_type: str | None = None) -> AttachmentOut:
        """Keep a file a member of staff attached to a record.

        Adding a file changes the record, so it takes the record's own *edit* permission, exactly as
        dropping one does — there is nothing new to grant. Unlike a file that came with a message, this
        one has no message to explain it, so the upload is written to the audit log and the timeline.
        """
        await check_entity_access(self.session, user, entity_type, entity_id, write=True)
        row = await self.keep(entity_type, entity_id, filename=filename, data=data,
                              content_type=content_type, source="upload", actor=user, commit=False)
        noted = {"attachment_id": row.id, "filename": row.filename, "size": row.size}
        await self.audit.record("attachment.upload", actor=user, entity_type=entity_type,
                                entity_id=entity_id, changes=noted)
        await self.timeline.record(entity_type, entity_id, "attachment.added",
                                   f"File added ({row.filename})", actor=user, data=noted)
        await self.session.commit()
        return row

    async def list_for(self, user: Any, entity_type: str, entity_id: int) -> list[AttachmentOut]:
        """A record's files, oldest first, for anyone who may see the record."""
        await check_entity_access(self.session, user, entity_type, entity_id, write=False)
        return [AttachmentOut.model_validate(a) for a in await self.repo.list_for(entity_type, entity_id)]

    async def _may_touch(self, user: Any, attachment_id: int, *, write: bool) -> Attachment:
        row = await self.repo.get(attachment_id)
        if row is None:
            raise NotFoundError("File not found")
        # The record the file hangs on decides who may reach it, not this module: nothing new to grant.
        await check_entity_access(self.session, user, row.entity_type, row.entity_id, write=write)
        return row

    async def download(self, user: Any, attachment_id: int) -> tuple[Attachment, bytes]:
        """One file's bytes, with the row that says what to call them."""
        row = await self._may_touch(user, attachment_id, write=False)
        try:
            data = await self.store.read(row.sha256)
        except FileStoreError as exc:
            raise NotFoundError(f"{row.filename} isn't on the server any more") from exc
        return row, data

    async def delete(self, user: Any, attachment_id: int) -> None:
        """Drop one file from a record. Whatever else points at the same bytes keeps them; the stored
        file goes only with the last row that did."""
        row = await self._may_touch(user, attachment_id, write=True)
        before = {"attachment_id": row.id, "filename": row.filename, "size": row.size}
        await self.repo.soft_delete(row)
        if await self.repo.count_stored(row.sha256) == 0:
            try:
                await self.store.delete(row.sha256)
            except FileStoreError as exc:
                log.warning("attachments: %s is still on the disk: %s", row.sha256, exc)  # not a wrong answer
        await self.audit.record("attachment.delete", actor=user, entity_type=row.entity_type,
                                entity_id=row.entity_id, changes=before)
        await self.timeline.record(row.entity_type, row.entity_id, "attachment.deleted",
                                   f"File removed ({row.filename})", actor=user, data=before)
        await self.session.commit()
