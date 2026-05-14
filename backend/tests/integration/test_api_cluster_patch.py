# backend/tests/integration/test_api_cluster_patch.py
import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_patch_cluster_notas_does_not_trigger_regen(db_engine, two_tenants, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    regen_called = False

    async def fake_regen(*args, **kwargs):
        nonlocal regen_called
        regen_called = True

    monkeypatch.setattr("agente10.api.clusters.regenerate_shortlist_for_cluster", fake_regen)

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
                "nome_cluster, cnae, cnae_confianca, cnae_metodo) "
                "VALUES (:i, :t, :u, 'X', '4744001', 0.9, 'retrieval')"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/clusters/{cluster_id}",
            json={"notas_revisor": "ok", "revisado_humano": True},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["notas_revisor"] == "ok"
    assert resp.json()["revisado_humano"] is True
    assert not regen_called

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


@pytest.mark.asyncio
async def test_patch_cluster_rejects_invalid_cnae(db_engine, two_tenants):
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
                "nome_cluster, cnae, cnae_confianca, cnae_metodo) "
                "VALUES (:i, :t, :u, 'X', '4744001', 0.9, 'retrieval')"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/clusters/{cluster_id}",
            json={"cnae": "9999999"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 422
    assert "9999999" in resp.json()["detail"]

    # Confirm the cluster was NOT mutated
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        cnae_now = await session.scalar(
            text("SELECT cnae FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
    assert cnae_now == "4744001"

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


@pytest.mark.asyncio
async def test_patch_cluster_cnae_triggers_regen(db_engine, two_tenants, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    regen_called = False

    async def fake_regen(*args, **kwargs):
        nonlocal regen_called
        regen_called = True

    monkeypatch.setattr("agente10.api.clusters.regenerate_shortlist_for_cluster", fake_regen)

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
                "nome_cluster, cnae, cnae_confianca, cnae_metodo, shortlist_gerada) "
                "VALUES (:i, :t, :u, 'X', '4744001', 0.9, 'retrieval', true)"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/clusters/{cluster_id}",
            json={"cnae": "4673700"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["cnae"] == "4673700"
    await asyncio.sleep(0.1)
    assert regen_called

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        flag = await session.scalar(
            text("SELECT shortlist_gerada FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
    assert flag is False
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
