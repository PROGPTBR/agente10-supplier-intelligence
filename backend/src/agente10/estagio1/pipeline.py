"""Estágio 1 + Estágio 3 orchestrator.

Drives spend_uploads.status: pending → processing → done|failed.
Each stage commits independently for idempotent re-run.
"""

from __future__ import annotations

import json
import logging
import traceback
from functools import partial
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agente10.cnae.retrieval import top_k_cnaes_hybrid
from agente10.core.tenancy import tenant_context
from agente10.curator.client import CuratorClient
from agente10.curator.cluster_namer import refine_cluster_name
from agente10.curator.cnae_picker import pick_cnae
from agente10.curator.shortlist_reranker import rerank_top10
from agente10.empresas.discovery import find_empresas_by_cnae
from agente10.estagio1.classificador_cnae import classify_cluster
from agente10.estagio1.clusterizador import cluster_rows
from agente10.estagio1.csv_parser import ParsedRow, parse_catalog_bytes
from agente10.estagio3.shortlist_generator import generate_shortlist
from agente10.integrations.voyage import VoyageClient

log = logging.getLogger(__name__)


async def _set_status(
    session: AsyncSession,
    upload_id: UUID,
    status: str,
    erro: str | None = None,
) -> None:
    # Record data_conclusao on terminal states so the UI can show total duration.
    sets = "status = :s, erro = :e"
    if status in ("done", "failed"):
        sets += ", data_conclusao = NOW()"
    await session.execute(
        text(f"UPDATE spend_uploads SET {sets} WHERE id = :id"),
        {"s": status, "e": erro, "id": str(upload_id)},
    )


