from __future__ import annotations

from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import Lead


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class LeadRepository(BaseRepository[Lead]):
    model = Lead

    def search(self, *, status: str | None = None, source: str | None = None, owner_id: int | None = None,
               unassigned: bool = False, q: str | None = None) -> Select[tuple[Lead]]:
        stmt = self.query()
        if status:
            stmt = stmt.where(Lead.status == status)
        if source:
            stmt = stmt.where(Lead.source == source)
        if owner_id is not None:
            stmt = stmt.where(Lead.owner_id == owner_id)
        if unassigned:
            stmt = stmt.where(Lead.owner_id.is_(None))
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(
                func.lower(Lead.first_name).like(p), func.lower(Lead.last_name).like(p),
                func.lower(Lead.company).like(p), func.lower(Lead.email).like(p),
                func.lower(Lead.phone).like(p),
            ))
        # newest first: a lead list is worked from the top
        return stmt.order_by(Lead.created_at.desc(), Lead.id.desc())

    async def by_email(self, email: str) -> Lead | None:
        """The newest lead with this address — used to warn about duplicates, not to enforce them."""
        rows = await self.list(self.query().where(func.lower(Lead.email) == email.strip().lower())
                               .order_by(Lead.id.desc()).limit(1))
        return rows[0] if rows else None

    async def count_where(self, *conditions) -> int:
        stmt = select(func.count()).select_from(Lead).where(Lead.deleted_at.is_(None), *conditions)
        return int((await self.session.execute(stmt)).scalar_one())
