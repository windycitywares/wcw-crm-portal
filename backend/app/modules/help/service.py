from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User

from .models import HelpFeedback
from .schemas import FeedbackIn, FeedbackOut, TopicSummary


class HelpFeedbackService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, data: FeedbackIn, actor: User) -> None:
        comment = " ".join((data.comment or "").split()) or None
        self.session.add(HelpFeedback(topic_id=data.topic_id, page=data.page.strip(), helpful=data.helpful,
                                      comment=comment, user_id=actor.id))
        await self.session.commit()

    async def summary(self) -> list[TopicSummary]:
        up = func.sum(case((HelpFeedback.helpful.is_(True), 1), else_=0))
        down = func.sum(case((HelpFeedback.helpful.is_(False), 1), else_=0))
        rows = await self.session.execute(
            select(HelpFeedback.topic_id, up, down, func.max(HelpFeedback.created_at))
            .group_by(HelpFeedback.topic_id)
            # The guides that people found unhelpful most come first: those are the ones to rewrite.
            .order_by(down.desc(), func.max(HelpFeedback.created_at).desc())
        )
        return [TopicSummary(topic_id=t, helpful=int(u or 0), not_helpful=int(d or 0), last_at=at) for t, u, d, at in rows]

    async def recent(self, topic_id: str | None, helpful: bool | None, limit: int) -> list[FeedbackOut]:
        stmt = (select(HelpFeedback, User.full_name).join(User, User.id == HelpFeedback.user_id, isouter=True)
                .order_by(HelpFeedback.created_at.desc(), HelpFeedback.id.desc()).limit(limit))
        if topic_id:
            stmt = stmt.where(HelpFeedback.topic_id == topic_id)
        if helpful is not None:
            stmt = stmt.where(HelpFeedback.helpful.is_(helpful))
        return [FeedbackOut(id=f.id, topic_id=f.topic_id, page=f.page, helpful=f.helpful, comment=f.comment,
                            user_name=name, created_at=f.created_at)
                for f, name in (await self.session.execute(stmt)).all()]
