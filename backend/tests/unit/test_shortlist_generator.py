# backend/tests/unit/test_shortlist_generator.py
from datetime import date
from unittest.mock import AsyncMock

import pytest

from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.empresas.discovery import EmpresaCandidate
from agente10.estagio3.shortlist_generator import (
    ShortlistEntry,
    generate_shortlist,
)


def _emp(cnpj: str) -> EmpresaCandidate:
    return EmpresaCandidate(
        cnpj=cnpj,
        razao_social="x",
        nome_fantasia=None,
        cnae_primario="4744001",
        primary_match=True,
        uf="SP",
        municipio="Sao Paulo",
        data_abertura=date(2000, 1, 1),
    )


@pytest.mark.asyncio
async def test_uses_curator_rerank_when_available():
    discovery = AsyncMock(return_value=[_emp(str(i).zfill(14)) for i in range(25)])
    rerank = AsyncMock(
        return_value=[
            RankedSupplier(cnpj=str(9 - i).zfill(14), rank=i + 1, reasoning="x") for i in range(10)
        ]
    )
    result = await generate_shortlist(
        "parafusos",
        "4744001",
        discovery=discovery,
        rerank=rerank,
    )
    assert len(result) == 10
    assert isinstance(result[0], ShortlistEntry)
    assert result[0].cnpj == "00000000000009"
    assert result[0].rank_estagio3 == 1


@pytest.mark.asyncio
async def test_falls_back_to_helper_order_on_rerank_failure():
    discovery = AsyncMock(return_value=[_emp(str(i).zfill(14)) for i in range(25)])
    rerank = AsyncMock(side_effect=RuntimeError("api down"))
    result = await generate_shortlist(
        "x",
        "4744001",
        discovery=discovery,
        rerank=rerank,
    )
    assert len(result) == 10
    assert result[0].cnpj == "00000000000000"
    assert result[0].rank_estagio3 == 1
    assert result[9].rank_estagio3 == 10
