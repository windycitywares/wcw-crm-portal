from datetime import datetime

from sqlalchemy import Select, func, or_, select

from app.core.permissions import Role
from app.shared.repository import BaseRepository

from .models import PasswordResetToken, User


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class UserRepository(BaseRepository[User]):
    model = User

    async def by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def search(self, *, q: str | None = None, role: Role | None = None, active: bool | None = None) -> Select[tuple[User]]:
        stmt = self.query()
        if q:
            pattern = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(func.lower(User.full_name).like(pattern), User.email.like(pattern)))
        if role:
            stmt = stmt.where(User.role == role.value)
        if active is not None:
            stmt = stmt.where(User.is_active.is_(active))
        return stmt.order_by(func.lower(User.full_name), User.id)

    async def directory(self) -> list[User]:
        return list(await self.list(self.query().order_by(User.is_active.desc(), func.lower(User.full_name))))

    async def count_active_admins(self) -> int:
        stmt = select(func.count()).select_from(User).where(User.role == Role.ADMIN.value, User.is_active.is_(True))
        return (await self.session.execute(stmt)).scalar_one()


class ResetTokenRepository(BaseRepository[PasswordResetToken]):
    model = PasswordResetToken

    async def by_hash(self, token_hash: str) -> PasswordResetToken | None:
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def invalidate_for_user(self, user_id: int, now: datetime) -> None:
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None)
        )
        for token in (await self.session.execute(stmt)).scalars():
            token.used_at = now
