"""Hybrid CNAE classification with cache + hybrid retrieval + rerank + curator.

Pipeline (per cluster):
  1. Cache hit by description hash → reuse, method='cache'
  2. Voyage embed cluster_name
  3. Hybrid retrieval: union top-K from `embedding` AND `embedding_rich`
     (denominacao-only + denominacao+exemplos) — wider candidate pool
  4. Voyage rerank-2.5 over the pool against FULL IBGE notes per candidate
     — much richer than the cosine-on-short-denominacao signal
  5. Take top-5 reranked
  6. Decision:
     - reranked top1 score >= AUTO_THRESHOLD → retrieval
     - >= CURATOR_THRESHOLD → Claude Haiku picks (with few-shots + hierarchy)
     - < CURATOR_THRESHOLD → manual_pending
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field

from agente10.cache import classification_cache as cache
from agente10.cnae.retrieval import CnaeCandidate
from agente10.cnae.trade_tier import (
    find_trade_tier_siblings,
    normalize_to_fabricacao_first,
)
from agente10.curator.cnae_picker import CnaePick
from agente10.integrations.voyage import VoyageClient

AUTO_THRESHOLD = 0.85
CURATOR_THRESHOLD = 0.60

# Rerank thresholds operate on rerank-2.5 relevance score (0..1, typically lower
# than cosine — rerank-2.5 is more conservative). Calibrated empirically:
# scores around 0.6-0.7 are confident; 0.3-0.5 ambiguous; <0.3 weak.
RERANK_AUTO_THRESHOLD = 0.70
RERANK_CURATOR_THRESHOLD = 0.35


class ClassificationResult(BaseModel):
    cnae: str
    cnae_confianca: float
    cnae_metodo: str  # cache | retrieval | curator | retrieval_fallback | manual_pending
    cnaes_secundarios: list[str] = Field(default_factory=list)


HybridRetrievalFn = Callable[[list[float], int, int], Awaitable[list[CnaeCandidate]]]
CuratorPickFn = Callable[..., Awaitable[CnaePick]]


async def _maybe_enrich_with_trade_tier(
    result: ClassificationResult,
    cache_session: object | None,
) -> ClassificationResult:
    """Auto-suggest fabricação/atacado/varejo siblings when the primary CNAE is
    in one of those divisions. Best-effort: any failure leaves the result
    unchanged. Skipped for manual_pending (no confident primary to anchor on)."""
    if result.cnae_metodo == "manual_pending" or cache_session is None:
        return result
    try:
        siblings = await find_trade_tier_siblings(cache_session, result.cnae)  # type: ignore[arg-type]
        new_primary, new_secs = normalize_to_fabricacao_first(
            result.cnae, result.cnaes_secundarios, siblings
        )
        result.cnae = new_primary
        result.cnaes_secundarios = new_secs
    except Exception:
        pass
    return result


def _build_rerank_doc(c: CnaeCandidate) -> str:
    """Compose a rerank document with all signals — keeps under rerank-2.5's token limit."""
    parts = [f"{c.codigo} — {c.denominacao}"]
    if c.divisao_descricao:
        parts.append(f"Divisão: {c.divisao_descricao[:300]}")
    if c.grupo_descricao:
        parts.append(f"Grupo: {c.grupo_descricao[:200]}")
    if c.exemplos_atividades:
        parts.append(f"Compreende: {c.exemplos_atividades[:800]}")
    if c.notas_explicativas:
        parts.append(f"NÃO compreende: {c.notas_explicativas[:500]}")
    return "\n".join(parts)


async def classify_cluster(
    cluster_name: str,
    *,
    voyage: VoyageClient,
    retrieval_hybrid: HybridRetrievalFn,
    curator_pick: CuratorPickFn,
    cache_session: object | None = None,
    sample_lines: list[str] | None = None,
) -> ClassificationResult:
    """Classify one cluster using cache → hybrid retrieval → rerank → curator."""
    # 1. Cache lookup
    if cache_session is not None:
        hit = await cache.lookup(cache_session, cluster_name)  # type: ignore[arg-type]
        if hit is not None:
            result = ClassificationResult(
                cnae=hit.cnae, cnae_confianca=hit.confianca, cnae_metodo="cache"
            )
            return await _maybe_enrich_with_trade_tier(result, cache_session)

    # 2. Embed + 3. Hybrid retrieval
    embedding = await voyage.embed_query(cluster_name)
    pool = await retrieval_hybrid(embedding, 5, 12)
    if not pool:
        raise RuntimeError("retrieval returned 0 candidates — taxonomy not loaded?")

    # 4. Voyage rerank-2.5 over full IBGE notes
    try:
        docs = [_build_rerank_doc(c) for c in pool]
        ranked = await voyage.rerank(cluster_name, docs, top_k=5)
        # ranked is list[(index, score)] in best-first order
        candidates = [pool[idx] for idx, _ in ranked]
        # Replace cosine similarity with rerank score for downstream gating
        for c, (_, score) in zip(candidates, ranked, strict=True):
            c.similarity = score  # type: ignore[misc]  # frozen=False on this Pydantic model
        rerank_top_score = ranked[0][1]
    except Exception:
        # Fallback: use the hybrid cosine ordering directly
        candidates = sorted(pool, key=lambda c: c.similarity, reverse=True)[:5]
        rerank_top_score = candidates[0].similarity

    top = candidates[0]

    # 5. Decision band (rerank thresholds apply since rerank score replaces cosine
    # similarity above; fallback path also uses cosine in the same 0..1 range).
    auto_thr = RERANK_AUTO_THRESHOLD
    curator_thr = RERANK_CURATOR_THRESHOLD

    if rerank_top_score >= auto_thr:
        result = ClassificationResult(
            cnae=top.codigo, cnae_confianca=rerank_top_score, cnae_metodo="retrieval"
        )
        if cache_session is not None:
            await cache.upsert(
                cache_session,  # type: ignore[arg-type]
                cluster_name,
                result.cnae,
                result.cnae_confianca,
                result.cnae_metodo,
                embedding=embedding,
            )
        return await _maybe_enrich_with_trade_tier(result, cache_session)

    if rerank_top_score >= curator_thr:
        # Few-shot: similar already-classified descriptions, prioritizing humano
        few_shots = None
        if cache_session is not None:
            try:
                few_shots = await cache.find_similar_examples(
                    cache_session,  # type: ignore[arg-type]
                    embedding,
                    k=3,
                )
            except Exception:
                few_shots = None
        try:
            pick = await curator_pick(
                cluster_name,
                candidates,
                few_shots=few_shots,
                sample_lines=sample_lines,
            )
            result = ClassificationResult(
                cnae=pick.cnae,
                cnae_confianca=pick.confidence,
                cnae_metodo="curator",
                cnaes_secundarios=pick.secondary_cnaes,
            )
            if cache_session is not None:
                await cache.upsert(
                    cache_session,  # type: ignore[arg-type]
                    cluster_name,
                    result.cnae,
                    result.cnae_confianca,
                    result.cnae_metodo,
                    embedding=embedding,
                )
            return await _maybe_enrich_with_trade_tier(result, cache_session)
        except Exception:
            fallback = ClassificationResult(
                cnae=top.codigo,
                cnae_confianca=rerank_top_score,
                cnae_metodo="retrieval_fallback",
            )
            return await _maybe_enrich_with_trade_tier(fallback, cache_session)

    return ClassificationResult(
        cnae=top.codigo, cnae_confianca=rerank_top_score, cnae_metodo="manual_pending"
    )
