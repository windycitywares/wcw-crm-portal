"""Outgoing email behind a small interface (dependency inversion).

Services depend on `EmailSender`, never on smtplib. In development and tests the `LogEmailSender`
prints the message; the SMTP account configured in Admin → Settings → Email (M1 settings module)
provides the outbox sender through `set_email_sender_factory(...)` (queue + SMTP from Admin → Settings).
"""

from .sender import (
    EmailSender, LogEmailSender, Mail, SmtpConfig, SmtpEmailSender, get_email_sender, set_email_sender,
    set_email_sender_factory,
)

__all__ = [
    "EmailSender", "LogEmailSender", "Mail", "SmtpConfig", "SmtpEmailSender", "get_email_sender", "set_email_sender",
    "set_email_sender_factory",
]
