from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status

from app.modules.users.deps import CurrentUser, SessionDep
from app.modules.users.service import UserService

from .service import SOURCES, NotificationService

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def notifications(
    response: Response, session: SessionDep, user: CurrentUser, limit: int = Query(20, ge=1, le=100),
    kind: Annotated[list[str] | None, Query(max_length=10)] = None, before: datetime | None = None,
) -> dict[str, Any]:
    """The bell: newest first, only kinds this person can act on. `kind` filters, `before` pages."""
    response.headers["Cache-Control"] = "no-store"
    kinds = [k for k in (kind or []) if k in SOURCES] or None
    return await NotificationService(session).feed(user, limit, kinds, before)


@router.post("/notifications/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_seen(session: SessionDep, user: CurrentUser) -> None:
    """Everything up to now counts as read (called when the bell is opened)."""
    await UserService(session).mark_notifications_seen(user.id)


@router.get("/live/events")
async def live_events(response: Response, session: SessionDep, user: CurrentUser,
                      after_id: Annotated[int | None, Query(ge=0)] = None) -> dict[str, Any]:
    """What changed since `after_id` (polled every few seconds by the web app). No `after_id`: where "now" is."""
    response.headers["Cache-Control"] = "no-store"
    return await NotificationService(session).live(user, after_id)
