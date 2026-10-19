"""Reading a mailbox (SPEC §3.9, the unified inbox).

One small interface, so the inbox job and its tests never speak IMAP themselves: `mailbox_for(config)`
hands back something that can be asked about the mailbox it points at — `check()` (what the admin's
"test connection" needs: the folder opens, and what is waiting in it), `unseen()` (the messages still
unread, oldest first) and `mark_seen()` (called once they are safely in the database, so nothing is
read twice and nothing is lost).

IMAP is blocking and lives in the standard library, so the implementation hands its work to a thread —
exactly as the outbox's SMTP sender does. Nothing here knows about the database: an `EmailAccount` row
becomes a `MailboxConfig`, and that is all this layer is told.
"""

from __future__ import annotations

import asyncio
import imaplib
import logging
import re
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Protocol

log = logging.getLogger("wcw.crm.email.inbound")

TIMEOUT = 20
# What a message with no text of its own (a screenshot, a wrapped PDF) becomes in a ticket.
NO_TEXT = "(no message text — an attachment came with it)"

# A Message-ID, with or without its angle brackets. Anything else in the header is somebody's comment.
_ID = re.compile(r"<([^<>\s]+@[^<>\s]+)>")


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


@dataclass(frozen=True)
class MailFile:
    """One file that came with a message: what the sender called it, what it is, and its bytes.

    `data` is what was in the message itself — nothing here fetches anything, so a mailbox that hands
    over a message hands over everything in it. A file with no name of its own is not a file beside the
    message (it is a part of the message, e.g. an image its HTML points at), so it isn't one of these.
    """

    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class InboundMessage:
    """One message, as the CRM needs it: who wrote it, what it says, the files it came with, and the ids
    that thread it.

    `message_id` is the sender's own `Message-ID` with the angle brackets taken off (that is what we
    store and match on); it is None only when the sender didn't provide one.
    """

    uid: str
    subject: str
    text: str
    message_id: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    to_email: str | None = None
    date: datetime | None = None
    in_reply_to: str | None = None
    references: tuple[str, ...] = ()
    auto_submitted: str | None = None  # the sender's own "a machine wrote this" header, if it has one
    attachments: tuple[MailFile, ...] = ()


class _Text(HTMLParser):
    """Enough HTML to read a message written in it: text in, tags out, script and style skipped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.skipping += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "blockquote"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.skipping:
            self.skipping -= 1

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)


def _plain(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def _id(value: object) -> str | None:
    """The `Message-ID` out of a header: angle brackets (and any comment around them) off."""
    text = str(value or "").strip()
    if not text:
        return None
    match = _ID.search(text)
    if match:
        return match.group(1)
    bare = text.strip("<>").strip()
    return bare if "@" in bare and not set(bare) & set(" \t<>") else None


def _address(value: object) -> tuple[str | None, str | None]:
    """(address, display name) out of a `From`/`To` header, the address lower-cased."""
    name, address = parseaddr(str(value or ""))
    return (address.strip().lower() or None), (" ".join(name.split()) or None)


def _when(msg: object) -> datetime | None:
    """When the message was written, if the header says something readable."""
    try:
        parsed = msg.get("Date")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a broken Date header must not lose the message
        return None
    if isinstance(parsed, datetime):
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    try:
        return parsedate_to_datetime(str(parsed or ""))
    except (ValueError, TypeError, OverflowError):
        # Malformed, empty or absurd dates are not worth losing the message over.
        return None


def _body(msg: object) -> str:
    """The message's own words: `text/plain` if it has any, else the HTML with its tags taken out."""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))  # type: ignore[attr-defined]
        content = part.get_content() if part is not None else None
    except Exception:  # noqa: BLE001 - an unreadable charset or part is not worth losing the ticket over
        log.debug("email: could not read message body", exc_info=True)
        return ""
    if content is None:
        return ""
    if part.get_content_type() != "text/html":
        return str(content)
    return _plain(str(content))


def _files(msg: object) -> tuple[MailFile, ...]:
    """Every part with a name of its own: what a customer attached, and what their client called it.

    A part with no name is part of the message — its text, or an image its HTML points at — so it is not
    a file beside it. Nothing here limits what it collects: the inbox job decides what is worth keeping
    (and says what it left behind), and the caller sees one message either way.
    """
    try:
        parts = list(msg.walk())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a message that can't be walked is a message with no files we can read
        log.debug("email: could not walk message parts", exc_info=True)
        return ()
    found: list[MailFile] = []
    for part in parts:
        try:
            if part.get_content_maintype() == "multipart":
                continue
            name = part.get_filename()
            payload = part.get_payload(decode=True) if name else None
            kind = part.get_content_type() if name else ""
        except Exception:  # noqa: BLE001 - one unreadable part must not cost us the message
            log.debug("email: skipping unreadable message part", exc_info=True)
            continue
        if not name or not payload:
            continue  # no name (not a file), or nothing in it: not worth a row
        found.append(MailFile(filename=str(name), content_type=str(kind or ""), data=payload))
    return tuple(found)


