from sqlalchemy import Select

from app.shared.repository import BaseRepository

from .models import AuditLog


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def search(
        self, *, action: str | None = None, entity_type: str | None = None, entity_id: int | None = None,
        actor_id: int | None = None,
    ) -> Select[tuple[AuditLog]]:
        stmt = self.query()
        if action:
            stmt = stmt.where(AuditLog.action.startswith(action))
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        return stmt.order_by(AuditLog.at.desc(), AuditLog.id.desc())
