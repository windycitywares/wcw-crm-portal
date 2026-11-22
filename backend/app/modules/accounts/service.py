"""Accounts: business rules. Own-vs-any follows customers (an account is a customer-side record):
anyone who may edit their own customers may add an account and edit the ones they own; managers edit any.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, register_entity
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.customfields.service import CustomFieldService
from app.modules.lookups.service import LookupService
from app.shared.snapshot import snapshot

from .models import Account
from .repository import AccountRepository
from .schemas import AccountIn, AccountOption, AccountOut, AccountPage, AccountUpdate

ENTITY = "account"
KIND = "account_type"
TRACKED = ("name", "account_type", "status", "industry", "website", "email", "phone", "address", "notes",
           "owner_id", "custom_fields")


async def _exists(session, account_id: int) -> bool:
    return await AccountRepository(session).get(account_id) is not None


async def _can_edit(session, user, account_id: int) -> bool:
    if has_permission(user.role, Permission.CUSTOMERS_EDIT_ANY):
        return True
    account = await AccountRepository(session).get(account_id)
    return account is not None and account.owner_id == user.id


async def _labels(session, ids: list[int]) -> dict[int, str]:
    return await AccountRepository(session).names(ids)


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Account",
        view=(Permission.CUSTOMERS_VIEW,), edit=(Permission.CUSTOMERS_EDIT_OWN, Permission.CUSTOMERS_EDIT_ANY),
        exists=_exists, can_edit=_can_edit, labels=_labels,
    ))


class AccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AccountRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)
        self.fields = CustomFieldService(session)

    # ---- reads ----------------------------------------------------------
    async def _get(self, account_id: int) -> Account:
        account = await self.repo.get(account_id)
        if account is None:
            raise NotFoundError("Account not found")
        return account

    async def _out(self, accounts: list[Account]) -> list[AccountOut]:
        from app.modules.contacts.service import ContactService  # contacts validate accounts: import late

        counts = await ContactService(self.session).counts_by_account([a.id for a in accounts])
        return [AccountOut.model_validate(a).model_copy(update={"contacts_count": counts.get(a.id, 0)})
                for a in accounts]

    async def list(self, params: PageParams, *, q: str | None = None, account_type: str | None = None,
                   status: str | None = None, owner_id: int | None = None, sort: str = "name") -> AccountPage:
        rows, total = await self.repo.paginate(
            self.repo.search(q=q, account_type=account_type, status=status, owner_id=owner_id, sort=sort), params)
        return AccountPage(items=await self._out(list(rows)), total=total, page=params.page,
                           page_size=params.page_size)

    async def options(self, *, q: str | None = None, account_type: str | None = None,
                      limit: int = 50) -> list[AccountOption]:
        stmt = self.repo.search(q=q, account_type=account_type, status="active").limit(limit)
        return [AccountOption(id=a.id, name=a.name, account_type=a.account_type) for a in await self.repo.list(stmt)]

    async def get(self, account_id: int) -> AccountOut:
        return (await self._out([await self._get(account_id)]))[0]

    async def require(self, account_id: int | None) -> int | None:
        """For other modules: the id of a live account, or a 422."""
        if account_id is None:
            return None
        if await self.repo.get(account_id) is None:
            raise ValidationFailedError(f"Account #{account_id} doesn't exist")
        return account_id

    async def names(self, ids: list[int]) -> dict[int, str]:
        return await self.repo.names(ids)

    # ---- writes ---------------------------------------------------------
    async def _validate(self, values: dict[str, Any], current: Account | None) -> dict[str, Any]:
        if values.get("account_type") is not None:
            values["account_type"] = await self.lookups.require(
                KIND, values["account_type"], allow_inactive_key=current.account_type if current else None)
        if "address" in values and values["address"] is not None:
            values["address"] = {k: v for k, v in values["address"].items() if v} or None
        if values.get("website") is not None:
            values["website"] = str(values["website"])
        if values.get("email") is not None:
            values["email"] = str(values["email"]).strip().lower()
        if "custom_fields" in values:
            values["custom_fields"] = await self.fields.validate(
                ENTITY, values["custom_fields"] or {}, existing=current.custom_fields if current else None)
        return values

    async def create(self, data: AccountIn, actor) -> AccountOut:
        values = await self._validate(data.model_dump(exclude_unset=True), None)
        values.setdefault("status", "active")
        if values.get("owner_id") is None:
            values["owner_id"] = actor.id
        elif values["owner_id"] != actor.id and not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("You can only add accounts you own")
        account = Account(**values, created_by=actor.id, updated_by=actor.id)
        await self.repo.add(account)
        await self.audit.record("account.create", actor=actor, entity_type=ENTITY, entity_id=account.id,
                                changes=diff({}, snapshot(account, TRACKED)))
        await self.timeline.record(ENTITY, account.id, "account.created", "Account added", actor=actor)
        await self.session.commit()
        return await self.get(account.id)

    async def ensure(self, name: str, account_type: str, actor) -> Account:
        """For other modules (suppliers, lead conversion): the live account of this name and type, made if
        missing. Flushes, never commits — the caller owns the transaction."""
        existing = await self.repo.by_name(name, account_type=account_type)
        if existing is not None:
            return existing
        await self.lookups.require(KIND, account_type)
        account = Account(name=" ".join(name.split()), account_type=account_type, status="active",
                          owner_id=getattr(actor, "id", None), created_by=getattr(actor, "id", None),
                          updated_by=getattr(actor, "id", None))
        await self.repo.add(account)
        await self.audit.record("account.create", actor=actor, entity_type=ENTITY, entity_id=account.id,
                                changes=diff({}, snapshot(account, TRACKED)))
        await self.timeline.record(ENTITY, account.id, "account.created", "Account added", actor=actor)
        return account

    async def update(self, account_id: int, data: AccountUpdate, actor) -> AccountOut:
        account = await self._get(account_id)
        if not await _can_edit(self.session, actor, account_id):
            raise PermissionDeniedError("You can only change accounts you own")
        values = data.model_dump(exclude_unset=True)
        for field in ("name", "account_type", "status"):
            if values.get(field) is None:
                values.pop(field, None)
        if "owner_id" in values and values["owner_id"] != account.owner_id \
                and not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("Only managers can hand an account to someone else")
        before = snapshot(account, TRACKED)
        values = await self._validate(values, account)
        self.repo.apply(account, values)
        account.updated_by = actor.id
        changes = diff(before, snapshot(account, TRACKED))
        if changes:
            await self.audit.record("account.update", actor=actor, entity_type=ENTITY, entity_id=account.id,
                                    changes=changes)
            await self.timeline.record(ENTITY, account.id, "account.updated", "Account details changed",
                                       actor=actor, data={"fields": list(changes)})
        await self.session.commit()
        await self.session.refresh(account)
        return await self.get(account.id)

    async def delete(self, account_id: int, actor) -> None:
        account = await self._get(account_id)
        if not has_permission(actor.role, Permission.CUSTOMERS_EDIT_ANY):
            raise PermissionDeniedError("Only managers can archive accounts")
        await self.repo.soft_delete(account)
        await self.audit.record("account.delete", actor=actor, entity_type=ENTITY, entity_id=account.id,
                                changes={"name": account.name})
        await self.timeline.record(ENTITY, account.id, "account.deleted", "Account archived", actor=actor)
        await self.session.commit()
