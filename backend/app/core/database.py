"""Async database engine and session factory."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def _build_engine():
    settings = get_settings()
    kwargs: dict = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,
        "connect_args": {"timeout": settings.db_connect_timeout},
    }
    if settings.db_use_null_pool:
        # Passenger may spawn/kill processes freely; don't hold pooled connections.
        kwargs["poolclass"] = NullPool
    return create_async_engine(settings.database_url, **kwargs)


engine = _build_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
