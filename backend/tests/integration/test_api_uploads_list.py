"""Integration tests for GET /api/v1/uploads (list) and progresso_pct field."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_list_uploads_returns_ordered_by_data_upload_desc(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    older_id = uuid.uuid4()
    newer_id = uuid.uuid4()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status, data_upload) "
                "VALUES (:i, :t, :n, '/tmp/x', 'done', NOW() - INTERVAL '1 hour')"
            ),
            {"i": str(older_id), "t": str(tenant_id), "n": "older.csv"},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status, linhas_total, linhas_classificadas) "
                "VALUES (:i, :t, :n, '/tmp/y', 'processing', 100, 50)"
            ),
            {"i": str(newer_id), "t": str(tenant_id), "n": "newer.csv"},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/uploads", headers={"X-Tenant-ID": str(tenant_id)})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["upload_id"] == str(newer_id)
    assert body[0]["progresso_pct"] == 50.0
    assert body[1]["upload_id"] == str(older_id)

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id IN (:a, :b)"),
            {"a": str(older_id), "b": str(newer_id)},
        )


@pytest.mark.asyncio
async def test_get_upload_includes_progresso_pct(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status, linhas_total, linhas_classificadas) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'processing', 200, 60)"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/uploads/{upload_id}", headers={"X-Tenant-ID": str(tenant_id)})
    assert resp.status_code == 200
    assert resp.json()["progresso_pct"] == 30.0

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"), {"u": str(upload_id)}
        )
