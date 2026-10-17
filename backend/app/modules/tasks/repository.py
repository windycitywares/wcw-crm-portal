from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, or_, select

from app.shared.repository import BaseRepository

from .models import Task


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TaskRepository(BaseRepository[Task]):
    model = Task

    def search(self, *, owner_id: int | None = None, created_by: int | None = None, status: str | None = "open",
               due_before: datetime | None = None, due_from: datetime | None = None, no_due: bool = False,
               related_type: str | None = None, related_id: int | None = None, task_type: str | None = None,
               q: str | None = None) -> Select[tuple[Task]]:
        stmt = self.query()
        if owner_id is not None:
            stmt = stmt.where(Task.owner_id == owner_id)
        if created_by is not None:
            stmt = stmt.where(Task.created_by == created_by)
        if status:
            stmt = stmt.where(Task.status == status)
        if due_before is not None:
            stmt = stmt.where(Task.due_at < due_before)
        if due_from is not None:
            stmt = stmt.where(Task.due_at >= due_from)
        if no_due:
            stmt = stmt.where(Task.due_at.is_(None))
        if related_type is not None:
            stmt = stmt.where(Task.related_type == related_type)
        if related_id is not None:
            stmt = stmt.where(Task.related_id == related_id)
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(func.lower(Task.title).like(p), func.lower(Task.description).like(p)))
        # open work by due date (undated last); finished work newest first
        if status == "open":
            return stmt.order_by(Task.due_at.asc().nullslast(), Task.id)
        return stmt.order_by(func.coalesce(Task.completed_at, Task.updated_at).desc(), Task.id.desc())

    async def count_where(self, *conditions) -> int:
        stmt = select(func.count()).select_from(Task).where(Task.deleted_at.is_(None), *conditions)
        return int((await self.session.execute(stmt)).scalar_one())

    async def reminders_due(self, now: datetime, limit: int = 100) -> list[Task]:
        stmt = (self.query().where(Task.status == "open", Task.reminded_at.is_(None), Task.reminder_at <= now)
                .order_by(Task.reminder_at).limit(limit))
        return list((await self.session.execute(stmt)).scalars())
