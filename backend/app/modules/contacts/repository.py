from sqlalchemy import Select, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.shared.repository import BaseRepository
from app.shared.text import phone_digits

from .models import Contact

SORTS = {
    "name": (func.lower(Contact.first_name), func.lower(Contact.last_name)),
    "-created": (Contact.created_at.desc(),),
    "created": (Contact.created_at,),
    "-updated": (Contact.updated_at.desc(),),
}


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _digits(value: str) -> ColumnElement[str]:
    return func.regexp_replace(value, r"\D", "", "g")


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    async def by_email(self, email: str) -> Contact | None:
        stmt = self.query().where(Contact.email == email.strip().lower())
        return (await self.session.execute(stmt)).scalars().first()

    async def by_any_email(self, email: str) -> Contact | None:
        """The main address or an alternate a merge kept aside."""
        email = email.strip().lower()
        stmt = self.query().where(or_(Contact.email == email, Contact.alt_emails.contains([email])))
        return (await self.session.execute(stmt)).scalars().first()

    async def by_user(self, user_id: int) -> Contact | None:
        stmt = self.query().where(Contact.user_id == user_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def by_customer(self, customer_id: int) -> Contact | None:
        stmt = self.query().where(Contact.customer_id == customer_id)
        return (await self.session.execute(stmt)).scalars().first()

    def search(self, *, q: str | None = None, type: str | None = None, status: str | None = None,
               owner_id: int | None = None, sort: str = "-updated") -> Select[tuple[Contact]]:
        stmt = self.query()
        if q:
            words = [w for w in q.strip().lower().split() if w][:5]
            for word in words:
                p = f"%{escape_like(word)}%"
                conditions = [
                    func.lower(Contact.first_name).like(p), func.lower(Contact.last_name).like(p),
                    func.lower(Contact.company).like(p), func.lower(Contact.title).like(p),
                    Contact.email.like(p), Contact.phone.like(p),
                ]
                digits = phone_digits(word)
                if len(digits) >= 7:
                    conditions.append(_digits(Contact.phone).like(f"%{digits}%"))
                stmt = stmt.where(or_(*conditions))
        if type:
            stmt = stmt.where(Contact.types.contains([type]))
        if status:
            stmt = stmt.where(Contact.status == status)
        if owner_id is not None:
            stmt = stmt.where(Contact.owner_id == owner_id)
        return stmt.order_by(*SORTS.get(sort, SORTS["-updated"]), Contact.id.desc())
