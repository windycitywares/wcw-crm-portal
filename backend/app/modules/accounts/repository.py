from sqlalchemy import Select, column, func, or_, select, table

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
               owner_id: int | None = None, parent_id: int | None = None,
               sort: str = "name") -> Select[tuple[Account]]:
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
        if parent_id is not None:
            stmt = stmt.where(Account.parent_id == parent_id)
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

    async def children_counts(self, ids: list[int]) -> dict[int, int]:
        if not ids:
            return {}
        rows = await self.session.execute(
            select(Account.parent_id, func.count()).where(Account.parent_id.in_(ids), Account.deleted_at.is_(None))
            .group_by(Account.parent_id))
        return {p: n for p, n in rows.all()}

    async def child_ids(self, ids: list[int]) -> list[int]:
        rows = await self.session.execute(
            select(Account.id).where(Account.parent_id.in_(ids), Account.deleted_at.is_(None)))
        return list(rows.scalars())

    async def subtree(self, root_id: int, *, max_depth: int) -> list[tuple[Account, int]]:
        """The account and every live account under it, depth-first, children by name."""
        root = await self.get(root_id)
        if root is None:
            return []
        out: list[tuple[Account, int]] = []
        seen: set[int] = set()

        async def walk(node: Account, depth: int) -> None:
            if node.id in seen:
                return
            seen.add(node.id)
            out.append((node, depth))
            if depth >= max_depth:
                return
            kids = (await self.session.execute(self.query().where(Account.parent_id == node.id)
                                               .order_by(func.lower(Account.name), Account.id))).scalars().all()
            for kid in kids:
                await walk(kid, depth + 1)

        await walk(root, 0)
        return out

    async def open_deals(self, ids: list[int]) -> dict[int, tuple[int, float]]:
        """Open deals per account: (how many, total value). Read from the deals table without the sales module."""
        if not ids:
            return {}
        deals = table("deals", column("account_id"), column("status"), column("value"), column("deleted_at"))
        rows = await self.session.execute(
            select(deals.c.account_id, func.count(), func.coalesce(func.sum(deals.c.value), 0))
            .where(deals.c.account_id.in_(ids), deals.c.status == "open", deals.c.deleted_at.is_(None))
            .group_by(deals.c.account_id))
        return {a: (int(n), float(v)) for a, n, v in rows.all()}
