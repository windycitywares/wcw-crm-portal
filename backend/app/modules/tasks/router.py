from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import TaskCreate, TaskOut, TaskPage, TaskSummary, TaskUpdate
from .service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require(Permission.TASKS_VIEW))])


@router.get("", response_model=TaskPage)
async def list_tasks(
    session: SessionDep, user: CurrentUser, page: PageDep,
    view: Literal["mine", "team", "created"] = "mine",
    status_: Annotated[Literal["open", "done", "cancelled", "all"], Query(alias="status")] = "open",
    due: Literal["any", "overdue", "today", "week", "none"] = "any", owner_id: int | None = None,
    related_type: str | None = None, related_id: int | None = None, type: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> TaskPage:
    return await TaskService(session).list(
        user, page, view=view, status=None if status_ == "all" else status_, due=due, owner_id=owner_id,
        related_type=related_type, related_id=related_id, task_type=type, q=q)


@router.get("/summary", response_model=TaskSummary)
async def my_summary(session: SessionDep, user: CurrentUser) -> TaskSummary:
    """Counts for the signed-in user's open work (sidebar badge, dashboard)."""
    return await TaskService(session).summary(user)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(session: SessionDep, actor: Annotated[User, Depends(require(Permission.TASKS_EDIT_OWN))],
                      data: TaskCreate) -> TaskOut:
    return await TaskService(session).create(data, actor)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(session: SessionDep, task_id: int) -> TaskOut:
    return await TaskService(session).get(task_id)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(session: SessionDep, actor: CurrentUser, task_id: int, data: TaskUpdate) -> TaskOut:
    return await TaskService(session).update(task_id, data, actor)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(session: SessionDep, actor: CurrentUser, task_id: int) -> None:
    await TaskService(session).delete(task_id, actor)
