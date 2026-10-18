"""Reading a mailbox (SPEC §3.9, the unified inbox).

One small interface, so the inbox's job and its tests never speak IMAP themselves: `mailbox_for(config)`
hands back something that can be asked about the mailbox it points at. `check()` is what the admin's
"test connection" needs — the folder opens and how much is waiting in it. The messages themselves
(`fetch()`) arrive with the email-in batch, and are the same object.

IMAP is blocking and lives in the standard library, so the implementation hands the work to a thread —
exactly as the outbox's SMTP sender does. Nothing here knows about the database: an `EmailAccount` row
becomes a `MailboxConfig`, and that is all this layer is told.
"""

from __future__ import annotations

import asyncio
import imaplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

TIMEOUT = 20


class MailboxError(Exception):
    """The mailbox couldn't be reached or read. The message is meant for whoever is looking at the screen."""


@dataclass(frozen=True)
class MailboxConfig:
    host: str
    port: int = 993
    security: str = "ssl"  # ssl | starttls | none
    username: str = ""
    password: str = ""
    folder: str = "INBOX"
    timeout: int = TIMEOUT


@dataclass(frozen=True)
class MailboxStatus:
    """What a mailbox says about itself: the folder that opened and what is in it."""

    folder: str
    messages: int
    unseen: int


class InboundMailbox(Protocol):
    async def check(self) -> MailboxStatus: ...


def _reason(data: object) -> str:
    """IMAP answers come back as bytes ("NO [AUTHENTICATIONFAILED] ...") — make them readable."""
    if isinstance(data, (list, tuple)):
        data = data[0] if data else b""
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return str(data or "")


class ImapInboundMailbox:
    def __init__(self, config: MailboxConfig):
        self.config = config

    def _connect(self) -> imaplib.IMAP4:
        c = self.config
        try:
            if c.security == "ssl":
                return imaplib.IMAP4_SSL(c.host, c.port, ssl_context=ssl.create_default_context(),
                                         timeout=c.timeout)
            client = imaplib.IMAP4(c.host, c.port, timeout=c.timeout)
            if c.security == "starttls":
                client.starttls(ssl_context=ssl.create_default_context())
            return client
        except OSError as exc:  # includes socket.gaierror, ConnectionRefusedError and ssl.SSLError
            raise MailboxError(f"Can't reach {c.host}:{c.port} ({exc})") from None

    def _check_sync(self) -> MailboxStatus:
        c = self.config
        client = self._connect()
        try:
            try:
                if c.username:
                    client.login(c.username, c.password)
                typ, data = client.select(c.folder, readonly=True)
            except imaplib.IMAP4.error as exc:
                raise MailboxError(f"The mailbox refused us ({exc})") from None
            if typ != "OK":
                raise MailboxError(f"The folder {c.folder} can't be opened ({_reason(data)})")
            messages = int(data[0]) if data and data[0] else 0
            typ, data = client.search(None, "UNSEEN")  # readonly: a test must not mark anything read
            unseen = len(data[0].split()) if typ == "OK" and data and data[0] else 0
            return MailboxStatus(folder=c.folder, messages=messages, unseen=unseen)
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001 - a failed goodbye must not hide the real answer
                pass

    async def check(self) -> MailboxStatus:
        return await asyncio.to_thread(self._check_sync)


_factory: Callable[[MailboxConfig], InboundMailbox] | None = None


def set_mailbox_factory(factory: Callable[[MailboxConfig], InboundMailbox] | None) -> None:
    """Tests (and any other source of mail): stand in for a real mailbox."""
    global _factory
    _factory = factory


def mailbox_for(config: MailboxConfig) -> InboundMailbox:
    if _factory is not None:
        return _factory(config)
    return ImapInboundMailbox(config)
