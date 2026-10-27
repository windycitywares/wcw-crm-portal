"""The bell and live updates (as in the shop admin: wcw-shop-portal services/notifications.py and admin_live).

Bell: recent activity across the CRM, each item linking to where it's handled. Nothing is stored per event: the feed
is read from the tables that already hold the activity (subscribers, tickets and customer replies, customers from the
shop, leads, tasks someone gave you, won deals). Each person only sees the kinds their role can act on, and anything
newer than `users.notifications_seen_at` counts as unread.

Live: every change the CRM makes is already written to the audit log, so "what changed since id N" is read from it
(only for record types the person may see). Lists use it to show "3 new · Refresh" without reloading by themselves.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, has_permission
from app.shared.time import utcnow

WINDOW_DAYS = 30
MAX_UNREAD = 99

# Every source returns: type, ref (id), at, title, detail, extra, state.
SOURCES: dict[str, tuple[Permission, str]] = {
    "subscriber": (Permission.CUSTOMERS_VIEW, """
        SELECT 'subscriber' AS type, c.id::text AS ref, c.subscribed_at AS at, c.email::text AS title,
               c.subscribe_source::text AS detail, NULL::text AS extra, NULL::text AS state
        FROM contacts c WHERE c.deleted_at IS NULL AND c.subscribed_at >= :since AND c.unsubscribed_at IS NULL"""),
    "ticket": (Permission.TICKETS_VIEW, """
        SELECT 'ticket', t.id::text, t.created_at, COALESCE(t.number, '')::text, t.subject::text, t.channel::text, t.status::text
        FROM tickets t WHERE t.deleted_at IS NULL AND t.created_at >= :since"""),
    "reply": (Permission.TICKETS_VIEW, """
        SELECT 'reply', t.id::text, m.created_at, COALESCE(t.number, '')::text, t.subject::text, m.from_email::text, t.status::text
        FROM ticket_messages m JOIN tickets t ON t.id = m.ticket_id
        WHERE m.direction = 'inbound' AND t.deleted_at IS NULL AND m.created_at >= :since
          AND m.created_at > t.created_at + interval '1 minute'"""),
    "customer": (Permission.CUSTOMERS_VIEW, """
        SELECT 'customer', c.id::text, c.created_at, COALESCE(NULLIF(trim(c.first_name || ' ' || c.last_name), ''), c.email, 'Customer')::text,
               c.email::text, NULL::text, NULL::text
        FROM customers c WHERE c.deleted_at IS NULL AND c.created_by IS NULL AND c.created_at >= :since"""),
    "lead": (Permission.SALES_VIEW, """
        SELECT 'lead', l.id::text, l.created_at,
               COALESCE(NULLIF(trim(COALESCE(l.first_name, '') || ' ' || COALESCE(l.last_name, '')), ''), l.company, l.email, 'Lead')::text,
               l.email::text, NULL::text, l.status::text
        FROM leads l WHERE l.deleted_at IS NULL AND l.created_at >= :since"""),
    "task": (Permission.TASKS_VIEW, """
        SELECT 'task', k.id::text, k.created_at, k.title::text, u.full_name::text, NULL::text, k.status::text
        FROM tasks k LEFT JOIN users u ON u.id = k.created_by
        WHERE k.deleted_at IS NULL AND k.owner_id = :me AND k.created_by IS DISTINCT FROM :me AND k.created_at >= :since"""),
    "deal_won": (Permission.SALES_VIEW, """
        SELECT 'deal_won', d.id::text, d.closed_at, d.title::text, NULL::text, d.value::text, d.status::text
        FROM deals d WHERE d.deleted_at IS NULL AND d.status = 'won' AND d.closed_at >= :since"""),
}

CHANNELS = {"email": "email", "shop_form": "the shop's contact form", "phone": "phone", "chat": "live chat", "etsy": "Etsy",
            "manual": "added by staff"}


def allowed_sources(user) -> list[str]:
    return [name for name, (perm, _) in SOURCES.items() if has_permission(user.role, perm)]


def _money(value: str | None) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except ValueError:
        return ""


def present(row: dict[str, Any]) -> dict[str, Any]:
    """A raw row → what the bell shows: a sentence, a second line and where clicking goes."""
    t, ref, title, detail, extra, state = row["type"], row["ref"], row["title"], row["detail"], row["extra"], row["state"]
    if t == "subscriber":
        where = {"site": "the website form", "checkout": "checkout", "account": "their account"}.get(detail or "", detail or "the shop")
        return {"title": "New newsletter subscriber", "detail": f"{title} · from {where}", "href": f"/subscribers?q={quote(title)}", "tone": "info"}
    if t == "ticket":
        return {"title": f"New ticket {title}", "detail": f"{detail} · via {CHANNELS.get(extra or '', extra or 'the CRM')}",
                "href": f"/tickets/{ref}", "tone": "accent" if state == "new" else "neutral"}
    if t == "reply":
        return {"title": f"Customer replied on {title}", "detail": f"{detail}{' · ' + extra if extra else ''}",
                "href": f"/tickets/{ref}", "tone": "accent"}
    if t == "customer":
        return {"title": "New customer from the shop", "detail": title if title == (detail or title) else f"{title} · {detail}",
                "href": f"/customers/{ref}", "tone": "info"}
    if t == "lead":
        return {"title": f"New lead: {title}", "detail": detail or "", "href": "/leads", "tone": "info"}
    if t == "task":
        return {"title": f"Task for you: {title}", "detail": f"From {detail}" if detail else "", "href": f"/tasks?task={ref}",
                "tone": "warning" if state == "open" else "neutral"}
    return {"title": f"Deal won: {title}", "detail": _money(extra), "href": "/sales", "tone": "success"}


# Live updates: which audit-log record types a person may hear about.
LIVE_TYPES: dict[str, Permission] = {
    "customer": Permission.CUSTOMERS_VIEW, "contact": Permission.CUSTOMERS_VIEW, "ticket": Permission.TICKETS_VIEW,
    "task": Permission.TASKS_VIEW, "lead": Permission.SALES_VIEW, "deal": Permission.SALES_VIEW,
    "supplier": Permission.SUPPLIERS_VIEW, "campaign": Permission.CAMPAIGNS_VIEW,
}


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _union(self, user, kinds: list[str] | None) -> str | None:
        names = [n for n in allowed_sources(user) if not kinds or n in kinds]
        cols = "(type, ref, at, title, detail, extra, state)"
        return " UNION ALL ".join(f"SELECT * FROM ({SOURCES[n][1]}) AS s_{n}{cols}" for n in names) if names else None

    async def feed(self, user, limit: int = 20, kinds: list[str] | None = None, before: datetime | None = None) -> dict[str, Any]:
        since = utcnow() - timedelta(days=WINDOW_DAYS)
        seen = user.notifications_seen_at
        union = self._union(user, kinds)
        if union is None:
            return {"items": [], "unread": 0, "seen_at": seen, "kinds": []}
        cond = "WHERE at < :before" if before else ""
        params: dict[str, Any] = {"since": since, "me": user.id, "n": limit}
        if before:
            params["before"] = before
        rows = (await self.session.execute(
            text(f"SELECT * FROM ({union}) AS feed {cond} ORDER BY at DESC, ref DESC LIMIT :n"), params)).mappings().all()
        unread = (await self.session.execute(
            text(f"SELECT count(*) FROM ({self._union(user, None)}) AS feed WHERE at > :seen"),
            {"since": since, "me": user.id, "seen": seen or since})).scalar_one()
        items = [{"id": f"{r['type']}:{r['ref']}", "type": r["type"], "at": r["at"],
                  "unread": seen is None or r["at"] > seen, **present(dict(r))} for r in rows]
        return {"items": items, "unread": min(int(unread), MAX_UNREAD), "seen_at": seen, "kinds": allowed_sources(user)}

    async def live(self, user, after_id: int | None, limit: int = 200) -> dict[str, Any]:
        """Changes after audit id `after_id` to record types this person may see. With no `after_id`, just the
        current position (a page starts listening from now)."""
        if after_id is None:
            last = (await self.session.execute(text("SELECT COALESCE(max(id), 0) FROM audit_log"))).scalar_one()
            return {"events": [], "last_id": int(last)}
        types = [t for t, perm in LIVE_TYPES.items() if has_permission(user.role, perm)]
        rows = (await self.session.execute(text("""
            SELECT a.id, a.action, a.entity_type, a.entity_id, a.actor_id, u.full_name AS actor_name, a.at
            FROM audit_log a LEFT JOIN users u ON u.id = a.actor_id
            WHERE a.id > :after ORDER BY a.id LIMIT :n"""), {"after": after_id, "n": limit})).mappings().all()
        last = int(rows[-1]["id"]) if rows else after_id
        events = [{"id": int(r["id"]), "kind": r["action"], "entity_type": r["entity_type"], "ref_id": r["entity_id"],
                   "actor_id": r["actor_id"], "actor_name": r["actor_name"], "at": r["at"]}
                  for r in rows if r["entity_type"] in types]
        return {"events": events, "last_id": last}
