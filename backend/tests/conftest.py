"""Shared pytest fixtures.

- ``client`` (unit): ASGI client with mocked /health pingers.
- ``db_engine``, ``db_session``, ``two_tenants`` (integration): real Postgres
  via the docker-compose service. Skipped unless ``-m integration`` is used.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# --- Unit-test fixture (no DB) -----------------------------------------------


@pytest.fixture
async def client(monkeypatch):
    """ASGI client with mocked DB/Redis dependencies."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@x/x")
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("ENV", "local")

    from agente10 import main as main_module

    async def _ok_db_ping() -> str:
        return "ok"

    async def _ok_redis_ping() -> str:
        return "ok"

    monkeypatch.setattr(main_module, "_db_ping", _ok_db_ping)
    monkeypatch.setattr(main_module, "_redis_ping", _ok_redis_ping)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Integration fixtures (real Postgres) ------------------------------------


def _integration_db_url() -> str:
    """Resolve the URL for the integration Postgres.

    Default uses the non-superuser ``agente10_app`` role + ``postgres`` hostname
    (docker service). Override via ``INTEGRATION_DATABASE_URL`` for other layouts
    (e.g., CI runners that connect over localhost).
    """
    return os.getenv(
        "INTEGRATION_DATABASE_URL",
        "postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10",
    )


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Session-scoped engine pointed at the real test Postgres."""
    engine = create_async_engine(_integration_db_url(), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Function-scoped session, rolled back at the end of every test."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def two_tenants(db_engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """Create two tenants for isolation tests; clean up at end.

    Inserts directly via a session that is *outside* the per-test rollback fixture,
    because RLS tests need the tenant rows to be visible across their own sessions.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with factory() as session, session.begin():
        await session.execute(
            text("INSERT INTO tenants (id, nome) VALUES (:a, 'tenant_a'), (:b, 'tenant_b')"),
            {"a": str(tenant_a), "b": str(tenant_b)},
        )

    yield (tenant_a, tenant_b)

    # Cleanup. RLS tables first (FK), then tenants. Bypass RLS by setting current
    # tenant; we just want everything related to A or B gone.
    async with factory() as session, session.begin():
        for tenant in (tenant_a, tenant_b):
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant)},
            )
            for table in (
                "supplier_shortlists",
                "concentracao_categorias",
                "spend_linhas",
                "spend_clusters",
                "spend_uploads",
            ):
                await session.execute(text(f"DELETE FROM {table}"))
        await session.execute(
            text("DELETE FROM tenants WHERE id IN (:a, :b)"),
            {"a": str(tenant_a), "b": str(tenant_b)},
        )


# --- Voyage marker handling --------------------------------------------------


def pytest_collection_modifyitems(config, items):
    """Skip tests marked ``voyage`` when ``VOYAGE_API_KEY`` is not set."""
    if os.environ.get("VOYAGE_API_KEY"):
        return
    skip_voyage = pytest.mark.skip(reason="VOYAGE_API_KEY not set")
    for item in items:
        if "voyage" in item.keywords:
            item.add_marker(skip_voyage)


@pytest.fixture(scope="session")
async def voyage_client():
    """Session-scoped Voyage client; tests marked ``voyage`` are skipped without API key."""
    from agente10.integrations.voyage import VoyageClient

    return VoyageClient()
