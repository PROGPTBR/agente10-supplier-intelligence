"""Integration tests for CNAE retrieval (top_k_cnaes). Requires populated cnae_taxonomy."""

import csv
import random
from pathlib import Path

import pytest

from agente10.cnae.retrieval import CnaeCandidate, top_k_cnaes

pytestmark = pytest.mark.integration

GOLDEN_PATH = Path(__file__).parent.parent / "fixtures" / "cnae_golden.csv"
MIN_RECALL_AT_5 = 0.85


def _load_golden() -> list[dict]:
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- Shape tests (no Voyage API; use a random query vector) ------------------


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


# --- Golden recall@5 test (Voyage required) ----------------------------------


@pytest.mark.voyage
@pytest.mark.asyncio
async def test_recall_at_5(db_session, voyage_client):
    """Each spend description must retrieve its expected CNAE within top-5 (recall >= 0.85)."""
    rows = _load_golden()
    assert len(rows) >= 10, f"fixture has {len(rows)} rows; need at least 10"

    misses: list[tuple[str, str, list[str]]] = []
    for row in rows:
        emb = await voyage_client.embed_query(row["descricao"])
        candidates = await top_k_cnaes(db_session, emb, k=5)
        codigos = [c.codigo for c in candidates]
        if row["cnae_esperado"] not in codigos:
            misses.append((row["descricao"], row["cnae_esperado"], codigos))

    recall = 1 - (len(misses) / len(rows))
    if misses:
        report = "\n".join(f"  - {d!r}: esperado {e}, top-5 = {c}" for d, e, c in misses)
        print(f"\nMisses ({len(misses)}/{len(rows)}):\n{report}")
    assert recall >= MIN_RECALL_AT_5, f"recall@5 = {recall:.2f}, esperado >= {MIN_RECALL_AT_5}"
