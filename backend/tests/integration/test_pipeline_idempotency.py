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
async def test_pipeline_idempotent_on_rerun(db_engine, two_tenants, tmp_path, monkeypatch):
    """Running the same upload twice must produce identical state, no duplicates."""
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

    tenant_id, _ = two_tenants
    upload_id = uuid.uuid4()
    storage = tmp_path / "c.csv"
    storage.write_text(
        "descricao_original,agrupamento\nParafuso,Parafusos\nGerador,Geradores\n",
        encoding="utf-8",
    )
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads"
                " (id, tenant_id, nome_arquivo, object_storage_path, status)"
                " VALUES (:i, :t, 'c', :p, 'pending')"
            ),
            {"i": str(upload_id), "t": str(tenant_id), "p": str(storage)},
        )

    await processar_upload(upload_id, tenant_id, storage, factory, voyage, curator)

    async def counts() -> tuple[int, int, int]:
        async with factory() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            linhas = await session.scalar(
                text("SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            clusters = await session.scalar(
                text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            shortlists = await session.scalar(
                text(
                    "SELECT COUNT(*) FROM supplier_shortlists s "
                    "JOIN spend_clusters c ON c.cnae = s.cnae "
                    "WHERE c.upload_id = :u"
                ),
                {"u": str(upload_id)},
            )
        return int(linhas), int(clusters), int(shortlists)

    before = await counts()

    # Re-run the pipeline → should be a no-op (idempotent)
    await processar_upload(upload_id, tenant_id, storage, factory, voyage, curator)

    after = await counts()
    assert before == after, f"non-idempotent: before={before} after={after}"
