"""Shared helpers for API tests against PostgreSQL (TEST_DATABASE_URL). Not a test module itself.

The database must already be migrated (CI runs `alembic upgrade head` first). Tests create users with
unique emails and leave their rows behind, so point TEST_DATABASE_URL at a throwaway database.
"""

from __future__ import annotations

import asyncio
import os
import unittest
import uuid
from typing import Any

RUN = bool(os.environ.get("TEST_DATABASE_URL"))
if RUN:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("DB_USE_NULL_POOL", "true")

skip_unless_db = unittest.skipUnless(RUN, "TEST_DATABASE_URL not set")
API = "/api/v1"


def reset_limits() -> None:
    from app.core import rate_limit

    for value in vars(rate_limit).values():
        if isinstance(value, rate_limit.RateLimiter):
            value.clear()


def run(coro_fn):
    async def go():
        from app.core.database import SessionFactory

        async with SessionFactory() as session:
            result = await coro_fn(session)
            await session.commit()
            return result

    return asyncio.run(go())


class World:
    """An app client, a recording email sender and helpers to make staff users."""

    def __init__(self) -> None:
        from fastapi.testclient import TestClient

        from app.integrations.email import LogEmailSender
        from app.main import create_app
        from app.modules.users.deps import email_sender

        self.mail = LogEmailSender()
        app = create_app()
        app.dependency_overrides[email_sender] = lambda: self.mail
        self.client = TestClient(app)
        self.sfx = uuid.uuid4().hex[:8]
        self._n = 0

    def email(self, label: str) -> str:
        self._n += 1
        return f"{label}-{self.sfx}-{self._n}@example.com"

    def make_user(self, role: str = "admin", password: str = "correct-horse-1", **extra: Any) -> dict[str, Any]:
        from app.core.security import hash_password
        from app.modules.users.models import User

        email = extra.pop("email", None) or self.email(role)

        async def create(session):
            user = User(email=email, full_name=extra.pop("full_name", role.title()), role=role,
                        password_hash=hash_password(password), **extra)
            session.add(user)
            await session.flush()
            return user.id

        return {"id": run(create), "email": email, "password": password}

    def login(self, email: str, password: str) -> dict[str, str]:
        res = self.client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    def user_with_token(self, role: str = "admin", **extra: Any) -> tuple[dict[str, Any], dict[str, str]]:
        user = self.make_user(role, **extra)
        return user, self.login(user["email"], user["password"])
