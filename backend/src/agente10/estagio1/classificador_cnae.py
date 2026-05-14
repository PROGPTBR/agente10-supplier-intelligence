"""Hybrid CNAE classification: cache / retrieval / curator / manual_pending."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from agente10.cache import classification_cache as cache
from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.integrations.voyage import VoyageClient

AUTO_THRESHOLD = 0.85
CURATOR_THRESHOLD = 0.60


class ClassificationResult(BaseModel):
    cnae: str
    cnae_confianca: float
    cnae_metodo: str  # 'cache' | 'retrieval' | 'curator' | 'retrieval_fallback' | 'manual_pending'


CandidatesFn = Callable[[list[float]], Awaitable[list[CnaeCandidate]]]
CuratorPickFn = Callable[[str, list[CnaeCandidate]], Awaitable[CnaePick]]


async def classify_cluster(
    cluster_name: str,
    *,
    voyage: VoyageClient,
    retrieval: CandidatesFn,
    curator_pick: CuratorPickFn,
    # AsyncSession; lookup-only, kept loose to avoid hard import.
    cache_session: object | None = None,
) -> ClassificationResult:
    """Classify one cluster following the three-path rule, with cache shortcut.

    - cache hit -> reuse, method='cache' (skips Voyage + retrieval + curator)
    - top_sim >= 0.85 -> retrieval top-1, method='retrieval'
    - 0.60 <= top_sim < 0.85 -> LLM curator picks from top-5, method='curator'
        (on curator failure, falls back to retrieval top-1, method='retrieval_fallback')
    - top_sim < 0.60 -> retrieval top-1 + flag manual_pending
    """
    if cache_session is not None:
        hit = await cache.lookup(cache_session, cluster_name)  # type: ignore[arg-type]
        if hit is not None:
            return ClassificationResult(
                cnae=hit.cnae, cnae_confianca=hit.confianca, cnae_metodo="cache"
            )

    embedding = await voyage.embed_query(cluster_name)
    candidates = await retrieval(embedding)
    if not candidates:
        raise RuntimeError("retrieval returned 0 candidates — taxonomy not loaded?")

    top = candidates[0]
    top_sim = top.similarity

    if top_sim >= AUTO_THRESHOLD:
        result = ClassificationResult(
            cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="retrieval"
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
        return result

    if top_sim >= CURATOR_THRESHOLD:
        # Few-shot examples improve curator decisions in mid-confidence band.
        # We pass the cluster's own embedding to find similar already-classified
        # descriptions in the cache (preferring revisado_humano + golden seeds).
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
            pick = await curator_pick(cluster_name, candidates, few_shots=few_shots)
            result = ClassificationResult(
                cnae=pick.cnae, cnae_confianca=pick.confidence, cnae_metodo="curator"
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
            return result
        except Exception:
            return ClassificationResult(
                cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="retrieval_fallback"
            )

    return ClassificationResult(
        cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="manual_pending"
    )
