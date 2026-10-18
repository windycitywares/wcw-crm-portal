from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .schemas import EmailAccountIn, EmailAccountOut, EmailAccountUpdate, MailboxCheck
from .service import InboxService

# A mailbox is configuration (like the SMTP account next door), so the whole surface — reading it too —
# needs `inbox:manage`: support works the queue, not the credentials.
router = APIRouter(prefix="/inbox/accounts", tags=["inbox"],
                   dependencies=[Depends(require(Permission.INBOX_MANAGE))])
Admin = Annotated[User, Depends(require(Permission.INBOX_MANAGE))]


@router.get("", response_model=list[EmailAccountOut])
async def list_accounts(session: SessionDep) -> list[EmailAccountOut]:
    """The mailboxes the CRM reads. A handful, so no paging: the screen shows them all."""
    return await InboxService(session).list()


@router.post("", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(session: SessionDep, actor: Admin, data: EmailAccountIn) -> EmailAccountOut:
    return await InboxService(session).create(data, actor)


@router.get("/{account_id}", response_model=EmailAccountOut)
async def get_account(session: SessionDep, account_id: int) -> EmailAccountOut:
    return await InboxService(session).get(account_id)


@router.patch("/{account_id}", response_model=EmailAccountOut)
async def update_account(session: SessionDep, actor: Admin, account_id: int,
                         data: EmailAccountUpdate) -> EmailAccountOut:
    return await InboxService(session).update(account_id, data, actor)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(session: SessionDep, actor: Admin, account_id: int) -> None:
    await InboxService(session).delete(account_id, actor)


@router.post("/{account_id}/test", response_model=MailboxCheck)
async def test_account(session: SessionDep, account_id: int) -> MailboxCheck:
    """Open the saved mailbox right now and report what the server says (SPEC §3.9)."""
    return await InboxService(session).check(account_id)
