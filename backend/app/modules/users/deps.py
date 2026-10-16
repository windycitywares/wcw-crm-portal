"""Authentication dependencies. Every module protects its routes with these:

    @router.get("", dependencies=[Depends(require(Permission.CUSTOMERS_VIEW))])
    async def list_customers(session: SessionDep, user: CurrentUser): ...

This is the one cross-module import every module is allowed to make.
"""

from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.permissions import Permission, has_permission
from app.core.security import decode_access_token
from app.integrations.email import EmailSender, get_email_sender

from .models import User

bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmailSenderDep = Annotated[EmailSender, Depends(get_email_sender)]


async def get_current_user(
    session: SessionDep, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    if credentials is None:
        raise AuthenticationError("Not signed in")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AuthenticationError("Your session has expired — please sign in again")
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise AuthenticationError("Account not found or disabled")
    if user.password_changed_at and int(payload.get("iat", 0)) < int(user.password_changed_at.timestamp()):
        raise AuthenticationError("Your password was changed — please sign in again")
    if payload.get("role") != user.role:
        raise AuthenticationError("Your access changed — please sign in again")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(*permissions: Permission):
    """Dependency factory: `Depends(require(Permission.CUSTOMERS_VIEW))`. All listed permissions are needed."""

    async def _checker(user: CurrentUser) -> User:
        if any(not has_permission(user.role, p) for p in permissions):
            raise PermissionDeniedError("You don't have permission to do that")
        return user

    return _checker
