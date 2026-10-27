"""Live / Test switch: which copy of the data the whole app (API, scheduled jobs) works on.

The live data is the `public` schema. Test mode works on a copy in the `wcw_test` schema of the same
database (HostItBro can't create databases from the app, and a schema needs no extension). The choice is
stored in `public.app_mode` and applied on every database connection the app takes from the pool by
setting `search_path`, so every query — ORM and raw SQL alike — reads and writes the chosen copy. Enum
types and anything else that isn't copied are still found in `public`.

The mode is cached per process for a few seconds, so a switch reaches every worker process within that time.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)

TEST_SCHEMA = "wcw_test"
LIVE, TEST = "live", "test"
CACHE_SECONDS = 5.0

_STATE_SQL = f"""
SELECT m.mode, m.test_mail_to, m.test_synced_at, m.test_login_emails,
       EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = '{TEST_SCHEMA}') AS test_exists
FROM public.app_mode m WHERE m.id = 1
"""


def login_emails(raw: str | None) -> tuple[str, ...]:
    """The stored list (one comma-separated string) as addresses; order kept, duplicates dropped."""
    found = (part.strip().lower() for part in (raw or "").replace("\n", ",").replace(";", ",").split(","))
    return tuple(dict.fromkeys(part for part in found if part))


@dataclass(frozen=True)
class ModeState:
    chosen: str = LIVE  # what the admin selected
    test_exists: bool = False
    test_mail_to: str | None = None
    test_synced_at: datetime | None = None
    # Staff who may sign in on the copy. In the CRM all staff may (they're the testers).
    login_emails: tuple[str, ...] = ()
    # The copy is on the same migration as the live data. A copy left behind by a deploy (new columns the code now
    # reads) would break every request, sign-in included, so the app stays on live data until it catches up.
    test_current: bool = True

    @property
    def effective(self) -> str:
        """Test only works when the copy exists and is up to date; otherwise the app stays on live data."""
        return TEST if self.chosen == TEST and self.test_exists and self.test_current else LIVE

    @property
    def is_test(self) -> bool:
        return self.effective == TEST

    @property
    def search_path(self) -> str:
        return f"{TEST_SCHEMA}, public" if self.is_test else "public"


_state = ModeState()
_loaded_at = 0.0
_override: ContextVar[ModeState | None] = ContextVar("wcw_mode_override", default=None)


def current() -> ModeState:
    """The mode for this piece of work: an override (see `use`) or the last known mode in this process."""
    return _override.get() or _state


def is_test() -> bool:
    return current().is_test


@contextmanager
def use(target: str) -> Iterator[ModeState]:
    """Work on one copy whatever the CRM is switched to (webhooks: live events update live data)."""
    state = ModeState(chosen=target, test_exists=target == TEST, test_mail_to=_state.test_mail_to,
                      test_synced_at=_state.test_synced_at, login_emails=_state.login_emails)
    token = _override.set(state)
    try:
        yield state
    finally:
        _override.reset(token)


def remember(state: ModeState) -> None:
    global _state, _loaded_at
    _state, _loaded_at = state, time.monotonic()


def forget() -> None:
    """Make the next connection re-read the mode (after a switch in this process)."""
    global _loaded_at
    _loaded_at = 0.0


_VERSIONS_SQL = f"""
SELECT (SELECT string_agg(version_num, ',' ORDER BY version_num) FROM {TEST_SCHEMA}.alembic_version) AS test,
       (SELECT string_agg(version_num, ',' ORDER BY version_num) FROM public.alembic_version) AS live
"""


def _copy_is_current(dbapi_connection) -> bool:
    try:
        row = dbapi_connection.run_async(lambda conn: conn.fetchrow(_VERSIONS_SQL))
    except Exception:  # no version table in the copy: treat it as behind
        log.warning("test copy has no migration version; staying on live data")
        return False
    current = row is not None and row["test"] == row["live"]
    if not current:
        log.warning("test copy is on migration %s, live is on %s; staying on live data", row["test"], row["live"])
    return current


def _row_to_state(row, test_current: bool = True) -> ModeState:
    if row is None:
        return ModeState()
    return ModeState(
        test_current=test_current,
        chosen=row["mode"],
        test_exists=bool(row["test_exists"]),
        test_mail_to=row["test_mail_to"],
        test_synced_at=row["test_synced_at"],
        login_emails=login_emails(row["test_login_emails"]),
    )


def on_checkout(dbapi_connection) -> None:
    """Pool 'checkout' hook: refresh the cached mode if it is old, then point the connection at the right schema."""
    if time.monotonic() - _loaded_at > CACHE_SECONDS:
        try:
            row = dbapi_connection.run_async(lambda conn: conn.fetchrow(_STATE_SQL))
            current = True
            if row is not None and row["mode"] == TEST and row["test_exists"]:
                current = _copy_is_current(dbapi_connection)
            remember(_row_to_state(row, current))
        except Exception:  # app_mode not migrated yet, or a hiccup: stay on (or fall back to) live data
            log.debug("app_mode not readable; using live data", exc_info=True)
            remember(ModeState())
    path = current().search_path
    dbapi_connection.run_async(lambda conn: conn.execute(f"SET search_path TO {path}"))


def install(engine) -> None:
    """Attach the hook to the app's engine (not Alembic's: migrations always run on the live schema)."""
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "checkout")
    def _checkout(dbapi_connection, connection_record, connection_proxy):  # noqa: ARG001
        on_checkout(dbapi_connection)