async def _parse_stage(
    session: AsyncSession,
    upload_id: UUID,
    tenant_id: UUID,
    csv_path: Path,
    column_mapping: dict[str, str] | None = None,
) -> int:
    existing = await session.scalar(
        text("SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u"),
        {"u": str(upload_id)},
    )
    if existing and existing > 0:
        log.info("parse stage: %d rows already present, skipping", existing)
        return int(existing)

    # Worker runs in a different container than the API, so the local
    # csv_path may not exist. Fall back to file_bytes stored in Postgres.
    if csv_path.exists():
        raw = csv_path.read_bytes()
    else:
        log.info("parse stage: csv_path %s missing, reading file_bytes from DB", csv_path)
        row = await session.execute(
            text("SELECT file_bytes, nome_arquivo FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
        r = row.first()
        if not r or not r.file_bytes:
            raise RuntimeError(f"upload {upload_id} has no file_bytes and {csv_path} doesn't exist")
        raw = bytes(r.file_bytes)
        # Override csv_path.name for filename-based format detection (xlsx vs csv)
        csv_path = Path(r.nome_arquivo)
    rows = list(parse_catalog_bytes(raw, csv_path.name, overrides=column_mapping))

    # Free the file bytes from Postgres now that we have spend_linhas — retries
    # skip parse when linhas exist, so the bytes are no longer needed.
    await session.execute(
        text("UPDATE spend_uploads SET file_bytes = NULL WHERE id = :u"),
        {"u": str(upload_id)},
    )
    for row in rows:
        await session.execute(
            text("""
                INSERT INTO spend_linhas (
                    tenant_id, upload_id, descricao_original, agrupamento,
                    id_linha_origem, fornecedor_atual, cnpj_fornecedor,
                    valor_total, quantidade, uf_solicitante, municipio_solicitante,
                    centro_custo, data_compra, extras
                ) VALUES (
                    :t, :u, :d, :a, :ilo, :fa, :cf, :v, :q, :uf, :m, :cc, :dc, CAST(:ex AS jsonb)
                )
                """),
            {
                "t": str(tenant_id),
                "u": str(upload_id),
                "d": row.descricao_original,
                "a": row.agrupamento,
                "ilo": row.id_linha_origem,
                "fa": row.fornecedor_atual,
                "cf": row.cnpj_fornecedor,
                "v": row.valor_total,
                "q": row.quantidade,
                "uf": row.uf_solicitante,
                "m": row.municipio_solicitante,
                "cc": row.centro_custo,
                "dc": row.data_compra,
                "ex": json.dumps(row.extras),
            },
        )
    await session.execute(
        text("UPDATE spend_uploads SET linhas_total = :n WHERE id = :u"),
        {"n": len(rows), "u": str(upload_id)},
    )
    return len(rows)


async def _cluster_stage(
    session: AsyncSession,
    upload_id: UUID,
    tenant_id: UUID,
    voyage: VoyageClient,
) -> None:
    existing = await session.scalar(
        text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u"),
        {"u": str(upload_id)},
    )
    if existing and existing > 0:
        log.info("cluster stage: %d clusters already exist, skipping", existing)
        return

    result = await session.execute(
        text(
            "SELECT id, descricao_original, agrupamento "
            "FROM spend_linhas WHERE upload_id = :u ORDER BY id"
        ),
        {"u": str(upload_id)},
    )
    rows = result.all()

    parsed = [
        ParsedRow(descricao_original=r.descricao_original, agrupamento=r.agrupamento) for r in rows
    ]
    assignments = await cluster_rows(parsed, voyage)

    name_to_cluster_id: dict[str, str] = {}
    for assignment in assignments:
        name = assignment.cluster_name
        if name not in name_to_cluster_id:
            row = await session.execute(
                text(
                    "INSERT INTO spend_clusters (tenant_id, upload_id, nome_cluster, num_linhas) "
                    "VALUES (:t, :u, :n, 0) RETURNING id"
                ),
                {"t": str(tenant_id), "u": str(upload_id), "n": name},
            )
            name_to_cluster_id[name] = str(row.scalar())
        cluster_id = name_to_cluster_id[name]
        await session.execute(
            text("UPDATE spend_linhas SET cluster_id = :c WHERE id = :i"),
            {"c": cluster_id, "i": str(rows[assignment.row_index].id)},
        )

    await session.execute(
        text(
            "UPDATE spend_clusters SET num_linhas = sub.cnt "
            "FROM (SELECT cluster_id, COUNT(*) AS cnt FROM spend_linhas "
            "      WHERE upload_id = :u GROUP BY cluster_id) sub "
            "WHERE spend_clusters.id = sub.cluster_id"
        ),
        {"u": str(upload_id)},
    )


async def _cnae_stage(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    upload_id: UUID,
    voyage: VoyageClient,
    curator: CuratorClient,
) -> None:
    # Per-cluster transactions: classify_cluster runs Voyage embed + (optionally)
    # Anthropic curator. Same long-tx risk as shortlist_stage over Railway proxy.
    async with session_factory() as s0, s0.begin():
        async with tenant_context(s0, tenant_id):
            result = await s0.execute(
                text(
                    "SELECT id, nome_cluster FROM spend_clusters "
                    "WHERE upload_id = :u AND cnae IS NULL"
                ),
                {"u": str(upload_id)},
            )
            clusters = result.all()

    for c in clusters:
        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                # Sample lines give the curator + namer concrete evidence of
                # what this cluster actually contains (centroid name alone is
                # often too narrow).
                sample_rows = await session.execute(
                    text(
                        "SELECT descricao_original FROM spend_linhas "
                        "WHERE cluster_id = :c ORDER BY id LIMIT 5"
                    ),
                    {"c": str(c.id)},
                )
                sample_lines = [r.descricao_original for r in sample_rows.all()]

                outcome = await classify_cluster(
                    c.nome_cluster,
                    voyage=voyage,
                    retrieval_hybrid=lambda emb, k, p: top_k_cnaes_hybrid(
                        session, emb, k=k, pool_size=p
                    ),
                    curator_pick=partial(pick_cnae, curator),
                    cache_session=session,
                    sample_lines=sample_lines,
                )

                # After CNAE is known, refine the cluster name into something
                # broader and aligned with the CNAE's domain (only for
                # high-confidence assignments — manual_pending stays raw).
                nome_refinado: str | None = None
                if outcome.cnae_metodo in ("retrieval", "curator", "cache"):
                    try:
                        denom_row = await session.execute(
                            text("SELECT denominacao FROM cnae_taxonomy WHERE codigo = :c"),
                            {"c": outcome.cnae},
                        )
                        denom = denom_row.scalar()
                        if denom:
                            refined = await refine_cluster_name(
                                curator,
                                c.nome_cluster,
                                sample_lines,
                                outcome.cnae,
                                denom,
                            )
                            nome_refinado = refined.nome
                    except Exception:
                        nome_refinado = None  # never block on naming failures

                await session.execute(
                    text(
                        "UPDATE spend_clusters SET "
                        "  cnae=:cnae, cnae_confianca=:c, cnae_metodo=:m, "
                        "  cnaes_secundarios=:sec, "
                        "  nome_cluster_refinado=:nr "
                        "WHERE id=:i"
                    ),
                    {
                        "cnae": outcome.cnae,
                        "c": outcome.cnae_confianca,
                        "m": outcome.cnae_metodo,
                        "sec": outcome.cnaes_secundarios,
                        "nr": nome_refinado,
                        "i": str(c.id),
                    },
                )
                # Live progress: running count of linhas whose cluster has CNAE.
                await session.execute(
                    text("""
                        UPDATE spend_uploads SET linhas_classificadas = COALESCE((
                            SELECT SUM(sc.num_linhas) FROM spend_clusters sc
                            WHERE sc.upload_id = :u AND sc.cnae IS NOT NULL
                        ), 0)
                        WHERE id = :u
                    """),
                    {"u": str(upload_id)},
                )


async def _shortlist_stage(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    upload_id: UUID,
    curator: CuratorClient,
) -> None:
    # Per-cluster transactions: rerank_top10 hits Anthropic (~1-3s/cluster);
    # holding one transaction for 163 clusters drops Railway's proxy connection.
    async with session_factory() as s0, s0.begin():
        async with tenant_context(s0, tenant_id):
            result = await s0.execute(
                text(
                    "SELECT id, nome_cluster, cnae, cnaes_secundarios "
                    "FROM spend_clusters "
                    "WHERE upload_id = :u AND cnae IS NOT NULL AND shortlist_gerada = false"
                ),
                {"u": str(upload_id)},
            )
            clusters = result.all()

    for c in clusters:
        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                # Generate a shortlist for primary + each secondary CNAE.
                # supplier_shortlists is keyed by (tenant_id, cnae, cnpj) so the
                # GET endpoint already dedupes across CNAEs at query time.
                cnaes_alvo = [c.cnae] + list(c.cnaes_secundarios or [])
                for cnae_target in cnaes_alvo:
                    entries = await generate_shortlist(
                        c.nome_cluster,
                        cnae_target,
                        discovery=lambda cnae: find_empresas_by_cnae(session, cnae, limit=25),
                        rerank=partial(rerank_top10, curator),
                    )
                    for entry in entries:
                        await session.execute(
                            text(
                                "INSERT INTO supplier_shortlists "
                                "(tenant_id, cnae, cnpj_fornecedor, rank_estagio3) "
                                "VALUES (:t, :cnae, :cnpj, :r)"
                            ),
                            {
                                "t": str(tenant_id),
                                "cnae": cnae_target,
                                "cnpj": entry.cnpj,
                                "r": entry.rank_estagio3,
                            },
                        )
                await session.execute(
                    text("UPDATE spend_clusters SET shortlist_gerada = true WHERE id = :i"),
                    {"i": str(c.id)},
                )


async def _denorm_stage(session: AsyncSession, upload_id: UUID) -> None:
    await session.execute(
        text(
            "UPDATE spend_linhas SET "
            "  cnae = c.cnae, "
            "  cnae_confianca = c.cnae_confianca, "
            "  cnae_metodo = c.cnae_metodo "
            "FROM spend_clusters c "
            "WHERE spend_linhas.cluster_id = c.id AND spend_linhas.upload_id = :u"
        ),
        {"u": str(upload_id)},
    )
    await session.execute(
        text(
            "UPDATE spend_uploads SET linhas_classificadas = "
            "(SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u AND cnae IS NOT NULL) "
            "WHERE id = :u"
        ),
        {"u": str(upload_id)},
    )


async def processar_upload(
    upload_id: UUID,
    tenant_id: UUID,
    csv_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    voyage: VoyageClient,
    curator: CuratorClient,
    column_mapping: dict[str, str] | None = None,
) -> None:
    """Run the full Estágio 1 + Estágio 3 pipeline for one upload."""
    # cnae_stage and shortlist_stage manage their own per-cluster sessions
    # (Voyage + Anthropic calls are too slow for one big transaction over
    # Railway's proxy).
    session_stages = [
        ("parse", _parse_stage, (upload_id, tenant_id, csv_path, column_mapping)),
        ("cluster", _cluster_stage, (upload_id, tenant_id, voyage)),
    ]
    async with session_factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await _set_status(session, upload_id, "processing")

    try:
        for name, fn, args in session_stages:
            log.info("pipeline upload=%s stage=%s starting", upload_id, name)
            async with session_factory() as session, session.begin():
                async with tenant_context(session, tenant_id):
                    await fn(session, *args)

        log.info("pipeline upload=%s stage=cnae starting", upload_id)
        await _cnae_stage(session_factory, tenant_id, upload_id, voyage, curator)

        log.info("pipeline upload=%s stage=shortlist starting", upload_id)
        await _shortlist_stage(session_factory, tenant_id, upload_id, curator)

        log.info("pipeline upload=%s stage=denorm starting", upload_id)
        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                await _denorm_stage(session, upload_id)

        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                await _set_status(session, upload_id, "done")
    except Exception:
        log.exception("pipeline upload=%s failed", upload_id)
        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                await _set_status(
                    session,
                    upload_id,
                    "failed",
                    erro=traceback.format_exc()[:4000],
                )
