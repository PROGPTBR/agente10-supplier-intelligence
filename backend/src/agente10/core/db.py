import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agente10.core.config import Settings

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> None:
    """Initialize the global async engine and session factory."""
    global _engine, _sessionmaker
    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    """Dispose the global engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_engine():
    if _engine is None:
        raise RuntimeError("Engine not initialized — call init_engine() first.")
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("Sessionmaker not initialized.")
    async with _sessionmaker() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global session factory, auto-initializing from DATABASE_URL if needed.

    The normal path is that ``init_engine`` is called by the FastAPI lifespan.
    When the app is used via ``ASGITransport`` in tests (which skips the lifespan),
    we fall back to lazy init from the ``DATABASE_URL`` environment variable.
    """
    global _engine, _sessionmaker
    if _sessionmaker is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("Sessionmaker not initialized — call init_engine() first.")
        _engine = create_async_engine(db_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _sessionmaker
