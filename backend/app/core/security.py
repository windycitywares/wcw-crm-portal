"""Password hashing, JWT helpers and encryption of secrets stored in the database."""

from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict, cast

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class AccessTokenPayload(TypedDict):
    """The claims carried by an access token once decoded.

    PyJWT turns the `iat`/`exp` datetimes we encode into Unix timestamps on the way out, so
    they arrive here as integers. Fields are not guaranteed to be present in a token we did
    not mint — callers still have to handle a missing `sub` or `role`.
    """

    sub: str
    role: str
    iat: int
    exp: int
    type: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str | int, role: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    minutes = expires_minutes or settings.access_token_expire_minutes
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AccessTokenPayload:
    """Raises jwt.PyJWTError on an invalid or expired token."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Wrong token type")
    return cast(AccessTokenPayload, payload)


class SecretBox:
    """Encrypts secrets kept in the database (SMTP password, API tokens) with DATA_ENCRYPTION_KEY."""

    def __init__(self, key: str | None = None):
        key = key or get_settings().data_encryption_key
        if not key:
            raise RuntimeError("DATA_ENCRYPTION_KEY is not set")
        self._fernet = Fernet(key.encode())

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Secret can't be decrypted (wrong DATA_ENCRYPTION_KEY?)") from exc
