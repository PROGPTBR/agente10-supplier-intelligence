from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from agente10.curator.cnae_picker import CnaePick
from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.estagio1.pipeline import processar_upload

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested]


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> Path:
    csv_text = (
        "descricao_original,agrupamento\n"
        "Parafuso M8,Parafusos\n"
        "Parafuso M10,Parafusos\n"
        "Gerador 5kVA,Geradores\n"
        "Cabo elétrico 2.5mm\n"
        "Cabo elétrico 4mm\n"
    )
    p = tmp_path / "catalogo.csv"
    p.write_text(csv_text, encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_e2e_pipeline_populates_all_tables(
    db_engine, two_tenants, synthetic_csv, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    voyage = AsyncMock()
    voyage.embed_query.side_effect = lambda t: [0.1] * 1024  # 1024-d
    voyage.embed_documents.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]

    curator = AsyncMock()

    # CNAE picker returns the first candidate's code (whatever it is)
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

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, object_storage_path) "
                "VALUES (:i, :t, :n, :p)"
            ),
            {
                "i": str(upload_id),
                "t": str(tenant_id),
                "n": "catalogo.csv",
                "p": str(synthetic_csv),
            },
        )

    await processar_upload(
        upload_id=upload_id,
        tenant_id=tenant_id,
        csv_path=synthetic_csv,
        session_factory=factory,
        voyage=voyage,
        curator=curator,
    )

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        status = await session.scalar(
            text("SELECT status FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
        linhas = await session.scalar(
            text("SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u"),
            {"u": str(upload_id)},
        )
        clusters = await session.scalar(
            text(
                "SELECT COUNT(*) FROM spend_clusters " "WHERE upload_id = :u AND cnae IS NOT NULL"
            ),
            {"u": str(upload_id)},
        )
        shortlist = await session.scalar(
            text(
                "SELECT COUNT(*) FROM supplier_shortlists s "
                "JOIN spend_clusters c ON c.cnae = s.cnae "
                "WHERE c.upload_id = :u AND c.tenant_id = :t"
            ),
            {"u": str(upload_id), "t": str(tenant_id)},
        )
        denormed = await session.scalar(
            text("SELECT COUNT(*) FROM spend_linhas " "WHERE upload_id = :u AND cnae IS NOT NULL"),
            {"u": str(upload_id)},
        )

    assert status == "done"
    assert linhas == 5
    assert clusters >= 2  # Parafusos, Geradores (Cabo elétrico may merge or split)
    assert shortlist >= 10
    assert denormed == 5
