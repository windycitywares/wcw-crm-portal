"""Outgoing email behind a small interface (dependency inversion).

Services depend on `EmailSender`, never on smtplib. In development and tests the `LogEmailSender`
prints the message; the SMTP account configured in Admin → Settings → Email (M1 settings module)
will provide an `SmtpEmailSender`. Swap the sender in one place: `set_email_sender(...)`.
"""

from .sender import EmailSender, LogEmailSender, Mail, SmtpConfig, SmtpEmailSender, get_email_sender, set_email_sender

__all__ = [
    "EmailSender", "LogEmailSender", "Mail", "SmtpConfig", "SmtpEmailSender", "get_email_sender", "set_email_sender",
]
