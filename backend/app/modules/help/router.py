from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User

from .schemas import FeedbackIn, FeedbackOut, TopicSummary
from .service import HelpFeedbackService

router = APIRouter(tags=["help"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


@router.post("/help/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def send_feedback(session: SessionDep, user: CurrentUser, data: FeedbackIn) -> None:
    """Anyone signed in may say whether a guide helped."""
    await HelpFeedbackService(session).add(data, user)


@router.get("/help/feedback/summary", response_model=list[TopicSummary])
async def feedback_summary(session: SessionDep, _: Admin) -> list[TopicSummary]:
    return await HelpFeedbackService(session).summary()


@router.get("/help/feedback", response_model=list[FeedbackOut])
async def feedback_list(session: SessionDep, _: Admin, topic_id: str | None = None, helpful: bool | None = None,
                        limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[FeedbackOut]:
    return await HelpFeedbackService(session).recent(topic_id, helpful, limit)