def parse_message(uid: str, raw: bytes) -> InboundMessage:
    """Turn one raw message into the fields the CRM keeps.

    Never raises: mail is written by strangers with every mail client ever made, so whatever can be read
    is read and the rest is left blank. A message with no text at all (an attachment and nothing else)
    says so, rather than arriving as an empty ticket.
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    from_email, from_name = _address(msg.get("From"))
    to_email, _ = _address(msg.get("To"))
    files = _files(msg)
    text = _body(msg).strip()
    if not text:
        text = NO_TEXT if files else ""
    return InboundMessage(
        uid=uid,
        subject=" ".join(str(msg.get("Subject") or "").split()),
        text=text,
        message_id=_id(msg.get("Message-ID")),
        from_email=from_email,
        from_name=from_name,
        to_email=to_email,
        date=_when(msg),
        in_reply_to=_id(msg.get("In-Reply-To")),
        references=tuple(i for i in (_id(v) for v in str(msg.get("References") or "").split()) if i),
        auto_submitted=" ".join(str(msg.get("Auto-Submitted") or "").split()) or None,
        attachments=files,
    )


class InboundMailbox(Protocol):
    async def check(self) -> MailboxStatus: ...

    async def unseen(self, limit: int = 50) -> list[InboundMessage]: ...

    async def mark_seen(self, uids: Sequence[str]) -> None: ...


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

    # ---- talking to the server (blocking; always called from a thread) ---------------------------
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

    def _login(self, client: imaplib.IMAP4) -> None:
        c = self.config
        try:
            if c.username:
                client.login(c.username, c.password)
        except imaplib.IMAP4.error as exc:
            raise MailboxError(f"The mailbox refused us ({exc})") from None

    def _select(self, client: imaplib.IMAP4, *, readonly: bool) -> int:
        """Open the folder and say how many messages are in it. A test opens it read-only."""
        c = self.config
        try:
            typ, data = client.select(c.folder, readonly=readonly)
        except imaplib.IMAP4.error as exc:
            raise MailboxError(f"The folder {c.folder} can't be opened ({exc})") from None
        if typ != "OK":
            raise MailboxError(f"The folder {c.folder} can't be opened ({_reason(data)})")
        return int(data[0]) if data and data[0] else 0

    def _bye(self, client: imaplib.IMAP4) -> None:
        try:
            client.logout()
        except Exception:  # noqa: BLE001 - a failed goodbye must not hide the real answer
            log.debug("email: IMAP logout failed (non-fatal)", exc_info=True)

    # ---- the three things a mailbox is asked -----------------------------------------------------
    def _check_sync(self) -> MailboxStatus:
        c = self.config
        client = self._connect()
        try:
            self._login(client)
            messages = self._select(client, readonly=True)  # a test marks nothing read
            typ, data = client.search(None, "UNSEEN")
            unseen = len(data[0].split()) if typ == "OK" and data and data[0] else 0
            return MailboxStatus(folder=c.folder, messages=messages, unseen=unseen)
        finally:
            self._bye(client)

    def _unseen_sync(self, limit: int) -> list[InboundMessage]:
        client = self._connect()
        try:
            self._login(client)
            self._select(client, readonly=False)  # writable: what we take, we mark read
            try:
                typ, data = client.uid("SEARCH", None, "UNSEEN")
            except imaplib.IMAP4.error as exc:
                raise MailboxError(f"Can't list the mail in {self.config.folder} ({exc})") from None
            ids = (data[0].split() if typ == "OK" and data and data[0] else [])[:limit]  # oldest first
            picked = []
            for uid in ids:
                try:
                    typ, data = client.uid("FETCH", uid, "(RFC822)")
                except imaplib.IMAP4.error:
                    continue  # unreadable right now: it stays unseen and the next run tries again
                if typ == "OK" and data and isinstance(data[0], tuple):
                    picked.append(parse_message(uid.decode(), data[0][1]))
            return picked
        finally:
            self._bye(client)

    def _mark_seen_sync(self, uids: Sequence[str]) -> None:
        client = self._connect()
        try:
            self._login(client)
            self._select(client, readonly=False)
            try:
                client.uid("STORE", ",".join(uids), "+FLAGS", "(\\Seen)")
            except imaplib.IMAP4.error as exc:
                raise MailboxError(f"Couldn't mark the mail as read ({exc})") from None
        finally:
            self._bye(client)

    # ---- the interface --------------------------------------------------------------------------
    async def check(self) -> MailboxStatus:
        return await asyncio.to_thread(self._check_sync)

    async def unseen(self, limit: int = 50) -> list[InboundMessage]:
        return await asyncio.to_thread(self._unseen_sync, limit)

    async def mark_seen(self, uids: Sequence[str]) -> None:
        if uids:
            await asyncio.to_thread(self._mark_seen_sync, list(uids))


_factory: Callable[[MailboxConfig], InboundMailbox] | None = None


def set_mailbox_factory(factory: Callable[[MailboxConfig], InboundMailbox] | None) -> None:
    """Tests (and any other source of mail): stand in for a real mailbox."""
    global _factory
    _factory = factory


def mailbox_for(config: MailboxConfig) -> InboundMailbox:
    if _factory is not None:
        return _factory(config)
    return ImapInboundMailbox(config)
