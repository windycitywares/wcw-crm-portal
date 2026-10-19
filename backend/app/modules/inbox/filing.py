"""Filing one message into the CRM, however it arrived (SPEC §3.9, the unified inbox).

The `inbox` job reads mailboxes (`poller.py`); a channel that isn't a mailbox — live chat, Etsy's
messages, and whatever comes next — hands the CRM one message over HTTP (`intake.py`). Both end up
here, so a message is filed by one set of rules whatever brought it in:

- the sender is a customer: found by the address they wrote from, or added (an existing name is never
  overwritten, exactly as when the shop or a mailbox brings somebody in);
- a message that answers something we have already seen joins *that* ticket — by the ids the sender
  carried, or by the "[T-000123]" every reply of ours puts in the subject — otherwise it opens one;
- the channel it came in on is written on a new ticket, and staff can re-file it;
- what came with it is kept against the ticket, each pointing at the message that carried it (see
  `app.modules.attachments`);
- a message we have already stored under the same external id is a duplicate, not a second ticket.

Nothing here commits: the caller does, so a message and its files are filed together or not at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.integrations.email import MailFile
from app.modules.activity.service import preview
from app.modules.attachments.service import MAX_BYTES as MAX_FILE_BYTES
from app.modules.attachments.service import AttachmentService
from app.modules.customers.service import CustomerService
from app.modules.lookups.service import LookupService
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import TicketService

MAX_BODY = 20_000   # what a ticket message holds (the same limit the API enforces)
MAX_SUBJECT = 200   # tickets.subject is String(200)
MAX_FILES = 10      # files kept from one message: a channel is open to anyone who finds its address
NUMBER = re.compile(r"\[([A-Za-z]+-\d+)\]")  # the "[T-000123]" our replies carry in the subject


@dataclass(frozen=True)
class Incoming:
    """One message from outside, in terms no channel owns: who wrote, what they said, which thread they
    mean, and what came with them.

    `label` is the word staff see when a message carries no subject of its own ("Email", "Live chat"),
    and `source` is how its files arrived, kept with each file.
    """

    external_id: str
    channel: str                      # a ticket_channel value: email, live_chat, etsy, ...
    body: str
    subject: str | None = None
    label: str = "Email"
    from_email: str | None = None
    from_phone: str | None = None    # a channel that has no address to give (a text, a live chat)
    from_name: str | None = None
    to_email: str | None = None      # the address it was sent to, when there is one (a mailbox listener)
    when: datetime | None = None
    thread: tuple[str, ...] = ()      # ids the sender says this answers (In-Reply-To, References)
    attachments: tuple[MailFile, ...] = ()
    source: str = "email"


@dataclass(frozen=True)
class Filed:
    """What became of one message: which way it was filed, which ticket, and how many files came."""

    outcome: str                      # opened | joined | duplicate
    ticket_id: int | None = None
    files: int = 0


class MessageFiler:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.customers = CustomerService(session)
        self.tickets = TicketService(session)
        self.attachments = AttachmentService(session)

    async def file(self, incoming: Incoming) -> Filed:
        """File one message. Says what happened: "opened" (a new ticket), "joined" (an existing thread)
        or "duplicate" (already stored under this external id) — and how many files came with it."""
        existing = await self.tickets.thread_for([incoming.external_id])
        if existing is not None:
            return Filed("duplicate", existing)  # a re-take after a crash; the id would refuse it anyway

        ticket_id = None
        node = [i for i in incoming.thread if i]
        if node:
            ticket_id = await self.tickets.thread_for(node)
        if ticket_id is None:
            ticket_id = await self._by_subject(incoming.subject)
        customer_id = None
        if incoming.from_email:  # no usable sender: still filed, so staff can link it by hand
            customer_id = await self.customers.find_or_create(
                email=incoming.from_email, full_name=incoming.from_name, how=incoming.label.lower())
        elif incoming.from_phone:
            # A number only ever *finds* somebody. Phones are shared and recycled, so a text from a number
            # nobody has on file stays unlinked (staff link it) rather than inventing a customer to hang it
            # on — and an address, when there is one, always outranks a number.
            customer_id = await self.customers.find_by_phone(incoming.from_phone)
        files, dropped = self._pick(incoming.attachments)
        body = self._body(incoming.body, dropped)
        if ticket_id is not None:
            message_id = await self.tickets.add_inbound(ticket_id, body=body, external_id=incoming.external_id,
                                                        from_email=incoming.from_email, to_email=incoming.to_email,
                                                        from_phone=incoming.from_phone, when=incoming.when)
            return Filed("joined", ticket_id,
                         await self._keep(ticket_id, files, incoming.source, message_id))
        ticket = await self.tickets.create(TicketCreate(
            subject=self._subject(incoming), description=body, ticket_type=await self._default_type(),
            channel=incoming.channel, customer_id=customer_id), actor=None, commit=False,
            opened_at=incoming.when)
        # The message that opened the ticket *is* the first thing said in it, not only its description:
        # that is what makes the ticket count as waiting on us, and what our reply answers so the
        # customer's next message finds its way back here. (A ticket staff typed in by hand has no
        # messages: nobody wrote in.)
        message_id = await self.tickets.add_inbound(ticket.id, body=body, external_id=incoming.external_id,
                                                    from_email=incoming.from_email, to_email=incoming.to_email,
                                                    from_phone=incoming.from_phone, when=incoming.when, opened=True)
        return Filed("opened", ticket.id, await self._keep(ticket.id, files, incoming.source, message_id))

    # ---- the files a message brought ---------------------------------------------------------------
    @staticmethod
    def _pick(attachments: tuple[MailFile, ...]) -> tuple[list[MailFile], int]:
        """Which of the message's files are worth keeping, and how many are left behind.

        A mailbox (or a channel) is open to anyone who finds the address, and the disk is finite: a
        message brings `MAX_FILES` sane-sized files and no more. What isn't kept is *counted*, and the
        message says so (`_body`) — a ticket that quietly lost a customer's photos is worse than one
        that admits it.
        """
        kept = [f for f in attachments if len(f.data) <= MAX_FILE_BYTES][:MAX_FILES]
        return kept, len(attachments) - len(kept)

    @staticmethod
    def _body(text: str, dropped: int) -> str:
        body = (text or "")[:MAX_BODY]
        if dropped:
            body += (f"\n\n({dropped} file{'s' if dropped != 1 else ''} came with this message "
                     "and couldn't be kept)")
        return body

    async def _keep(self, ticket_id: int, files: list[MailFile], source: str, message_id: int) -> int:
        """Keep what came with the message against its ticket, in the order it was sent, each pointing at
        the message that carried it. Returns how many landed; the caller commits, so a message and its
        files are filed together or not at all."""
        kept = 0
        for file in files:
            try:
                await self.attachments.keep("ticket", ticket_id, filename=file.filename,
                                            content_type=file.content_type, data=file.data, source=source,
                                            message_id=message_id, commit=False)
            except ValidationFailedError:  # empty, or bigger than `_pick` allowed for: counted, not fatal
                continue
            kept += 1
        return kept

    # ---- pieces ------------------------------------------------------------------------------------
    def _subject(self, incoming: Incoming) -> str:
        subject = " ".join((incoming.subject or "").split())
        if not subject:  # the shop's contact form does the same with a message that has no subject
            subject = f"{incoming.label}: {preview(incoming.body)}"
        return subject[:MAX_SUBJECT]

    async def _by_subject(self, subject: str | None) -> int | None:
        """A sender whose client lost the headers still says which ticket they mean: every reply of ours
        carries "[T-000123]" in the subject."""
        match = NUMBER.search(subject or "")
        return await self.tickets.ticket_by_number(match.group(1).upper()) if match else None

    async def _default_type(self) -> str | None:
        """File a new ticket as "Other", as the shop's contact form does — staff re-file it if they care."""
        try:
            return await LookupService(self.session).require("ticket_type", "other")
        except (NotFoundError, ValidationFailedError):
            return None  # someone removed the type: file the ticket untyped rather than fail
