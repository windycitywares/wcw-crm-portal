"""Where the files are kept (SPEC §4.2, attachments).

One small interface, so the CRM never speaks to a disk directly: `file_store()` hands back something
that can `save` a file (and say what it is called from then on), `read` it back and `delete` it, and
`set_store_factory(...)` lets tests stand in for the disk — exactly as the email integrations do with
`mailbox_for` / `set_email_sender`.

The one implementation writes to the server's own disk (`attachments_dir`, outside the checkout: a
deploy replaces the checkout, and a customer's photo must outlive it). A file is stored under the
sha256 of its own bytes, so the same PDF sent twice is kept once — the *rows* that point at a file are
what say who it belongs to (see `app.modules.attachments`), and `AttachmentService.delete` drops the
stored file with the last row that pointed at it.

Blocking calls run in a thread, so a busy inbox job doesn't hold up the event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

# A storage key is the file's sha256 and nothing else: never a name a caller (or a mail) supplied, so a
# key can't be talked into pointing somewhere else on the disk.
KEY = re.compile(r"^[0-9a-f]{64}$")


class FileStoreError(Exception):
    """The file couldn't be stored, read or dropped. The message is meant for whoever reads the log."""


class FileStore(Protocol):
    """Files by their content, not by their name: `save` returns the key the file is known by."""

    async def save(self, data: bytes) -> str: ...

    async def read(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalFileStore:
    """The server's own disk: `{root}/{aa}/{sha256}`, the first two digits spreading the files."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not KEY.match(key):
            raise FileStoreError("That is not a file key")
        return self.root / key[:2] / key

    # ---- blocking work, always called from a thread -------------------------------------------------
    def _save_sync(self, data: bytes) -> str:
        key = hashlib.sha256(data).hexdigest()
        path = self._path(key)
        if path.exists():
            return key  # the same bytes are already here: that is the point of naming files by content
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Written aside and moved into place: a half-written file must never look like a whole one.
            part = path.parent / f".{key}.part"
            part.write_bytes(data)
            os.replace(part, path)
        except OSError as exc:
            raise FileStoreError(f"Couldn't store the file ({exc})") from None
        return key

    def _read_sync(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as exc:
            raise FileStoreError(f"The file isn't on the server any more ({exc})") from None

    def _delete_sync(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            return  # already gone: the caller wanted it gone
        except OSError as exc:
            raise FileStoreError(f"Couldn't drop the file ({exc})") from None

    # ---- the interface ------------------------------------------------------------------------------
    async def save(self, data: bytes) -> str:
        return await asyncio.to_thread(self._save_sync, data)

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._read_sync, key)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)


_factory: Callable[[], FileStore] | None = None


def set_store_factory(factory: Callable[[], FileStore] | None) -> None:
    """Tests (and anywhere else files are kept): stand in for the disk."""
    global _factory
    _factory = factory


def file_store() -> FileStore:
    if _factory is not None:
        return _factory()
    return LocalFileStore(get_settings().attachments_dir)
