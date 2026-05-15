from datetime import date
from unittest.mock import AsyncMock

import pytest

from agente10.curator import shortlist_reranker
from agente10.curator.shortlist_reranker import RankedSupplier, rerank_top10
from agente10.empresas.discovery import EmpresaCandidate


def _candidate(cnpj: str) -> EmpresaCandidate:
    return EmpresaCandidate(
        cnpj=cnpj,
        razao_social=f"EMP {cnpj}",
        nome_fantasia=None,
        cnae_primario="4744001",
        primary_match=True,
        uf="SP",
        municipio="Sao Paulo",
        data_abertura=date(2000, 1, 1),
    )


@pytest.mark.asyncio
async def test_reranker_returns_top_in_voyage_order(monkeypatch):
    """Voyage rerank-2.5 returns (index, score) pairs in best-first order.
    rerank_top10 must map those indices back to the original candidates and
    emit RankedSupplier objects with sequential ranks starting at 1.
    """
    candidates = [_candidate(str(i).zfill(14)) for i in range(25)]
    # Voyage hands back indices 24,23,...,15 (reverse order) — verifies we
    # actually use the indices instead of returning candidates in input order.
    fake_pairs = [(24 - i, 0.9 - 0.01 * i) for i in range(10)]
    voyage_mock = AsyncMock()
    voyage_mock.rerank.return_value = fake_pairs
    monkeypatch.setattr(shortlist_reranker, "VoyageClient", lambda: voyage_mock)

    top = await rerank_top10(None, "parafusos m8", candidates)  # type: ignore[arg-type]
    assert len(top) == 10
    assert isinstance(top[0], RankedSupplier)
    assert top[0].cnpj == candidates[24].cnpj
    assert top[0].rank == 1
    assert top[9].cnpj == candidates[15].cnpj
    assert top[9].rank == 10


@pytest.mark.asyncio
async def test_reranker_empty_input_returns_empty():
    """Short-circuit before instantiating VoyageClient — keeps the cheap path cheap."""
    assert await rerank_top10(None, "x", []) == []  # type: ignore[arg-type]
