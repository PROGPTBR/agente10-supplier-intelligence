import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_post_upload_returns_202_and_id(db_engine, two_tenants):
    from agente10 import main as main_module

    tenant_id, _ = two_tenants

    csv_bytes = b"descricao_original\nParafuso M8\n"
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/uploads",
            files={"file": ("c.csv", csv_bytes, "text/csv")},
            data={"nome_arquivo": "c.csv"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "upload_id" in body
    assert body["status"] == "pending"

    # Cleanup — delete child rows first to avoid FK violations from background task
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_linhas WHERE upload_id = :u"),
            {"u": body["upload_id"]},
        )
        await session.execute(
            text("DELETE FROM spend_clusters WHERE upload_id = :u"),
            {"u": body["upload_id"]},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": body["upload_id"]},
        )


@pytest.mark.asyncio
async def test_get_upload_returns_status(db_engine, two_tenants):
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
                "INSERT INTO spend_uploads "
                "(id, tenant_id, nome_arquivo, object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
