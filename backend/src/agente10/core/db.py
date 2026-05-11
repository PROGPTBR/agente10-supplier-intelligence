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
