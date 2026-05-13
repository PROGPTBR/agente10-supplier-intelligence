"""Hybrid CNAE classification: retrieval / curator / manual_pending."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.integrations.voyage import VoyageClient

AUTO_THRESHOLD = 0.85
CURATOR_THRESHOLD = 0.60


class ClassificationResult(BaseModel):
    cnae: str
    cnae_confianca: float
    cnae_metodo: str  # 'retrieval' | 'curator' | 'retrieval_fallback' | 'manual_pending'


CandidatesFn = Callable[[list[float]], Awaitable[list[CnaeCandidate]]]
CuratorPickFn = Callable[[str, list[CnaeCandidate]], Awaitable[CnaePick]]


async def classify_cluster(
    cluster_name: str,
    *,
    voyage: VoyageClient,
    retrieval: CandidatesFn,
    curator_pick: CuratorPickFn,
) -> ClassificationResult:
    """Classify one cluster following the three-path rule.

    - top_sim >= 0.85 -> retrieval top-1, method='retrieval'
    - 0.60 <= top_sim < 0.85 -> LLM curator picks from top-5, method='curator'
        (on curator failure, falls back to retrieval top-1, method='retrieval_fallback')
    - top_sim < 0.60 -> retrieval top-1 + flag manual_pending
    """
    embedding = await voyage.embed_query(cluster_name)
    candidates = await retrieval(embedding)
    if not candidates:
        raise RuntimeError("retrieval returned 0 candidates — taxonomy not loaded?")

    top = candidates[0]
    top_sim = top.similarity

    if top_sim >= AUTO_THRESHOLD:
        return ClassificationResult(
            cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="retrieval"
        )

    if top_sim >= CURATOR_THRESHOLD:
        try:
            pick = await curator_pick(cluster_name, candidates)
            return ClassificationResult(
                cnae=pick.cnae, cnae_confianca=pick.confidence, cnae_metodo="curator"
            )
        except Exception:
            return ClassificationResult(
                cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="retrieval_fallback"
            )

    return ClassificationResult(
        cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="manual_pending"
    )
