from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import Customer

SORTS = {
    "name": (func.lower(Customer.first_name), func.lower(Customer.last_name)),
    "-created": (Customer.created_at.desc(),),
    "created": (Customer.created_at,),
    "-last_order": (Customer.last_order_at.desc().nullslast(),),
    "-total_spent": (Customer.total_spent.desc(),),
    "-updated": (Customer.updated_at.desc(),),
}


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def by_email(self, email: str) -> Customer | None:
        stmt = self.query().where(Customer.email == email.strip().lower())
        return (await self.session.execute(stmt)).scalars().first()

    async def by_shop_user(self, shop_user_id: int) -> Customer | None:
        stmt = select(Customer).where(Customer.shop_user_id == shop_user_id)
        return (await self.session.execute(stmt)).scalars().first()

    def search(self, *, q: str | None = None, customer_type: str | None = None, status: str | None = None,
               owner_id: int | None = None, ids: list[int] | None = None, has_orders: bool | None = None,
               deleted: bool = False, sort: str = "-updated") -> Select[tuple[Customer]]:
        stmt = select(Customer).where(Customer.deleted_at.is_not(None) if deleted else Customer.deleted_at.is_(None))
        if q:
            words = [w for w in q.strip().lower().split() if w][:5]
            for word in words:
                p = f"%{escape_like(word)}%"
                stmt = stmt.where(or_(
                    func.lower(Customer.first_name).like(p), func.lower(Customer.last_name).like(p),
                    func.lower(Customer.company).like(p), Customer.email.like(p), Customer.phone.like(p),
                ))
        if customer_type:
            stmt = stmt.where(Customer.customer_type == customer_type)
        if status:
            stmt = stmt.where(Customer.status == status)
        if owner_id is not None:
            stmt = stmt.where(Customer.owner_id == owner_id)
        if ids is not None:
            stmt = stmt.where(Customer.id.in_(ids or [-1]))
        if has_orders is not None:
            stmt = stmt.where(Customer.orders_count > 0 if has_orders else Customer.orders_count == 0)
        return stmt.order_by(*SORTS.get(sort, SORTS["-updated"]), Customer.id.desc())
