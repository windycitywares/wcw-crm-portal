"""Tasks (SPEC §3.4): to-dos for the team, optionally about a record (customer, ticket, deal …).

Rules:
- everyone with tasks:edit_own can add tasks for themselves and change tasks assigned to or created by them;
  tasks:assign lets them give tasks to others; tasks:edit_any changes anyone's;
- a task about a record needs read access to that record; the record's timeline shows the task being added/done;
- completing a recurring task creates the next one (same assignee, dates moved on);
- reminders are emailed to the assignee by the `task-reminders` job.
"""

from __future__ import annotations

import calendar
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, check_entity_access, entity_labels, register_entity
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.pagination import PageParams
from app.core.permissions import Permission, has_permission
from app.integrations.email import Mail, get_email_sender
from app.modules.activity.service import TimelineService
from app.modules.audit.service import AuditService, diff
from app.modules.lookups.service import LookupService
from app.modules.settings.service import SettingsService

from .models import Task
from .repository import TaskRepository
from .schemas import TaskCreate, TaskOut, TaskPage, TaskSummary, TaskUpdate

ENTITY = "task"
TRACKED = ("title", "task_type", "priority", "status", "due_at", "owner_id", "related_type", "related_id", "recurrence")
Views = ("mine", "team", "created")
Dues = ("any", "overdue", "today", "week", "none")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot(t: Task) -> dict[str, Any]:
    """Audit-friendly values (dates as ISO text: the audit log is JSON)."""
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k in TRACKED for v in [getattr(t, k)]}


def _add_months(value: datetime, months: int) -> datetime:
    month = value.month - 1 + months
    year, month = value.year + month // 12, month % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


def next_occurrence(value: datetime, recurrence: str) -> datetime:
    if recurrence == "daily":
        return value + timedelta(days=1)
    if recurrence == "weekly":
        return value + timedelta(days=7)
    return _add_months(value, 1)


async def _exists(session, entity_id: int) -> bool:
    return await TaskRepository(session).get(entity_id) is not None


def _may_change(user, task: Task) -> bool:
    return has_permission(user.role, Permission.TASKS_EDIT_ANY) or (
        has_permission(user.role, Permission.TASKS_EDIT_OWN) and user.id in (task.owner_id, task.created_by))


async def _can_edit(session, user, entity_id: int) -> bool:
    task = await TaskRepository(session).get(entity_id)
    return task is not None and _may_change(user, task)


async def _labels(session, ids: list[int]) -> dict[int, str]:
    repo = TaskRepository(session)
    return {t.id: t.title for t in await repo.list(repo.query(include_deleted=True).where(Task.id.in_(ids)))}


