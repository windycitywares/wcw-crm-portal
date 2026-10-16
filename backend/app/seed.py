"""Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD when the CRM has no admin yet.

    python -m app.seed

Safe to run repeatedly: it never changes an existing account. Later milestones add seed data here
(lookup types, pipelines, SLA policy — SPEC §9) through each module's own seeder.
"""

import asyncio

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules import load_modules
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


async def seed_admin() -> str:
    settings = get_settings()
    async with SessionFactory() as session:
        repo = UserRepository(session)
        if await repo.count_active_admins():
            return "admin exists — nothing to do"
        if not settings.admin_email or not settings.admin_password:
            return "no admin yet: set ADMIN_EMAIL and ADMIN_PASSWORD in backend/.env and run again"
        if len(settings.admin_password) < 10:
            return "ADMIN_PASSWORD must be at least 10 characters"
        email = settings.admin_email.strip().lower()
        existing = await repo.by_email(email)
        if existing:
            return f"{email} exists but isn't an active admin — promote it in the database or pick another email"
        await repo.add(User(email=email, full_name="Administrator", role=Role.ADMIN.value,
                            password_hash=hash_password(settings.admin_password)))
        await session.commit()
        return f"created admin {email} — change the password after signing in"


async def main() -> None:
    load_modules()
    print(await seed_admin())


if __name__ == "__main__":
    asyncio.run(main())
