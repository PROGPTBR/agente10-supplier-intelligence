"""Integration tests for CNAE retrieval (top_k_cnaes). Requires populated cnae_taxonomy."""

import random

import pytest

from agente10.cnae.retrieval import CnaeCandidate, top_k_cnaes

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_top_k_returns_k_candidates_sorted_desc(db_session):
    random.seed(42)
    fake_query = [random.gauss(0, 1) for _ in range(1024)]

    candidates = await top_k_cnaes(db_session, fake_query, k=10)

    assert len(candidates) == 10
    assert all(isinstance(c, CnaeCandidate) for c in candidates)
    assert all(len(c.codigo) == 7 for c in candidates)
    assert all(c.denominacao for c in candidates)
    sims = [c.similarity for c in candidates]
    assert sims == sorted(sims, reverse=True)
    assert all(-1.0 <= s <= 1.0 for s in sims)


@pytest.mark.asyncio
async def test_top_k_respects_k_parameter(db_session):
    random.seed(0)
    fake_query = [random.gauss(0, 1) for _ in range(1024)]

    for k in (1, 3, 25):
        candidates = await top_k_cnaes(db_session, fake_query, k=k)
        assert len(candidates) == k
