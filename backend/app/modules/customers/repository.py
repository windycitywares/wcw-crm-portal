from sqlalchemy import Select, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.shared.repository import BaseRepository
from app.shared.text import phone_digits

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


def _digits(value: str) -> ColumnElement[str]:
    """What a stored phone number's digits look like to Postgres: the punctuation is ours, not theirs."""
    return func.regexp_replace(value, r"\D", "", "g")


def phone_forms(phone: str) -> list[str]:
    """The digit strings a stored number may hold that mean the same number as this one.

    A number is stored as it was typed ("(312) 555-0142", "+1 312 555 0142") and arrives from a gateway as
    E.164 ("+13125550142"), so both sides are compared by their digits: the number as it is, and — for a
    ten-digit North-American one — with the country code in front, which is how the other side may have
    written it. Empty means "no number here" (`phone_digits` found no digits)."""
    digits = phone_digits(phone)
    if not digits:
        return []
    return sorted({digits, f"1{digits}"} if len(digits) == 10 else {digits})


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def by_email(self, email: str) -> Customer | None:
        stmt = self.query().where(Customer.email == email.strip().lower())
        return (await self.session.execute(stmt)).scalars().first()

    async def by_any_email(self, email: str) -> Customer | None:
        """A customer's main address, or one a merge kept aside as an alternate — so somebody writing in
        from an address we already know isn't added twice."""
        email = email.strip().lower()
        stmt = self.query().where(or_(Customer.email == email, Customer.alt_emails.contains([email])))
        return (await self.session.execute(stmt)).scalars().first()

    async def by_shop_user(self, shop_user_id: int) -> Customer | None:
        stmt = select(Customer).where(Customer.shop_user_id == shop_user_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def by_phone(self, phone: str) -> Customer | None:
        """The live customer whose number this is, comparing digits rather than punctuation (`phone_forms`).

        A number is written down the way the person said it ("(312) 555-0142") and arrives from a gateway as
        E.164 ("+13125550142"), so only the digits can be trusted to match. Live rows only: a number a merge
        moved aside belongs to the record that kept it, and matching the copy would file a message on the
        wrong person."""
        forms = phone_forms(phone)
        if not forms:
            return None
        stmt = self.query().where(_digits(Customer.phone).in_(forms))
        return (await self.session.execute(stmt)).scalars().first()

    def search(self, *, q: str | None = None, customer_type: str | None = None, status: str | None = None,
               owner_id: int | None = None, ids: list[int] | None = None, has_orders: bool | None = None,
               deleted: bool = False, sort: str = "-updated") -> Select[tuple[Customer]]:
        stmt = select(Customer).where(Customer.deleted_at.is_not(None) if deleted else Customer.deleted_at.is_(None))
        if q:
            words = [w for w in q.strip().lower().split() if w][:5]
            for word in words:
                p = f"%{escape_like(word)}%"
                conditions = [
                    func.lower(Customer.first_name).like(p), func.lower(Customer.last_name).like(p),
                    func.lower(Customer.company).like(p), Customer.email.like(p), Customer.phone.like(p),
                ]
                digits = phone_digits(word)
                if len(digits) >= 7:
                    # Somebody pasted a whole number: the row may hold it with punctuation it doesn't share
                    # with what was typed here ("(312) 555-0142" against "+1 312 555 0142").
                    conditions.append(_digits(Customer.phone).like(f"%{digits}%"))
                stmt = stmt.where(or_(*conditions))
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
