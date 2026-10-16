"""Run every installed module's background jobs once. Cron calls this every minute (deploy/run-jobs.sh).

    python -m app.workers.run_jobs                # all jobs
    python -m app.workers.run_jobs --only outbox  # some jobs

Two runs never overlap (PostgreSQL advisory lock). Prints a line only when a job did something or failed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime

from sqlalchemy import text

from app.core.database import SessionFactory, engine
from app.modules import load_modules

LOCK_ID = 7_235_001  # any constant unique to this app


def _log(line: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} jobs: {line}", flush=True)


async def run(only: set[str] | None = None) -> int:
    modules = load_modules()
    for mod in modules:  # e.g. the mail module installs the outbox sender
        for hook in mod.on_startup:
            hook()
    failures = 0
    async with engine.connect() as lock_conn:
        got = (await lock_conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_ID})).scalar()
        if not got:
            return 0  # another run is busy
        try:
            for mod in modules:
                for name, fn in mod.jobs:
                    if only and name not in only:
                        continue
                    try:
                        async with SessionFactory() as session:
                            result = await fn(session)
                        if result:
                            _log(f"{name}: {result}")
                    except Exception as exc:  # noqa: BLE001 - one failing job mustn't stop the others
                        failures += 1
                        _log(f"{name}: FAILED {type(exc).__name__}: {exc}")
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_ID})
    await engine.dispose()
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="job names to run")
    args = parser.parse_args()
    sys.exit(1 if asyncio.run(run(set(args.only) if args.only else None)) else 0)


if __name__ == "__main__":
    main()
