"""Messages arriving on a channel that isn't a mailbox (SPEC §3.9, the unified inbox).

A connector posts one message at a time, signed: the shop's chat widget, an Etsy poller, an SMS gateway —
anything that can make an HTTP request. The contract is docs/INBOX_CHANNELS.md. What happens to a message
once it is let in is `filing.py`, the same rules mail goes through, so a chat message and a letter open a
ticket in exactly the same way.

A message that can't be let in is refused with a status the connector can read (`IntakeRejected`); one the
CRM fails to file is a 500, and posting it again is the connector's job — the message id is stored, so a
re-post is a duplicate rather than a second ticket.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.integrations import signing
from app.integrations.email import MailFile
from app.integrations.email.inbound import NO_TEXT
from app.modules.lookups.service import LookupService
from app.modules.settings.service import SettingsService

from .filing import Incoming, MessageFiler
from .schemas import MAX_REQUEST, InboundMessageIn, IntakeOut
from .settings import InboxSettings

log = logging.getLogger("wcw.crm.inbox")


class IntakeRejected(Exception):
    """Refused before anything was filed: `status_code` and `detail` go back to the connector."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


class InboxIntakeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.filer = MessageFiler(session)

    async def settings(self) -> InboxSettings:
        return await SettingsService(self.session).get_model("inbox", factory=InboxSettings)

    async def accept(self, body: bytes, timestamp: str | None, signature: str | None) -> IntakeOut:
        """Let one message in and file it. Raises `IntakeRejected` when it can't be taken."""
        if len(body) > MAX_REQUEST:
            raise IntakeRejected(413, "Message too large")
        cfg = await self.settings()
        if not cfg.enabled or not cfg.ingest_secret:
            raise IntakeRejected(503, "Channels are switched off in the CRM")
        problem = signing.verify(cfg.ingest_secret, timestamp, signature, body)
        if problem:
            log.warning("inbox channel refused: %s", problem)
            raise IntakeRejected(401, "Invalid signature")
        try:
            message = InboundMessageIn.model_validate(json.loads(body))
        except (ValueError, ValidationError):
            raise IntakeRejected(400, "Not a valid message") from None
        channel, label = await self._channel(message.channel)
        files = self._files(message)
        try:
            async with self.session.begin_nested():
                filed = await self.filer.file(Incoming(
                    external_id=message.id, channel=channel, label=label,
                    body=message.body or (NO_TEXT if files else ""), subject=message.subject,
                    from_email=str(message.sender.email) if message.sender.email else None,
                    from_phone=message.sender.phone, from_name=message.sender.name, when=message.at,
                    thread=(message.thread,) if message.thread else (), attachments=files, source=channel))
            await self.session.commit()
        except ValidationFailedError as exc:  # e.g. a file the CRM won't keep
            raise IntakeRejected(400, str(exc)) from None
        return IntakeOut(status="filed" if filed.outcome in ("opened", "joined") else "duplicate",
                         ticket_id=filed.ticket_id, files=filed.files)

    # ---- pieces ------------------------------------------------------------------------------------
    async def _channel(self, channel: str) -> tuple[str, str]:
        """The channel has to be one staff can pick on a ticket (Admin → Settings → Types), so a typo is
        refused here rather than filed as a ticket nobody can find again. It answers with the word staff
        see for it too, so a chat that carries no subject reads "Live chat: …" and not "live_chat: …"."""
        looks = LookupService(self.session)
        try:
            key = await looks.require("ticket_channel", channel) or channel
        except (NotFoundError, ValidationFailedError) as exc:
            raise IntakeRejected(400, f"channel: {exc}") from None
        values = await looks.values("ticket_channel", include_inactive=False)
        return key, next((v.label for v in values if v.key == key), key.replace("_", " ").capitalize())

    @staticmethod
    def _files(message: InboundMessageIn) -> tuple[MailFile, ...]:
        """The files that came with the message. One that isn't base64 is the connector's bug, and a photo
        that quietly went missing is worse than a message refused, so the whole message is refused."""
        files = []
        for file in message.files:
            try:
                data = base64.b64decode("".join(file.data.split()), validate=True)
            except (binascii.Error, ValueError):
                raise IntakeRejected(400, f"files: '{file.filename}' is not base64") from None
            files.append(MailFile(filename=file.filename,
                                  content_type=file.content_type or "application/octet-stream", data=data))
        return tuple(files)
