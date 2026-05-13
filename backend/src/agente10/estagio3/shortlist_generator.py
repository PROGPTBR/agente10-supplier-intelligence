"""Estágio 3: per cluster (cnae) → top-10 supplier shortlist."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.empresas.discovery import EmpresaCandidate

SHORTLIST_SIZE = 10
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
) -> list[ShortlistEntry]:
    """Return top-10 supplier shortlist. Curator rerank with fallback to helper order."""
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
        return [ShortlistEntry(cnpj=r.cnpj, rank_estagio3=r.rank) for r in deduped[:SHORTLIST_SIZE]]
    except Exception:
        seen_fallback: set[str] = set()
        deduped_fallback: list[EmpresaCandidate] = []
        for c in candidates:
            if c.cnpj not in seen_fallback:
                seen_fallback.add(c.cnpj)
                deduped_fallback.append(c)
        return [
            ShortlistEntry(cnpj=c.cnpj, rank_estagio3=i + 1)
            for i, c in enumerate(deduped_fallback[:SHORTLIST_SIZE])
        ]
