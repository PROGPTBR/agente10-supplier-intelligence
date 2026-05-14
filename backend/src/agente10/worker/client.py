"""Singleton arq Redis pool for enqueueing jobs from the API process."""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis

from agente10.worker.tasks import _redis_settings

_pool: ArqRedis | None = None


async def init_pool() -> None:
    """Initialize the arq pool. Call once in FastAPI lifespan startup."""
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def get_pool() -> ArqRedis:
    """Return the live pool. Raises if init_pool wasn't called."""
    if _pool is None:
        raise RuntimeError("arq pool not initialized — check FastAPI lifespan")
    return _pool
