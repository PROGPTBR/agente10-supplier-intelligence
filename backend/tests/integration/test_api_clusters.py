import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_cluster(
    factory,
    tenant_id,
    *,
    cnae: str | None = "4744001",
    metodo: str | None = "retrieval",
    revisado: bool = False,
):
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
                "INSERT INTO spend_clusters "
                "(id, tenant_id, upload_id, nome_cluster, cnae, cnae_confianca, "
                "cnae_metodo, num_linhas, revisado_humano) "
                "VALUES (:i, :t, :u, 'Parafusos', :cnae, 0.92, :m, 6, :r)"
            ),
            {
                "i": str(cluster_id),
                "t": str(tenant_id),
                "u": str(upload_id),
                "cnae": cnae,
                "m": metodo,
                "r": revisado,
            },
        )
        for n in range(3):
            await session.execute(
                text(
                    "INSERT INTO spend_linhas (tenant_id, upload_id, "
                    "descricao_original, cluster_id) "
                    "VALUES (:t, :u, :d, :c)"
                ),
                {
                    "t": str(tenant_id),
                    "u": str(upload_id),
                    "d": f"Parafuso M{n}",
                    "c": str(cluster_id),
                },
            )
    return upload_id, cluster_id


async def _cleanup(factory, tenant_id, upload_id):
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        for table in ("spend_linhas", "spend_clusters"):
            await session.execute(
                text(f"DELETE FROM {table} WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )


@pytest.mark.asyncio
async def test_list_clusters_for_upload(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, cluster_id = await _seed_cluster(factory, tenant_id)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}/clusters",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["nome_cluster"] == "Parafusos"
    assert body[0]["cnae"] == "4744001"
    assert body[0]["num_linhas"] == 6
    await _cleanup(factory, tenant_id, upload_id)


@pytest.mark.asyncio
async def test_list_clusters_filters_by_metodo(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, _ = await _seed_cluster(factory, tenant_id, metodo="retrieval")

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}/clusters?metodo=curator",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json() == []
    await _cleanup(factory, tenant_id, upload_id)


@pytest.mark.asyncio
async def test_get_cluster_detail_includes_sample_linhas(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, cluster_id = await _seed_cluster(factory, tenant_id)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/clusters/{cluster_id}",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome_cluster"] == "Parafusos"
    assert len(body["sample_linhas"]) == 3
    assert body["sample_linhas"][0].startswith("Parafuso")
    await _cleanup(factory, tenant_id, upload_id)


@pytest.mark.asyncio
async def test_get_shortlist_returns_empty_when_no_entries(db_engine, two_tenants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agente10 import main as main_module

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, cluster_id = await _seed_cluster(factory, tenant_id)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/clusters/{cluster_id}/shortlist",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json() == []
    await _cleanup(factory, tenant_id, upload_id)
