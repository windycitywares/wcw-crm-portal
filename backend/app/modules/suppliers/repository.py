from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import Supplier, SupplierContact


class SupplierRepository(BaseRepository[Supplier]):
    model = Supplier

    def search(self, *, q: str | None = None, supplier_type: str | None = None,
               status: str | None = None) -> Select[tuple[Supplier]]:
        stmt = self.query()
        if q:
            pattern = f"%{q.strip().lower()}%"
            stmt = stmt.where(or_(
                func.lower(Supplier.name).like(pattern),
                func.lower(Supplier.supplier_type).like(pattern),
                func.lower(Supplier.website).like(pattern),
            ))
        if supplier_type:
            stmt = stmt.where(Supplier.supplier_type == supplier_type)
        if status:
            stmt = stmt.where(Supplier.status == status)
        return stmt.order_by(func.lower(Supplier.name), Supplier.id)

    async def contacts_for(self, supplier_ids: list[int]) -> dict[int, list[SupplierContact]]:
        if not supplier_ids:
            return {}
        stmt = select(SupplierContact).where(
            SupplierContact.supplier_id.in_(supplier_ids), SupplierContact.deleted_at.is_(None),
        ).order_by(SupplierContact.is_primary.desc(), func.lower(SupplierContact.name), SupplierContact.id)
        rows = (await self.session.execute(stmt)).scalars().all()
        out: dict[int, list[SupplierContact]] = {supplier_id: [] for supplier_id in supplier_ids}
        for contact in rows:
            out[contact.supplier_id].append(contact)
        return out

    async def contact(self, supplier_id: int, contact_id: int) -> SupplierContact | None:
        stmt = select(SupplierContact).where(
            SupplierContact.id == contact_id,
            SupplierContact.supplier_id == supplier_id,
            SupplierContact.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SupplierContactRepository(BaseRepository[SupplierContact]):
    model = SupplierContact