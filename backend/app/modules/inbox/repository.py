from sqlalchemy import Select, func, select

from app.shared.repository import BaseRepository

from .models import EmailAccount


class EmailAccountRepository(BaseRepository[EmailAccount]):
    model = EmailAccount

    def ordered(self) -> Select[tuple[EmailAccount]]:
        return self.query().order_by(func.lower(EmailAccount.address), EmailAccount.id)

    async def by_address(self, address: str) -> EmailAccount | None:
        """Case-insensitively, so "Support@…" can't be set up next to "support@…"."""
        stmt = self.query().where(func.lower(EmailAccount.address) == address.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()
