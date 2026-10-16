"""Email outbox: every outgoing email is queued, sent with the SMTP account from Admin → Settings → Email,
paced to its limits, and retried by the background job."""

from app.integrations.email import set_email_sender_factory
from app.modules import CrmModule


def _install() -> None:
    from .service import OutboxEmailSender

    set_email_sender_factory(lambda session: OutboxEmailSender(session))


async def _deliver(session):
    from .service import MailService

    return await MailService(session).deliver_due()


module = CrmModule(name="mail", models="app.modules.mail.models", on_startup=(_install,), jobs=(("outbox", _deliver),))
