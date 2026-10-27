import asyncio
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.modules import load_modules
from app.shared.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_modules()  # imports every installed module's models so autogenerate sees all tables
target_metadata = Base.metadata
DATABASE_URL = get_settings().database_url

# MIGRATE_SCHEMA=wcw_test alembic upgrade head — bring the Test mode copy (Settings → Test mode) to the same
# migration as the live data; deploy/update-api.sh does it after migrating live. Default: the live schema.
SCHEMA = os.environ.get("MIGRATE_SCHEMA") or None
if SCHEMA is not None and not re.fullmatch(r"[a-z_][a-z0-9_]*", SCHEMA):
    raise SystemExit(f"MIGRATE_SCHEMA must be a plain schema name, got {SCHEMA!r}")


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    if SCHEMA:
        # New tables and columns land in the copy; enum types and the like are still found in public.
        connection.execute(text(f"SET search_path TO {SCHEMA}, public"))
        connection.commit()
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                      version_table_schema=SCHEMA)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
