from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Protocol

log = logging.getLogger("wcw.email")


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
    reply_to: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class EmailSender(Protocol):
    async def send(self, mail: Mail) -> None: ...


class LogEmailSender:
    """Development/test sender: records and logs messages instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    async def send(self, mail: Mail) -> None:
        self.sent.append(mail)
        log.info("email (not sent) to=%s subject=%s\n%s", mail.to, mail.subject, mail.text)


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int = 465
    security: str = "ssl"  # ssl | starttls | none
    user: str | None = None
    password: str | None = None
    from_address: str = "no-reply@windycitywares.com"
    from_name: str = "Windy City Wares"
    timeout: int = 20


class SmtpEmailSender:
    def __init__(self, config: SmtpConfig):
        self.config = config

    def _build(self, mail: Mail) -> EmailMessage:
        c = self.config
        msg = EmailMessage()
        msg["From"] = formataddr((c.from_name, c.from_address))
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        msg["Message-ID"] = make_msgid(domain=c.from_address.split("@")[-1])
        if mail.reply_to:
            msg["Reply-To"] = mail.reply_to
        for key, value in mail.headers.items():
            msg[key] = value
        msg.set_content(mail.text)
        if mail.html:
            msg.add_alternative(mail.html, subtype="html")
        return msg

    def _send_sync(self, mail: Mail) -> None:
        c = self.config
        msg = self._build(mail)
        if c.security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(c.host, c.port, timeout=c.timeout, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(c.host, c.port, timeout=c.timeout)
        with server:
            if c.security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if c.user:
                server.login(c.user, c.password or "")
            server.send_message(msg)

    async def send(self, mail: Mail) -> None:
        await asyncio.to_thread(self._send_sync, mail)


_sender: EmailSender = LogEmailSender()
# Set by the mail module at start-up: builds a sender bound to the request's DB session (the outbox).
_factory: Callable[[Any], EmailSender] | None = None


def get_email_sender(session: Any = None) -> EmailSender:
    """FastAPI dependency (see users.deps.EmailSenderDep). Falls back to logging when no factory is set."""
    if _factory is not None and session is not None:
        return _factory(session)
    return _sender


def set_email_sender(sender: EmailSender) -> None:
    global _sender
    _sender = sender


def set_email_sender_factory(factory: Callable[[Any], EmailSender] | None) -> None:
    global _factory
    _factory = factory
