import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_dashboard_stats_counts(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()
    cluster_id = uuid.uuid4()

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_clusters (id, tenant_id, upload_id, "
                "nome_cluster, cnae, cnae_metodo, revisado_humano) "
                "VALUES (:i, :t, :u, 'X', '4744001', 'retrieval', true)"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/dashboard/stats",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["uploads_total"] >= 1
    assert body["uploads_done"] >= 1
    assert body["clusters_total"] >= 1
    assert body["clusters_revised"] >= 1
    assert body["clusters_by_metodo"].get("retrieval", 0) >= 1
    assert any(u["upload_id"] == str(upload_id) for u in body["recent_uploads"])

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