def register() -> None:
    register_entity(EntityType(
        key=ENTITY, label="Task", view=(Permission.TASKS_VIEW,),
        edit=(Permission.TASKS_EDIT_OWN, Permission.TASKS_EDIT_ANY), exists=_exists, can_edit=_can_edit, labels=_labels,
    ))


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TaskRepository(session)
        self.audit = AuditService(session)
        self.timeline = TimelineService(session)
        self.lookups = LookupService(session)

    # ---- helpers ------------------------------------------------------------------------
    async def _tz(self) -> ZoneInfo:
        hours = await SettingsService(self.session).get_model("business_hours")
        return ZoneInfo(getattr(hours, "timezone", "America/Chicago"))

    async def _day_bounds(self) -> tuple[datetime, datetime]:
        tz = await self._tz()
        start = datetime.combine(datetime.now(tz).date(), time(0), tz)
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)

    async def _out(self, tasks: list[Task]) -> list[TaskOut]:
        labels: dict[tuple[str, int], str] = {}
        by_type: dict[str, list[int]] = {}
        for t in tasks:
            if t.related_type and t.related_id:
                by_type.setdefault(t.related_type, []).append(t.related_id)
        for kind, ids in by_type.items():
            for rid, label in (await entity_labels(self.session, kind, ids)).items():
                labels[(kind, rid)] = label
        now = _now()
        out = []
        for t in tasks:
            item = TaskOut.model_validate(t)
            item.related_label = labels.get((t.related_type or "", t.related_id or 0))
            item.is_overdue = t.status == "open" and t.due_at is not None and t.due_at < now
            out.append(item)
        return out

    async def _get(self, task_id: int) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        return task

    async def _check_related(self, user, related_type: str | None, related_id: int | None) -> None:
        if related_type is not None and related_id is not None:
            if related_type == ENTITY:
                raise ValidationFailedError("A task can't be about another task")
            await check_entity_access(self.session, user, related_type, related_id, write=False)

    def _check_owner(self, user, owner_id: int | None, current: int | None = None) -> None:
        if owner_id is not None and owner_id != user.id and owner_id != current \
                and not has_permission(user.role, Permission.TASKS_ASSIGN):
            raise PermissionDeniedError("Only managers can give tasks to someone else")

    async def _related_line(self, task: Task, kind: str, title: str, actor) -> None:
        if task.related_type and task.related_id:
            await self.timeline.record(task.related_type, task.related_id, kind, title, actor=actor,
                                       data={"task_id": task.id})

    # ---- reads ------------------------------------------------------------------------------
    async def list(self, user, params: PageParams, *, view: str = "mine", status: str | None = "open", due: str = "any",
                   owner_id: int | None = None, related_type: str | None = None, related_id: int | None = None,
                   task_type: str | None = None, q: str | None = None) -> TaskPage:
        filters: dict[str, Any] = {"status": status, "related_type": related_type, "related_id": related_id,
                                   "task_type": task_type, "q": q}
        if related_type is not None and related_id is not None:
            await check_entity_access(self.session, user, related_type, related_id, write=False)
        elif view == "mine":
            filters["owner_id"] = user.id
        elif view == "created":
            filters["created_by"] = user.id
        if owner_id is not None:
            filters["owner_id"] = owner_id
        if due != "any":
            start, end = await self._day_bounds()
            if due == "overdue":
                filters["due_before"] = _now()
            elif due == "today":
                filters["due_from"], filters["due_before"] = start, end
            elif due == "week":
                filters["due_before"] = start + timedelta(days=7)
            elif due == "none":
                filters["no_due"] = True
        rows, total = await self.repo.paginate(self.repo.search(**filters), params)
        return TaskPage(items=await self._out(list(rows)), total=total, page=params.page, page_size=params.page_size)

    async def get(self, task_id: int) -> TaskOut:
        return (await self._out([await self._get(task_id)]))[0]

    async def summary(self, user) -> TaskSummary:
        start, end = await self._day_bounds()
        mine = (Task.owner_id == user.id, Task.status == "open")
        return TaskSummary(
            open=await self.repo.count_where(*mine),
            overdue=await self.repo.count_where(*mine, Task.due_at < _now()),
            due_today=await self.repo.count_where(*mine, Task.due_at >= start, Task.due_at < end),
        )

    # ---- writes -------------------------------------------------------------------------------
    async def create(self, data: TaskCreate, actor) -> TaskOut:
        values = data.model_dump(exclude_unset=True)
        owner_id = values.pop("owner_id", None) or actor.id
        self._check_owner(actor, owner_id)
        await self._check_related(actor, values.get("related_type"), values.get("related_id"))
        if values.get("task_type"):
            values["task_type"] = await self.lookups.require("task_type", values["task_type"])
        task = Task(**{k: v for k, v in values.items() if v is not None}, owner_id=owner_id,
                    created_by=actor.id, updated_by=actor.id)
        await self.repo.add(task)
        await self.audit.record("task.create", actor=actor, entity_type=ENTITY, entity_id=task.id,
                                changes=diff({}, _snapshot(task)))
        await self._related_line(task, "task.created", f"Task added: {task.title}", actor)
        await self.session.commit()
        return await self.get(task.id)

    async def update(self, task_id: int, data: TaskUpdate, actor) -> TaskOut:
        task = await self._get(task_id)
        if not _may_change(actor, task):
            raise PermissionDeniedError("You can only change tasks assigned to or created by you")
        values = data.model_dump(exclude_unset=True)
        if "title" in values and not values["title"]:
            raise ValidationFailedError("A task needs a title")
        if "owner_id" in values:
            if values["owner_id"] is None:
                values["owner_id"] = task.owner_id
            self._check_owner(actor, values["owner_id"], task.owner_id)
        if "related_type" in values or "related_id" in values:
            await self._check_related(actor, values.get("related_type"), values.get("related_id"))
        if values.get("task_type"):
            values["task_type"] = await self.lookups.require("task_type", values["task_type"],
                                                             allow_inactive_key=task.task_type)
        if "priority" in values and values["priority"] is None:
            values.pop("priority")
        if "due_has_time" in values and values["due_has_time"] is None:
            values.pop("due_has_time")
        new_status = values.pop("status", None)
        if "reminder_at" in values and values["reminder_at"] != task.reminder_at:
            task.reminded_at = None  # a new reminder time sends again
        before = _snapshot(task)
        self.repo.apply(task, values)
        if new_status and new_status != task.status:
            await self._set_status(task, new_status, actor)
        task.updated_by = actor.id
        await self.session.flush()
        changes = diff(before, _snapshot(task))
        if changes:
            await self.audit.record("task.update", actor=actor, entity_type=ENTITY, entity_id=task.id, changes=changes)
        await self.session.commit()
        return await self.get(task.id)

    async def _set_status(self, task: Task, status: str, actor) -> Task | None:
        task.status = status
        if status == "done":
            task.completed_at, task.completed_by = _now(), actor.id
            await self._related_line(task, "task.done", f"Task done: {task.title}", actor)
            if task.recurrence:
                return await self._next(task, actor)
        else:
            task.completed_at = task.completed_by = None
        return None

    async def _next(self, task: Task, actor) -> Task:
        base = task.due_at or _now()
        due = next_occurrence(base, task.recurrence or "weekly")
        while due < _now():  # finished late: skip the dates already gone
            due = next_occurrence(due, task.recurrence or "weekly")
        reminder = due - (base - task.reminder_at) if task.reminder_at and task.due_at else None
        nxt = Task(title=task.title, description=task.description, task_type=task.task_type, priority=task.priority,
                   due_at=due, due_has_time=task.due_has_time, reminder_at=reminder, recurrence=task.recurrence,
                   owner_id=task.owner_id, related_type=task.related_type, related_id=task.related_id,
                   created_by=actor.id, updated_by=actor.id)
        await self.repo.add(nxt)
        await self.audit.record("task.create", actor=actor, entity_type=ENTITY, entity_id=nxt.id,
                                changes={"repeats": task.id})
        return nxt

    async def delete(self, task_id: int, actor) -> None:
        task = await self._get(task_id)
        if not _may_change(actor, task):
            raise PermissionDeniedError("You can only delete tasks assigned to or created by you")
        await self.repo.soft_delete(task)
        await self.audit.record("task.delete", actor=actor, entity_type=ENTITY, entity_id=task.id,
                                changes={"title": task.title})
        await self.session.commit()

    # ---- reminders (job) -------------------------------------------------------------------
    async def send_reminders(self, sender=None) -> str | None:
        from app.core.config import get_settings
        from app.modules.users.service import UserService

        due = await self.repo.reminders_due(_now())
        if not due:
            return None
        contacts = {uid: (name, email) for uid, name, email in await UserService(self.session).contacts()}
        sender = sender or get_email_sender(self.session)
        tz = await self._tz()
        site = get_settings().site_url.rstrip("/")
        sent = 0
        for task in due:
            task.reminded_at = _now()
            person = contacts.get(task.owner_id or 0)
            if not person:
                continue
            name, email = person
            when = ""
            if task.due_at:
                local = task.due_at.astimezone(tz)
                when = local.strftime("%a %b %d, %I:%M %p") if task.due_has_time else local.strftime("%a %b %d")
            await sender.send(Mail(
                to=email, subject=f"Reminder: {task.title}",
                text=(f"Hi {name.split(' ')[0]},\n\nA reminder about your task \"{task.title}\""
                      f"{f' (due {when})' if when else ''}.\n\nOpen it: {site}/tasks?task={task.id}\n"),
            ))
            sent += 1
        await self.session.commit()
        return f"task reminders: {sent} sent" if sent else None
