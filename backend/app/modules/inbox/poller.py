"""Email arriving on the mailboxes the CRM reads (SPEC §3.9, the unified inbox).

The `inbox` job, once a minute: for every mailbox that is switched on, take the mail it hasn't read yet
(oldest first) and file each message — opening a ticket for somebody who writes in, joining the thread
for somebody answering us. *Filing* is `filing.py`, which the channels that aren't mailboxes use too, so
mail and a chat message land in a ticket by the same rules. What was taken is then marked read in the
mailbox, so the next run doesn't see it again; the `Message-ID` is stored either way, so even a double
take cannot double a message.

A run never drains a mailbox: it takes what it can and leaves the rest for the next minute. One message
that can't be filed doesn't stop the others (and stays unread to be retried), and one unreachable mailbox
doesn't stop the others either — what went wrong is written on the mailbox (`last_error`) where the admin
who set it up can see it.

Two things are deliberately *not* done here. Automatic mail (an out-of-office reply, a robot answering a
robot) is skipped rather than filed: a machine isn't a customer. And spam is left alone — a human reads
the inbox the CRM fills, so filtering it out is a policy decision for a later batch, not a quiet rule here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecretBox
from app.integrations.email import InboundMessage, MailboxConfig, MailboxError, mailbox_for
from app.shared.time import utcnow

from .filing import Filed, Incoming, MessageFiler
from .models import EmailAccount
from .repository import EmailAccountRepository
from .service import account_password, config_for

log = logging.getLogger("wcw.crm.inbox")

PER_RUN = 50  # messages taken from one mailbox in a run; the rest wait for the next minute


def _why(exc: Exception) -> str:
    return str(exc) if isinstance(exc, MailboxError) else f"{type(exc).__name__}: {exc}"


@dataclass(frozen=True)
class Mailbox:
    """One mailbox to read: everything the job needs, taken off the row before any of it can go stale —
    a rollback part-way through a run expires loaded rows, and the rest of the run must not care."""

    id: int
    address: str
    config: MailboxConfig


@dataclass
class Polled:
    """What one mailbox gave us in a run."""

    filed: int = 0    # messages stored: a ticket opened or a thread joined
    opened: int = 0   # of those, new tickets
    skipped: int = 0  # already stored, or the sender is a machine answering a machine
    missed: int = 0   # couldn't be taken; left unread for the next run
    files: int = 0    # files kept out of those messages


class InboxPoller:
    def __init__(self, session: AsyncSession, *, limit: int = PER_RUN):
        self.session = session
        self.limit = limit
        self.accounts = EmailAccountRepository(session)
        self.filer = MessageFiler(session)
        self.box = SecretBox()

    # ---- the job ---------------------------------------------------------------------------------
    async def poll(self) -> str | None:
        rows = await self.accounts.active()
        if not rows:
            return None
        boxes, unreadable = self._prepare(rows)
        filed = opened = skipped = missed = files = broken = 0
        for account_id, address, why in unreadable:
            broken += 1
            await self._note(account_id, address, why)
            log.warning("inbox: %s: %s", address, why)
        for box in boxes:
            try:
                got = await self.poll_account(box)
            except Exception as exc:  # noqa: BLE001 - one bad mailbox mustn't stop the others
                broken += 1
                await self.session.rollback()  # whatever went wrong, the next mailbox starts clean
                await self._note(box.id, box.address, _why(exc))
                log.warning("inbox: %s: %s", box.address, exc)
                continue
            filed, opened = filed + got.filed, opened + got.opened
            skipped, missed = skipped + got.skipped, missed + got.missed
            files += got.files
        if not (filed or skipped or missed or broken):
            return None  # a quiet run says nothing: the job log only speaks when something happened
        return (f"mailboxes {len(rows)}, filed {filed} ({opened} new), files {files}, skipped {skipped}, "
                f"missed {missed}, failed {broken}")

    def _prepare(self, rows: list[EmailAccount]) -> tuple[list[Mailbox], list[tuple[int, str, str]]]:
        """What each row says, taken now and kept: a rollback later in the run expires loaded rows, and the
        rest of the run must not care. A mailbox whose stored password can't be read (the encryption key
        was rotated) is that mailbox's problem, not the run's — it must not stop the others being read."""
        boxes: list[Mailbox] = []
        unreadable: list[tuple[int, str, str]] = []
        for row in rows:
            try:
                boxes.append(Mailbox(id=row.id, address=row.address,
                                     config=config_for(row, password=account_password(row, self.box))))
            except Exception as exc:  # noqa: BLE001 - see above
                unreadable.append((row.id, row.address, _why(exc)))
        return boxes, unreadable

    async def poll_account(self, box: Mailbox) -> Polled:
        """Take what this mailbox has for us. Raises only if the mailbox itself can't be reached."""
        mailbox = mailbox_for(box.config)
        messages = await mailbox.unseen(self.limit)
        got = Polled()
        seen: list[str] = []
        for message in messages:
            try:
                async with self.session.begin_nested():
                    filed = await self.absorb(box, message)
                await self.session.commit()
            except Exception as exc:  # noqa: BLE001 - one bad message mustn't stop the rest
                got.missed += 1
                log.warning("inbox: %s couldn't take uid %s: %s", box.address, message.uid, exc)
                continue
            if filed.outcome == "opened":
                got.opened, got.filed = got.opened + 1, got.filed + 1
            elif filed.outcome == "joined":
                got.filed += 1
            else:
                got.skipped += 1
            got.files += filed.files
            seen.append(message.uid)
        if seen:
            await mailbox.mark_seen(seen)  # only what is safely stored: a crash here only means a re-take
        await self._note(box.id, box.address, f"{got.missed} message(s) couldn't be taken" if got.missed else None)
        return got

    # ---- one message, in the terms the filer speaks -------------------------------------------------
    async def absorb(self, box: Mailbox, message: InboundMessage) -> Filed:
        """File one message: "opened" (a new ticket), "joined" (an existing thread), "duplicate"
        (already stored under this `Message-ID`) or "automatic" (a machine wrote it)."""
        if message.auto_submitted and message.auto_submitted.lower() != "no":
            return Filed("automatic")
        return await self.filer.file(Incoming(
            external_id=self._external_id(box, message), channel="email", label="Email",
            body=message.text or "", subject=message.subject, from_email=message.from_email,
            from_name=message.from_name, to_email=box.address, when=message.date,
            thread=tuple(i for i in (message.in_reply_to, *reversed(message.references or ())) if i),
            attachments=tuple(message.attachments), source="email"))

    @staticmethod
    def _external_id(box: Mailbox, message: InboundMessage) -> str:
        """What makes this message one of a kind here. A sender that didn't say (no `Message-ID`) still
        gets one, from the mailbox and the message's uid, so nothing depends on a mail client behaving."""
        return message.message_id or f"no-message-id.{box.id}.{message.uid}@{box.address}"

    async def _note(self, account_id: int, address: str, error: str | None) -> None:
        """Write how the poll went on the mailbox, where Admin → Settings → Email accounts can show it.

        The row is read back rather than kept from the start: a rollback part-way through a run expires the
        rows the run began with, and a note is not worth a stale-object surprise."""
        try:
            account = await self.session.get(EmailAccount, account_id)
            if account is None:
                return  # the admin removed the mailbox while we were reading it
            account.last_polled_at = utcnow()
            account.last_error = (error or "")[:400] or None
            await self.session.commit()
        except Exception:  # noqa: BLE001 - the note is worth less than the run
            log.exception("inbox: couldn't record how %s went", address)
