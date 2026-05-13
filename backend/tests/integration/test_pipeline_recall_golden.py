"""Golden recall@10: 10 known categories → pipeline should put expected CNPJ in top-10."""

import csv
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.integrations.voyage import VoyageClient

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested, pytest.mark.voyage]

GOLDEN_CSV = Path(__file__).parent.parent / "fixtures" / "catalogo_golden.csv"
MIN_RECALL = 0.80


@pytest.mark.asyncio
async def test_pipeline_recall_golden(db_engine, two_tenants, tmp_path):
    """Upload 10-row catalog → pipeline → assert expected CNPJ in top-10 shortlist."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    rows = list(csv.DictReader(GOLDEN_CSV.open(encoding="utf-8")))
    assert len(rows) == 10

    # Build upload CSV with cluster names = categoria
    upload_csv = tmp_path / "golden_upload.csv"
    with upload_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["descricao_original", "agrupamento"])
        for r in rows:
            w.writerow([r["descricao"], r["categoria"]])

    tenant_id, _ = two_tenants
    upload_id = uuid.uuid4()
    storage = Path("/app/data/uploads") / str(tenant_id) / f"{upload_id}.csv"
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_bytes(upload_csv.read_bytes())

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'golden', :p, 'pending')"
            ),
            {"i": str(upload_id), "t": str(tenant_id), "p": str(storage)},
        )

    await processar_upload(
        upload_id=upload_id,
        tenant_id=tenant_id,
        csv_path=storage,
        session_factory=factory,
        voyage=VoyageClient(),
        curator=CuratorClient(),
    )

    # Check: for each category, expected CNPJ should appear in shortlist (top-10)
    hits = 0
    misses: list[tuple[str, str, list[str]]] = []
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        for r in rows:
            cluster = await session.execute(
                text(
                    "SELECT id, cnae FROM spend_clusters "
                    "WHERE upload_id = :u AND nome_cluster = :c"
                ),
                {"u": str(upload_id), "c": r["categoria"].lower()},
            )
            cluster_row = cluster.first()
            if not cluster_row:
                misses.append((r["categoria"], r["cnpj_esperado"], []))
                continue
            shortlist = await session.execute(
                text(
                    "SELECT cnpj_fornecedor FROM supplier_shortlists "
                    "WHERE cnae = :cnae AND tenant_id = :t "
                    "ORDER BY rank_estagio3 LIMIT 10"
                ),
                {"cnae": cluster_row.cnae, "t": str(tenant_id)},
            )
            cnpjs = [row.cnpj_fornecedor for row in shortlist.all()]
            if r["cnpj_esperado"] in cnpjs:
                hits += 1
            else:
                misses.append((r["categoria"], r["cnpj_esperado"], cnpjs[:5]))

    recall = hits / len(rows)
    if misses:
        report = "\n".join(
            f"  - {cat}: esperado {cnpj}, top-5 = {top}" for cat, cnpj, top in misses
        )
        print(f"\nMisses ({len(misses)}/{len(rows)}):\n{report}")
    assert recall >= MIN_RECALL, f"recall@10 = {recall:.2f}, esperado >= {MIN_RECALL}"
