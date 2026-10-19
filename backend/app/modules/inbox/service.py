"""The mailboxes the CRM reads, and the mail that arrives on them (SPEC §3.9, the unified inbox).

Setting a mailbox up (and proving the CRM can reach it) lives here; reading its mail into tickets is
`poller.py`, which is what the once-a-minute `inbox` job runs. `check()` exists on its own because an
admin who has just typed a host, a folder and a password needs to know it works before anything
depends on it.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.security import SecretBox
from app.integrations.email import MailboxConfig, MailboxError, mailbox_for
from app.modules.audit.service import AuditService, diff
from app.shared.snapshot import snapshot

from .models import EmailAccount
from .repository import EmailAccountRepository
from .schemas import EmailAccountIn, EmailAccountOut, EmailAccountUpdate, MailboxCheck

ENTITY = "email_account"
ACCOUNT_FIELDS = ("address", "display_name", "imap_host", "imap_port", "imap_security", "imap_user", "folder",
                  "is_active")
# The two a mailbox may genuinely not have. Everything else: a null in a patch means "not changing it",
# which is also what stops a null reaching a NOT NULL column.
NULLABLE = ("display_name", "imap_user")



def config_for(account: EmailAccount, *, password: str) -> MailboxConfig:
    """How to reach the mailbox. Without a username of its own, a mailbox is read as its own address."""
    return MailboxConfig(
        host=account.imap_host, port=account.imap_port, security=account.imap_security,
        username=account.imap_user or account.address, password=password, folder=account.folder,
    )


def account_password(account: EmailAccount, box: SecretBox) -> str:
    """The mailbox's password, decrypted. Server-side use only — the API never returns it."""
    return box.decrypt(account.imap_password_enc)


class InboxService:
    def __init__(self, session: AsyncSession, box: SecretBox | None = None):
        self.session = session
        self.repo = EmailAccountRepository(session)
        self.audit = AuditService(session)
        self._box = box

    @property
    def box(self) -> SecretBox:
        if self._box is None:
            self._box = SecretBox()
        return self._box

    async def _get(self, account_id: int) -> EmailAccount:
        account = await self.repo.get(account_id)
        if account is None:
            raise NotFoundError("Mailbox not found")
        return account

    def _password(self, account: EmailAccount) -> str:
        return account_password(account, self.box)

    async def _check_address(self, address: str, *, exclude_id: int | None = None) -> None:
        other = await self.repo.by_address(address)
        if other is not None and other.id != exclude_id:
            raise ValidationFailedError(f"{other.address} is already set up as a mailbox")

    # ---- reads -----------------------------------------------------------------------------------
    async def list(self) -> list[EmailAccountOut]:
        return [EmailAccountOut.model_validate(account) for account in await self.repo.list(self.repo.ordered())]

    async def get(self, account_id: int) -> EmailAccountOut:
        return EmailAccountOut.model_validate(await self._get(account_id))

    # ---- writes ----------------------------------------------------------------------------------
    async def create(self, data: EmailAccountIn, actor) -> EmailAccountOut:
        values = data.model_dump(exclude_unset=True)
        values["address"] = str(values["address"]).strip()
        await self._check_address(values["address"])
        secret = self.box.encrypt(values.pop("imap_password"))
        account = EmailAccount(**values, imap_password_enc=secret, created_by=actor.id, updated_by=actor.id)
        await self.repo.add(account)
        await self.audit.record("inbox.account_create", actor=actor, entity_type=ENTITY, entity_id=account.id,
                                changes=diff({}, snapshot(account, ACCOUNT_FIELDS)))
        await self.session.commit()
        return await self.get(account.id)

    async def update(self, account_id: int, data: EmailAccountUpdate, actor) -> EmailAccountOut:
        account = await self._get(account_id)
        values = {key: value for key, value in data.model_dump(exclude_unset=True).items()
                  if value is not None or key in NULLABLE}
        if values.get("address") is not None:
            values["address"] = str(values["address"]).strip()
            await self._check_address(values["address"], exclude_id=account.id)
        before = snapshot(account, ACCOUNT_FIELDS)
        secret_changed = values.get("imap_password") not in (None, "")
        if secret_changed:
            account.imap_password_enc = self.box.encrypt(values.pop("imap_password"))
        else:
            values.pop("imap_password", None)  # blank = keep the stored password
        self.repo.apply(account, values)
        account.updated_by = actor.id
        changes = diff(before, snapshot(account, ACCOUNT_FIELDS))
        if secret_changed:
            changes["imap_password"] = ["••••", "••••"]
        if changes:
            await self.audit.record("inbox.account_update", actor=actor, entity_type=ENTITY,
                                    entity_id=account.id, changes=changes)
        await self.session.commit()
        return await self.get(account.id)

    async def delete(self, account_id: int, actor) -> None:
        """Deleted, not archived: a mailbox nobody reads any more shouldn't keep a password in the database.
        The tickets its mail opened are conversations, and they stay."""
        account = await self._get(account_id)
        address = account.address
        await self.repo.hard_delete(account)
        await self.audit.record("inbox.account_delete", actor=actor, entity_type=ENTITY, entity_id=account_id,
                                changes={"address": address})
        await self.session.commit()

    # ---- "can we reach it?" ----------------------------------------------------------------------
    async def check(self, account_id: int) -> MailboxCheck:
        """Open the mailbox now and report what it says. Nothing is written: a test is a test."""
        account = await self._get(account_id)
        try:
            status = await mailbox_for(config_for(account, password=self._password(account))).check()
        except MailboxError as exc:
            return MailboxCheck(ok=False, detail=str(exc)[:500])
        except Exception as exc:  # noqa: BLE001 - show the mailbox's own error to the admin
            return MailboxCheck(ok=False, detail=f"{type(exc).__name__}: {exc}"[:500])
        return MailboxCheck(
            ok=True, detail=f"{status.folder}: {status.messages:,} messages, {status.unseen:,} unread.",
            folder=status.folder, messages=status.messages, unseen=status.unseen,
        )
