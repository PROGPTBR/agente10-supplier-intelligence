from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from agente10.curator.cnae_picker import CnaePick
from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.estagio1.pipeline import processar_upload

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested]


@pytest.mark.asyncio
async def test_two_tenants_data_isolated(db_engine, two_tenants, tmp_path, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    voyage = AsyncMock()
    voyage.embed_query.side_effect = lambda t: [0.1] * 1024
    voyage.embed_documents.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]
    curator = AsyncMock()

    async def fake_pick(name, cands):
        return CnaePick(cnae=cands[0].codigo, confidence=0.9, reasoning="x")

    async def fake_rerank(name, cands):
        return [
            RankedSupplier(cnpj=c.cnpj, rank=i + 1, reasoning="x") for i, c in enumerate(cands[:10])
        ]

    monkeypatch.setattr("agente10.estagio1.pipeline.pick_cnae", fake_pick)
    monkeypatch.setattr("agente10.estagio1.pipeline.rerank_top10", fake_rerank)

    tenant_a, tenant_b = two_tenants
    csv_text = "descricao_original,agrupamento\nParafuso,Parafusos\n"

    # Upload as tenant A
    upload_a = uuid.uuid4()
    storage_a = tmp_path / "a.csv"
    storage_a.write_text(csv_text, encoding="utf-8")
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_a)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads"
                " (id, tenant_id, nome_arquivo, object_storage_path, status)"
                " VALUES (:i, :t, 'a', :p, 'pending')"
            ),
            {"i": str(upload_a), "t": str(tenant_a), "p": str(storage_a)},
        )
    await processar_upload(
        upload_a,
        tenant_a,
        storage_a,
        factory,
        voyage,
        curator,
    )

    # Query as tenant B → MUST see 0 clusters from tenant A
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_b)},
        )
        count = await session.scalar(
            text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u"),
            {"u": str(upload_a)},
        )
    assert count == 0, "tenant B saw tenant A's clusters (RLS broken!)"
