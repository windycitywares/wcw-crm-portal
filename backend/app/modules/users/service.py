"""Sign-in, passwords and staff accounts. Routers stay thin; every rule lives here."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError, ConflictError, NotFoundError, TooManyRequestsError, ValidationFailedError,
)
from app.core.pagination import PageParams
from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Role, permissions_for
from app.core.security import create_access_token, hash_password, verify_password
from app.integrations.email import EmailSender, Mail
from app.modules.audit.service import AuditService, diff
from app.shared.time import utcnow

from .models import PasswordResetToken, User
from .repository import ResetTokenRepository, UserRepository
from .schemas import (
    DirectoryEntry, MeOut, PasswordChange, ProfileUpdate, RoleOut, TokenOut, UserCreate, UserOut, UserPage, UserUpdate,
)

RESET_TOKEN_MINUTES = 60
# Compared against when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def me_out(user: User) -> MeOut:
    return MeOut(
        **UserOut.model_validate(user).model_dump(),
        permissions=sorted(p.value for p in permissions_for(user.role)),
    )


def roles() -> list[RoleOut]:
    return [
        RoleOut(key=role, label=ROLE_LABELS[role], permissions=sorted(p.value for p in ROLE_PERMISSIONS[role]))
        for role in Role
    ]


def _snapshot(user: User) -> dict:
    return {"full_name": user.full_name, "role": user.role, "is_active": user.is_active,
            "title": user.title, "phone": user.phone, "timezone": user.timezone, "email": user.email}


class AuthService:
    def __init__(self, session: AsyncSession, email_sender: EmailSender | None = None):
        self.session = session
        self.users = UserRepository(session)
        self.tokens = ResetTokenRepository(session)
        self.audit = AuditService(session)
        self.email_sender = email_sender

    def _issue(self, user: User) -> TokenOut:
        return TokenOut(access_token=create_access_token(user.id, user.role), user=me_out(user))

    async def login(self, email: str, password: str, ip: str) -> TokenOut:
        email = email.strip().lower()
        if rate_limit.failed_logins_by_email.is_blocked(email) or rate_limit.failed_logins_by_ip.is_blocked(ip):
            raise TooManyRequestsError("Too many failed sign-ins. Try again in 15 minutes.")
        user = await self.users.by_email(email)
        ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
        if not user or not ok or not user.is_active:
            rate_limit.failed_logins_by_email.hit(email)
            rate_limit.failed_logins_by_ip.hit(ip)
            await self.audit.record("auth.login_failed", actor_email=email, ip=ip,
                                    entity_type="user", entity_id=user.id if user else None)
            await self.session.commit()
            raise AuthenticationError("Wrong email or password")
        rate_limit.failed_logins_by_email.reset(email)
        user.last_login_at = utcnow()
        await self.audit.record("auth.login", actor=user, entity_type="user", entity_id=user.id, ip=ip)
        await self.session.commit()
        return self._issue(user)

    async def update_profile(self, user: User, data: ProfileUpdate) -> MeOut:
        before = _snapshot(user)
        self.users.apply(user, data.model_dump(exclude_unset=True, exclude_none=True))
        await self.audit.record("user.update_profile", actor=user, entity_type="user", entity_id=user.id,
                                changes=diff(before, _snapshot(user)))
        await self.session.commit()
        return me_out(user)

    async def change_password(self, user: User, data: PasswordChange, ip: str) -> TokenOut:
        if not verify_password(data.current_password, user.password_hash):
            raise ValidationFailedError("Current password is wrong")
        self._set_password(user, data.new_password)
        await self.tokens.invalidate_for_user(user.id, utcnow())
        await self.audit.record("auth.password_changed", actor=user, entity_type="user", entity_id=user.id, ip=ip)
        await self.session.commit()
        return self._issue(user)  # old tokens stop working; this one is fresh

    async def forgot_password(self, email: str, ip: str) -> None:
        """Always succeeds from the caller's point of view, so it can't be used to find accounts."""
        email = email.strip().lower()
        if rate_limit.reset_requests_by_ip.is_blocked(ip) or rate_limit.reset_requests_by_email.is_blocked(email):
            raise TooManyRequestsError("Too many requests. Try again later.")
        rate_limit.reset_requests_by_ip.hit(ip)
        rate_limit.reset_requests_by_email.hit(email)
        user = await self.users.by_email(email)
        if not user or not user.is_active:
            return
        now = utcnow()
        await self.tokens.invalidate_for_user(user.id, now)
        token = secrets.token_urlsafe(32)
        await self.tokens.add(PasswordResetToken(
            user_id=user.id, token_hash=_token_hash(token), expires_at=now + timedelta(minutes=RESET_TOKEN_MINUTES)
        ))
        await self.audit.record("auth.reset_requested", actor=user, entity_type="user", entity_id=user.id, ip=ip)
        await self.session.commit()
        if self.email_sender:
            link = f"{get_settings().site_url.rstrip('/')}/reset-password?token={token}"
            await self.email_sender.send(Mail(
                to=user.email,
                subject="Reset your Windy City Wares CRM password",
                text=(f"Hi {user.full_name},\n\nSomeone (hopefully you) asked to reset your CRM password.\n"
                      f"Open this link within {RESET_TOKEN_MINUTES} minutes to choose a new one:\n\n{link}\n\n"
                      "If you didn't ask for this, ignore this email — your password stays the same."),
            ))

    async def reset_password(self, token: str, new_password: str, ip: str) -> TokenOut:
        if rate_limit.reset_attempts_by_ip.is_blocked(ip):
            raise TooManyRequestsError("Too many attempts. Try again later.")
        rate_limit.reset_attempts_by_ip.hit(ip)
        row = await self.tokens.by_hash(_token_hash(token))
        now = utcnow()
        if not row or row.used_at or row.expires_at <= now:
            raise ValidationFailedError("This reset link is invalid or has expired. Ask for a new one.")
        user = await self.users.get(row.user_id)
        if not user or not user.is_active:
            raise ValidationFailedError("This reset link is invalid or has expired. Ask for a new one.")
        row.used_at = now
        self._set_password(user, new_password)
        await self.audit.record("auth.password_reset", actor=user, entity_type="user", entity_id=user.id, ip=ip)
        await self.session.commit()
        return self._issue(user)

    @staticmethod
    def _set_password(user: User, password: str) -> None:
        user.password_hash = hash_password(password)
        # Tokens carry whole seconds; round down so a token issued right now is still valid.
        user.password_changed_at = utcnow().replace(microsecond=0)


class UserService:
    """Staff account administration (Admin → Users)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    async def _get(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    async def list(self, params: PageParams, *, q: str | None, role: Role | None, active: bool | None) -> UserPage:
        rows, total = await self.users.paginate(self.users.search(q=q, role=role, active=active), params)
        return UserPage(items=[UserOut.model_validate(u) for u in rows], total=total,
                        page=params.page, page_size=params.page_size)

    async def directory(self) -> list[DirectoryEntry]:
        return [DirectoryEntry.model_validate(u) for u in await self.users.directory()]

    async def contacts(self) -> list[tuple[int, str, str]]:
        """(id, full name, email) of every user — server-side only (e.g. owner columns in imports/exports)."""
        return [(u.id, u.full_name, u.email) for u in await self.users.directory()]

    async def get(self, user_id: int) -> UserOut:
        return UserOut.model_validate(await self._get(user_id))

    async def create(self, data: UserCreate, actor: User) -> UserOut:
        email = data.email.strip().lower()
        if await self.users.by_email(email):
            raise ConflictError("A user with this email already exists")
        user = await self.users.add(User(
            email=email, full_name=data.full_name.strip(), role=data.role.value,
            password_hash=hash_password(data.password), title=data.title, phone=data.phone,
            password_changed_at=utcnow().replace(microsecond=0),
        ))
        await self.audit.record("user.create", actor=actor, entity_type="user", entity_id=user.id,
                                changes=diff({}, _snapshot(user)))
        await self.session.commit()
        await self.session.refresh(user)
        return UserOut.model_validate(user)

    async def update(self, user_id: int, data: UserUpdate, actor: User) -> UserOut:
        user = await self._get(user_id)
        before = _snapshot(user)
        changes = data.model_dump(exclude_unset=True)
        if "role" in changes and changes["role"] is not None:
            changes["role"] = changes["role"].value
        changes = {k: v for k, v in changes.items() if v is not None or k in ("title", "phone")}
        losing_admin = user.role == Role.ADMIN.value and user.is_active and (
            changes.get("role", Role.ADMIN.value) != Role.ADMIN.value or changes.get("is_active") is False
        )
        if losing_admin:
            if user.id == actor.id:
                raise ValidationFailedError("You can't remove your own admin access or deactivate yourself")
            if await self.users.count_active_admins() <= 1:
                raise ValidationFailedError("There must be at least one active admin")
        self.users.apply(user, changes)
        await self.audit.record("user.update", actor=actor, entity_type="user", entity_id=user.id,
                                changes=diff(before, _snapshot(user)))
        await self.session.commit()
        await self.session.refresh(user)
        return UserOut.model_validate(user)

    async def set_password(self, user_id: int, new_password: str, actor: User) -> None:
        user = await self._get(user_id)
        AuthService._set_password(user, new_password)
        await self.audit.record("user.password_set", actor=actor, entity_type="user", entity_id=user.id)
        await self.session.commit()
