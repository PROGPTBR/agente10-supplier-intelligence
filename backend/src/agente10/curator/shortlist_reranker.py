"""Supplier shortlist reranker — Voyage rerank-2.5 (no LLM).

Earlier versions called Claude Haiku per cluster × per CNAE, which dominated
the per-upload cost. Voyage rerank-2.5 is two orders of magnitude cheaper
per call ($0.05/MTok vs Haiku's $1+$5) and gives equally usable ordering for
"sort these supplier candidates by how well they fit this category".

The function signature is kept compatible with the previous Haiku version
(it still accepts a `CuratorClient` as the first arg, ignored) so the call
sites in `_shortlist_stage` and `regenerate_shortlist_for_cluster` don't
need to thread a new Voyage handle.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from agente10.curator.client import CuratorClient
from agente10.empresas.discovery import EmpresaCandidate
from agente10.integrations.voyage import VoyageClient


class RankedSupplier(BaseModel):
    cnpj: str
    rank: int
    reasoning: str = ""


def _doc_for_candidate(c: EmpresaCandidate, today: date) -> str:
    """Build the rerank document for one candidate. Compact but information-
    dense: name + size + geography + age — the four signals that drive a
    procurement analyst's gut ranking."""
    idade = (today - c.data_abertura).days // 365 if c.data_abertura else None
    parts = [c.razao_social]
    if c.nome_fantasia and c.nome_fantasia != c.razao_social:
        parts.append(c.nome_fantasia)
    parts.append(f"UF: {c.uf or 'N/A'}")
    if c.municipio:
        parts.append(c.municipio)
    if idade is not None:
        parts.append(f"{idade} anos de mercado")
    return " · ".join(parts)


def _query_for_cluster(cluster_name: str) -> str:
    """Short query that conveys the procurement intent. rerank-2.5 weighs the
    query against each doc — we frame it as a B2B sourcing question."""
    return f"Fornecedor B2B Brasil para: {cluster_name}"


async def rerank_top10(
    _client: CuratorClient,  # kept for signature compatibility — not used
    cluster_name: str,
    candidates: list[EmpresaCandidate],
) -> list[RankedSupplier]:
    """Rerank candidates by Voyage rerank-2.5. Returns ranked list sorted by
    relevance descending. Idempotent — same input always yields same output."""
    if not candidates:
        return []
    voyage = VoyageClient()
    today = date.today()
    docs = [_doc_for_candidate(c, today) for c in candidates]
    pairs = await voyage.rerank(
        query=_query_for_cluster(cluster_name),
        documents=docs,
        top_k=len(candidates),
    )
    out: list[RankedSupplier] = []
    for rank, (idx, _score) in enumerate(pairs, start=1):
        out.append(
            RankedSupplier(
                cnpj=candidates[idx].cnpj,
                rank=rank,
            )
        )
    return out
