"""Estágio 3: per cluster (cnae) → top-N supplier shortlist."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agente10.curator.client import CuratorClient
from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.empresas.discovery import EmpresaCandidate

DEFAULT_SHORTLIST_SIZE = 10
RETRIEVAL_POOL = 25

DiscoveryFn = Callable[[str], Awaitable[list[EmpresaCandidate]]]
RerankFn = Callable[[str, list[EmpresaCandidate]], Awaitable[list[RankedSupplier]]]


class ShortlistEntry(BaseModel):
    cnpj: str
    rank_estagio3: int


async def generate_shortlist(
    cluster_name: str,
    cnae: str,
    *,
    discovery: DiscoveryFn,
    rerank: RerankFn,
    size: int = DEFAULT_SHORTLIST_SIZE,
) -> list[ShortlistEntry]:
    """Return top-`size` supplier shortlist. Curator rerank with fallback to helper order."""
    candidates = await discovery(cnae)
    if not candidates:
        return []
    try:
        ranked = await rerank(cluster_name, candidates)
        seen: set[str] = set()
        deduped: list[RankedSupplier] = []
        for r in ranked:
            if r.cnpj not in seen:
                seen.add(r.cnpj)
                deduped.append(r)
        return [ShortlistEntry(cnpj=r.cnpj, rank_estagio3=r.rank) for r in deduped[:size]]
    except Exception:
        seen_fallback: set[str] = set()
        deduped_fallback: list[EmpresaCandidate] = []
        for c in candidates:
            if c.cnpj not in seen_fallback:
                seen_fallback.add(c.cnpj)
                deduped_fallback.append(c)
        return [
            ShortlistEntry(cnpj=c.cnpj, rank_estagio3=i + 1)
            for i, c in enumerate(deduped_fallback[:size])
        ]


async def regenerate_shortlist_for_cluster(
    cluster_id: UUID,
    tenant_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    curator: CuratorClient,
) -> None:
    """Re-run Estágio 3 for a single cluster: delete old shortlist, re-insert new.

    Reads the upload's shortlist config (size + filters) so a PATCH-triggered
    regen honors the same constraints the user picked at upload time.
    """
    from functools import partial

    from sqlalchemy import text

    from agente10.config.shortlist import parse_from_metadados
    from agente10.core.tenancy import tenant_context
    from agente10.curator.shortlist_reranker import rerank_top10
    from agente10.empresas.discovery import find_empresas_by_cnae

    async with session_factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            cluster = (
                await session.execute(
                    text(
                        "SELECT c.id, c.cnae, c.nome_cluster, u.metadados "
                        "FROM spend_clusters c "
                        "JOIN spend_uploads u ON u.id = c.upload_id "
                        "WHERE c.id = :i"
                    ),
                    {"i": str(cluster_id)},
                )
            ).first()
            if not cluster or not cluster.cnae:
                return
            cfg = parse_from_metadados(cluster.metadados)
            pool_size = max(cfg.size * 3, RETRIEVAL_POOL)
            await session.execute(
                text("DELETE FROM supplier_shortlists WHERE cnae = :c AND tenant_id = :t"),
                {"c": cluster.cnae, "t": str(tenant_id)},
            )
            entries = await generate_shortlist(
                cluster.nome_cluster,
                cluster.cnae,
                discovery=lambda cnae: find_empresas_by_cnae(
                    session,
                    cnae,
                    uf=cfg.uf,
                    municipio=cfg.municipio,
                    only_matriz=cfg.only_matriz,
                    min_capital=cfg.min_capital,
                    limit=pool_size,
                ),
                rerank=partial(rerank_top10, curator),
                size=cfg.size,
            )
            for entry in entries:
                await session.execute(
                    text(
                        "INSERT INTO supplier_shortlists "
                        "(tenant_id, cnae, cnpj_fornecedor, rank_estagio3) "
                        "VALUES (:t, :c, :cnpj, :r)"
                    ),
                    {
                        "t": str(tenant_id),
                        "c": cluster.cnae,
                        "cnpj": entry.cnpj,
                        "r": entry.rank_estagio3,
                    },
                )
            await session.execute(
                text("UPDATE spend_clusters SET shortlist_gerada = true WHERE id = :i"),
                {"i": str(cluster_id)},
            )
