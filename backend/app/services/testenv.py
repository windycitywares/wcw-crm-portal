"""Test mode: copy the live data into the `wcw_test` schema, switch the app between live and test, delete the copy.

Copying runs in one REPEATABLE READ transaction, so the copy is a consistent snapshot and the old copy is only
replaced once the new one is complete. Ids in the copy start 1,000,000 above live, so anything created during
testing can never be mistaken for a live record.

Every action is recorded in the *live* audit log (public.audit_log), whichever mode is on.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core import appmode
from app.core.exceptions import ConflictError, ValidationFailedError

SCHEMA = appmode.TEST_SCHEMA
BUILDING = f"{SCHEMA}_new"
ID_OFFSET = 1_000_000
_NEXTVAL = re.compile(r"nextval\('(?P<seq>[^']+)'::regclass\)")
_SAFE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def _ident(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise ValidationFailedError(f"Unexpected database object name {name!r}; copy stopped")
    return f'"{name}"'


async def _rows(conn: AsyncConnection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in (await conn.execute(text(sql), params)).mappings().all()]


async def _clone(conn: AsyncConnection) -> dict[str, Any]:
    await conn.execute(text("SET LOCAL search_path TO public"))
    await conn.execute(text("SET LOCAL lock_timeout = '20s'"))
    await conn.execute(text(f"DROP SCHEMA IF EXISTS {BUILDING} CASCADE"))
    await conn.execute(text(f"CREATE SCHEMA {BUILDING}"))

    tables = [r["tablename"] for r in await _rows(conn, "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")]
    sequences = await _rows(conn, """
        SELECT sequencename, start_value, min_value, max_value, increment_by, cycle, last_value
        FROM pg_sequences WHERE schemaname = 'public' ORDER BY sequencename
    """)
    defaults = await _rows(conn, """
        SELECT c.relname AS tbl, a.attname AS col, pg_get_expr(d.adbin, d.adrelid) AS expr
        FROM pg_attrdef d
        JOIN pg_class c ON c.oid = d.adrelid JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE n.nspname = 'public' AND pg_get_expr(d.adbin, d.adrelid) LIKE 'nextval(%'
    """)
    foreign_keys = await _rows(conn, """
        SELECT cl.relname AS tbl, con.conname AS name, pg_get_constraintdef(con.oid) AS def
        FROM pg_constraint con JOIN pg_class cl ON cl.oid = con.conrelid JOIN pg_namespace n ON n.oid = cl.relnamespace
        WHERE con.contype = 'f' AND n.nspname = 'public' ORDER BY cl.relname, con.conname
    """)

    for s in sequences:
        name = _ident(s["sequencename"])
        await conn.execute(text(
            f"CREATE SEQUENCE {BUILDING}.{name} INCREMENT BY {int(s['increment_by'])} MINVALUE {int(s['min_value'])} "
            f"MAXVALUE {int(s['max_value'])} START WITH {int(s['start_value'])} {'CYCLE' if s['cycle'] else 'NO CYCLE'}"
        ))
        base = max(int(s["last_value"] or 0), int(s["start_value"]))
        await conn.execute(text(f"SELECT setval('{BUILDING}.{s['sequencename']}', :v, true)"), {"v": base + ID_OFFSET})

    rows_copied = 0
    for t in tables:
        name = _ident(t)
        await conn.execute(text(f"CREATE TABLE {BUILDING}.{name} (LIKE public.{name} INCLUDING ALL)"))
        result = await conn.execute(text(f"INSERT INTO {BUILDING}.{name} SELECT * FROM public.{name}"))
        rows_copied += max(result.rowcount or 0, 0)

    for d in defaults:
        found = _NEXTVAL.fullmatch(d["expr"])
        if not found:
            continue
        seq = found["seq"].split(".")[-1].strip('"')
        await conn.execute(text(
            f"ALTER TABLE {BUILDING}.{_ident(d['tbl'])} ALTER COLUMN {_ident(d['col'])} SET DEFAULT nextval('{BUILDING}.{_ident(seq)}'::regclass)"
        ))

    # Emails that were waiting to go to real customers must not be sent from the copy.
    if "email_outbox" in tables:
        await conn.execute(text(
            f"UPDATE {BUILDING}.email_outbox SET status = 'skipped', last_error = 'Not sent: copied into the test data' WHERE status = 'queued'"
        ))

    # Foreign keys last (the data is already consistent). The definitions name tables without a schema, so resolve
    # them against the new copy.
    await conn.execute(text(f"SET LOCAL search_path TO {BUILDING}, public"))
    for fk in foreign_keys:
        await conn.execute(text(f"ALTER TABLE {BUILDING}.{_ident(fk['tbl'])} ADD CONSTRAINT {_ident(fk['name'])} {fk['def']}"))
    await conn.execute(text("SET LOCAL search_path TO public"))

    await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    await conn.execute(text(f"ALTER SCHEMA {BUILDING} RENAME TO {SCHEMA}"))
    await conn.execute(text("UPDATE public.app_mode SET test_synced_at = now() WHERE id = 1"))
    return {"tables": len(tables), "rows": rows_copied, "sequences": len(sequences)}


async def _audit(conn: AsyncConnection, user, action: str, summary: str, data: dict[str, Any] | None = None) -> None:
    await conn.execute(
        text("""
            INSERT INTO public.audit_log (actor_id, actor_email, action, entity_type, entity_id, changes)
            VALUES (:actor_id, :email, :action, 'environment', NULL, CAST(:data AS jsonb))
        """),
        {"actor_id": getattr(user, "id", None), "email": getattr(user, "email", None), "action": action,
         "data": json.dumps({"summary": summary, **(data or {})})},
    )


class TestEnvironment:
    """Every method opens its own connection and commits it, independent of the request's session."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def status(self) -> dict[str, Any]:
        async with self.engine.connect() as conn:
            await conn.execute(text("SET search_path TO public"))
            mode = (await _rows(conn, "SELECT mode, test_mail_to, test_synced_at, changed_at, changed_by_email FROM public.app_mode WHERE id = 1")) or [{}]
            row = mode[0]
            exists = bool((await conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :s)"), {"s": SCHEMA})).scalar_one())
            live_version = (await conn.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1"))).scalar_one_or_none()
            test_version, size = None, None
            if exists:
                if (await conn.execute(text(f"SELECT to_regclass('{SCHEMA}.alembic_version') IS NOT NULL"))).scalar_one():
                    test_version = (await conn.execute(text(f"SELECT version_num FROM {SCHEMA}.alembic_version LIMIT 1"))).scalar_one_or_none()
                size = (await conn.execute(text("""
                    SELECT COALESCE(sum(pg_total_relation_size(c.oid)), 0)::bigint FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = :s AND c.relkind = 'r'
                """), {"s": SCHEMA})).scalar_one()
        chosen = row.get("mode", appmode.LIVE)
        out_of_date = bool(exists and test_version != live_version)
        return {
            "mode": chosen,
            # Same rule as core/appmode.py: a copy behind the live migrations isn't used, so the app is on live data.
            "effective": appmode.TEST if chosen == appmode.TEST and exists and not out_of_date else appmode.LIVE,
            "test_exists": exists,
            "test_synced_at": row.get("test_synced_at"),
            "test_mail_to": row.get("test_mail_to"),
            "test_size_bytes": size,
            "out_of_date": out_of_date,
            "changed_at": row.get("changed_at"),
            "changed_by_email": row.get("changed_by_email"),
        }

    async def _set_mode(self, conn: AsyncConnection, mode: str, user) -> None:
        await conn.execute(
            text("UPDATE public.app_mode SET mode = :m, changed_at = now(), changed_by_email = :e WHERE id = 1"),
            {"m": mode, "e": getattr(user, "email", None)},
        )

    async def sync(self, user, *, switch_on: bool = False) -> dict[str, Any]:
        """Replace the test copy with a fresh copy of the live data (and switch to it when `switch_on`)."""
        started = time.monotonic()
        async with self.engine.connect() as raw:
            conn = await raw.execution_options(isolation_level="REPEATABLE READ")
            stats = await _clone(conn)
            if switch_on:
                await self._set_mode(conn, appmode.TEST, user)
            stats["seconds"] = round(time.monotonic() - started, 1)
            await _audit(conn, user, "environment.test_on" if switch_on else "environment.sync",
                         "Switched to test mode with a fresh copy of the live data" if switch_on else "Copied the live data into the test data again",
                         stats)
            await conn.commit()
        appmode.forget()
        return stats

    async def switch(self, mode: str, user) -> dict[str, Any]:
        if mode == appmode.TEST:
            return await self.sync(user, switch_on=True)  # turning test on always starts from a fresh copy
        async with self.engine.connect() as conn:
            await conn.execute(text("SET search_path TO public"))
            await self._set_mode(conn, appmode.LIVE, user)
            await _audit(conn, user, "environment.live", "Switched back to the live data")
            await conn.commit()
        appmode.forget()
        return {}

    async def delete_copy(self, user) -> None:
        state = await self.status()
        if state["mode"] == appmode.TEST:
            raise ConflictError("Switch to live before deleting the test data")
        async with self.engine.connect() as conn:
            await conn.execute(text("SET search_path TO public"))
            await conn.execute(text("SET lock_timeout = '20s'"))
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {BUILDING} CASCADE"))
            await conn.execute(text("UPDATE public.app_mode SET test_synced_at = NULL WHERE id = 1"))
            await _audit(conn, user, "environment.delete_test", "Deleted the test data")
            await conn.commit()
        appmode.forget()

    async def set_mail_to(self, email: str | None, user) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SET search_path TO public"))
            await conn.execute(text("UPDATE public.app_mode SET test_mail_to = :e WHERE id = 1"), {"e": email})
            await _audit(conn, user, "environment.mail_to", f"Test emails now go to {email}" if email else "Test emails are no longer sent")
            await conn.commit()
        appmode.forget()
