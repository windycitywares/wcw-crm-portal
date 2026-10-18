"""Outgoing email behind a small interface (dependency inversion).

Services depend on `EmailSender`, never on smtplib. In development and tests the `LogEmailSender`
prints the message; the SMTP account configured in Admin → Settings → Email (M1 settings module)
provides the outbox sender through `set_email_sender_factory(...)` (queue + SMTP from Admin → Settings).

Coming *in* is the other half: `InboundMailbox` (this package's `inbound` module) is what the inbox
reads with — `check()`, `unseen()` and `mark_seen()` — and `mailbox_for(...)` builds one: real IMAP,
or a stand-in in tests.
"""

from .inbound import (
    InboundMailbox, InboundMessage, ImapInboundMailbox, MailboxConfig, MailboxError, MailboxStatus,
    mailbox_for, parse_message, set_mailbox_factory,
)
from .sender import (
    EmailSender, LogEmailSender, Mail, SmtpConfig, SmtpEmailSender, get_email_sender, set_email_sender,
    set_email_sender_factory,
)

__all__ = [
    "EmailSender", "InboundMailbox", "InboundMessage", "ImapInboundMailbox", "LogEmailSender", "Mail",
    "MailboxConfig", "MailboxError", "MailboxStatus", "SmtpConfig", "SmtpEmailSender", "get_email_sender",
    "mailbox_for", "parse_message", "set_email_sender", "set_email_sender_factory", "set_mailbox_factory",
]
