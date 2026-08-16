"""SQLAlchemy database engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from nexus.core.config import get_settings

settings = get_settings()

# SQLite doesn't support pool_size / max_overflow
# In-memory SQLite needs StaticPool to share the DB across connections
_engine_kwargs: dict = {
    "echo": settings.api_debug,
    "pool_pre_ping": True,
}
if "sqlite" in settings.database_url:
    from sqlalchemy.pool import StaticPool

    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all models."""


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """FastAPI dependency — yields an async DB session.

    If the database is unavailable, yields None (graceful degradation).
    Routes that need persistence should handle None gracefully.
    """
    try:
        session = async_session_factory()
    except Exception:
        # DB engine creation failed — degrade gracefully
        yield None
        return

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
