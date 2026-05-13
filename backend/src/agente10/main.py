from contextlib import asynccontextmanager

import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from agente10.api.uploads import router as uploads_router
from agente10.core.config import get_settings
from agente10.core.db import dispose_engine, get_engine, init_engine

_redis_client: redis_asyncio.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine(settings)

    global _redis_client
    _redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)

    yield

    if _redis_client is not None:
        await _redis_client.aclose()
    await dispose_engine()


app = FastAPI(title="Agente 10", version="0.1.0", lifespan=lifespan)
app.include_router(uploads_router)


async def _db_ping() -> str:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


async def _redis_ping() -> str:
    try:
        if _redis_client is None:
            return "error: not initialized"
        pong = await _redis_client.ping()
        return "ok" if pong else "error: no pong"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


@app.get("/health")
async def health() -> JSONResponse:
    db = await _db_ping()
    rd = await _redis_ping()
    ok = db == "ok" and rd == "ok"
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "error", "db": db, "redis": rd},
    )
