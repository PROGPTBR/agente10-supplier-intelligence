from datetime import date
from unittest.mock import AsyncMock

import pytest

from agente10.curator.shortlist_reranker import RankedSupplier, rerank_top10
from agente10.empresas.discovery import EmpresaCandidate


def _candidate(cnpj: str, capital: int = 1_000_000) -> EmpresaCandidate:
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
async def test_reranker_returns_top10_in_order():
    candidates = [_candidate(str(i).zfill(14)) for i in range(25)]
    client = AsyncMock()
    client.ask_json.return_value = [
        {"cnpj": str(i).zfill(14), "rank": i + 1, "reasoning": f"r{i}"} for i in range(10)
    ]
    top10 = await rerank_top10(client, "parafusos m8", candidates)
    assert len(top10) == 10
    assert isinstance(top10[0], RankedSupplier)
    assert top10[0].cnpj == "00000000000000"
    assert top10[0].rank == 1
    assert top10[9].rank == 10


@pytest.mark.asyncio
async def test_reranker_validates_all_cnpjs_in_input():
    candidates = [_candidate(str(i).zfill(14)) for i in range(5)]
    client = AsyncMock()
    client.ask_json.return_value = [
        {"cnpj": "99999999999999", "rank": 1, "reasoning": "fake"},
    ]
    with pytest.raises(ValueError, match="not in input candidates"):
        await rerank_top10(client, "x", candidates)
