from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import Account

SORTS = {
    "name": (func.lower(Account.name),),
    "-updated": (Account.updated_at.desc(),),
    "-created": (Account.created_at.desc(),),
}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class AccountRepository(BaseRepository[Account]):
    model = Account

    def search(self, *, q: str | None = None, account_type: str | None = None, status: str | None = None,
               owner_id: int | None = None, sort: str = "name") -> Select[tuple[Account]]:
        stmt = self.query()
        if q:
            for word in [w for w in q.strip().lower().split() if w][:5]:
                p = f"%{_escape(word)}%"
                stmt = stmt.where(or_(
                    func.lower(Account.name).like(p), func.lower(Account.industry).like(p),
                    func.lower(Account.website).like(p), func.lower(Account.email).like(p),
                    Account.phone.like(p),
                ))
        if account_type:
            stmt = stmt.where(Account.account_type == account_type)
        if status:
            stmt = stmt.where(Account.status == status)
        if owner_id is not None:
            stmt = stmt.where(Account.owner_id == owner_id)
        return stmt.order_by(*SORTS.get(sort, SORTS["name"]), Account.id)

    async def by_name(self, name: str, *, account_type: str | None = None) -> Account | None:
        stmt = self.query().where(func.lower(Account.name) == name.strip().lower())
        if account_type:
            stmt = stmt.where(Account.account_type == account_type)
        return (await self.session.execute(stmt.order_by(Account.id))).scalars().first()

    async def names(self, ids: list[int], *, include_deleted: bool = True) -> dict[int, str]:
        if not ids:
            return {}
        stmt = select(Account.id, Account.name).where(Account.id.in_(ids))
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))
        return {row.id: row.name for row in (await self.session.execute(stmt)).all()}
