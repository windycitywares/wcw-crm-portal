"""Email arriving on the mailboxes the CRM reads (SPEC §3.9, the unified inbox).

The `inbox` job, once a minute: for every mailbox that is switched on, take the mail it hasn't read yet
(oldest first) and file each message — opening a ticket for somebody who writes in, joining the thread for
somebody answering us. What was taken is then marked read in the mailbox, so the next run doesn't see it
again; the `Message-ID` is stored either way, so even a double take cannot double a message.

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
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.security import SecretBox
from app.integrations.email import InboundMessage, MailboxConfig, MailboxError, mailbox_for
from app.modules.customers.service import CustomerService
from app.modules.lookups.service import LookupService
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import TicketService

from .models import EmailAccount
from .repository import EmailAccountRepository
from .service import account_password, config_for

log = logging.getLogger("wcw.crm.inbox")

PER_RUN = 50        # messages taken from one mailbox in a run; the rest wait for the next minute
MAX_BODY = 20_000   # what a ticket message holds (the same limit the API enforces)
MAX_SUBJECT = 200   # tickets.subject is String(200)
NUMBER = re.compile(r"\[([A-Za-z]+-\d+)\]")  # the "[T-000123]" our replies carry in the subject


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


class InboxPoller:
    def __init__(self, session: AsyncSession, *, limit: int = PER_RUN):
        self.session = session
        self.limit = limit
        self.accounts = EmailAccountRepository(session)
        self.customers = CustomerService(session)
        self.tickets = TicketService(session)
        self.box = SecretBox()

    # ---- the job ---------------------------------------------------------------------------------
    async def poll(self) -> str | None:
        rows = await self.accounts.active()
        if not rows:
            return None
        boxes, unreadable = self._prepare(rows)
        filed = opened = skipped = missed = broken = 0
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
        if not (filed or skipped or missed or broken):
            return None  # a quiet run says nothing: the job log only speaks when something happened
        return (f"mailboxes {len(rows)}, filed {filed} ({opened} new), skipped {skipped}, "
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
                    outcome = await self.absorb(box, message)
                await self.session.commit()
            except Exception as exc:  # noqa: BLE001 - one bad message mustn't stop the rest
                got.missed += 1
                log.warning("inbox: %s couldn't take uid %s: %s", box.address, message.uid, exc)
                continue
            if outcome == "opened":
                got.opened, got.filed = got.opened + 1, got.filed + 1
            elif outcome == "joined":
                got.filed += 1
            else:
                got.skipped += 1
            seen.append(message.uid)
        if seen:
            await mailbox.mark_seen(seen)  # only what is safely stored: a crash here only means a re-take
        await self._note(box.id, box.address, f"{got.missed} message(s) couldn't be taken" if got.missed else None)
        return got

    # ---- filing one message ----------------------------------------------------------------------
    async def absorb(self, box: Mailbox, message: InboundMessage) -> str:
        """File one message. Says what happened: "opened" (a new ticket), "joined" (an existing thread),
        "duplicate" (already stored under this `Message-ID`) or "automatic" (a machine wrote it)."""
        external_id = self._external_id(box, message)
        if message.auto_submitted and message.auto_submitted.lower() != "no":
            return "automatic"
        if await self.tickets.thread_for([external_id]):
            return "duplicate"  # a re-take after a crash; the unique id would refuse it anyway

        node = [i for i in (message.in_reply_to, *reversed(message.references or ())) if i]
        ticket_id = await self.tickets.thread_for(node) if node else None
        if ticket_id is None:
            ticket_id = await self._by_subject(message)
        customer_id = None
        if message.from_email:  # a message with no usable From still gets filed: staff can link it later
            customer_id = await self.customers.find_or_create(email=message.from_email, full_name=message.from_name,
                                                              how="email")
        body = (message.text or "")[:MAX_BODY]
        if ticket_id is not None:
            await self.tickets.add_inbound(ticket_id, body=body, external_id=external_id,
                                           from_email=message.from_email, to_email=box.address,
                                           when=message.date)
            return "joined"
        await self.tickets.create(TicketCreate(
            subject=self._subject(message), description=body, ticket_type=await self._default_type(),
            channel="email", customer_id=customer_id), actor=None, commit=False, opened_at=message.date)
        return "opened"

    # ---- pieces ----------------------------------------------------------------------------------
    @staticmethod
    def _external_id(box: Mailbox, message: InboundMessage) -> str:
        """What makes this message one of a kind here. A sender that didn't say (no `Message-ID`) still
        gets one, from the mailbox and the message's uid, so nothing depends on a mail client behaving."""
        return message.message_id or f"no-message-id.{box.id}.{message.uid}@{box.address}"

    @staticmethod
    def _subject(message: InboundMessage) -> str:
        subject = " ".join((message.subject or "").split())
        if not subject:  # the shop's contact form does the same with a message that has no subject
            subject = "Email: " + " ".join((message.text or "").split())[:MAX_SUBJECT - 7]
        return subject[:MAX_SUBJECT]

    async def _by_subject(self, message: InboundMessage) -> int | None:
        """A customer whose mail client lost the headers still says which ticket they mean: every reply of
        ours carries "[T-000123]" in the subject."""
        match = NUMBER.search(message.subject or "")
        return await self.tickets.ticket_by_number(match.group(1).upper()) if match else None

    async def _default_type(self) -> str | None:
        """File a new ticket as "Other", as the shop's contact form does — staff re-file it if they care."""
        try:
            return await LookupService(self.session).require("ticket_type", "other")
        except (NotFoundError, ValidationFailedError):
            return None  # someone removed the type: file the ticket untyped rather than fail

    async def _note(self, account_id: int, address: str, error: str | None) -> None:
        """Write how the poll went on the mailbox, where Admin → Settings → Email accounts can show it.

        The row is read back rather than kept from the start: a rollback part-way through a run expires the
        rows the run began with, and a note is not worth a stale-object surprise."""
        try:
            account = await self.session.get(EmailAccount, account_id)
            if account is None:
                return  # the admin removed the mailbox while we were reading it
            account.last_polled_at = _now()
            account.last_error = (error or "")[:400] or None
            await self.session.commit()
        except Exception:  # noqa: BLE001 - the note is worth less than the run
            log.exception("inbox: couldn't record how %s went", address)
