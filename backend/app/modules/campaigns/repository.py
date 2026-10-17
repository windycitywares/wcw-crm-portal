"""Queries for campaigns: search the templates, and ask the suppression list about an address."""

from __future__ import annotations

from sqlalchemy import Select, func, or_

from app.shared.repository import BaseRepository

from .models import EmailTemplate, Suppression


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class EmailTemplateRepository(BaseRepository[EmailTemplate]):
    model = EmailTemplate

    def search(self, *, q: str | None = None) -> Select[tuple[EmailTemplate]]:
        stmt = self.query()
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(
                func.lower(EmailTemplate.name).like(p), func.lower(EmailTemplate.subject).like(p),
            ))
        return stmt.order_by(func.lower(EmailTemplate.name), EmailTemplate.id)

    async def by_name(self, name: str) -> EmailTemplate | None:
        """Used to refuse two templates with the same name — a campaign is picked by name."""
        rows = await self.list(self.query().where(func.lower(EmailTemplate.name) == name.strip().lower())
                               .order_by(EmailTemplate.id).limit(1))
        return rows[0] if rows else None


class SuppressionRepository(BaseRepository[Suppression]):
    model = Suppression

    def search(self, *, reason: str | None = None, q: str | None = None) -> Select[tuple[Suppression]]:
        stmt = self.query()
        if reason:
            stmt = stmt.where(Suppression.reason == reason)
        if q:
            p = f"%{escape_like(q.strip().lower())}%"
            stmt = stmt.where(or_(Suppression.email.like(p), func.lower(Suppression.note).like(p)))
        return stmt.order_by(Suppression.created_at.desc(), Suppression.id.desc())

    async def by_email(self, email: str, *, include_deleted: bool = False) -> Suppression | None:
        stmt = (self.query(include_deleted=include_deleted)
                .where(func.lower(Suppression.email) == (email or "").strip().lower())
                .order_by(Suppression.id).limit(1))
        rows = await self.list(stmt)
        return rows[0] if rows else None

    async def suppressed_of(self, emails: list[str]) -> set[str]:
        """Which of these addresses are on the list (lower-cased, for a batch of recipients)."""
        wanted = sorted({(e or "").strip().lower() for e in emails if e})
        if not wanted:
            return set()
        stmt = self.query().where(func.lower(Suppression.email).in_(wanted))
        return {row.email for row in await self.list(stmt)}
