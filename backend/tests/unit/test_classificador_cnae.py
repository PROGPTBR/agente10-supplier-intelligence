from unittest.mock import AsyncMock

import pytest

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.estagio1.classificador_cnae import (
    ClassificationResult,
    classify_cluster,
)


def _candidates(top_sim: float) -> list[CnaeCandidate]:
    return [
        CnaeCandidate(codigo="4744001", denominacao="x", similarity=top_sim),
        CnaeCandidate(codigo="4673700", denominacao="y", similarity=top_sim - 0.05),
        CnaeCandidate(codigo="4674500", denominacao="z", similarity=top_sim - 0.10),
        CnaeCandidate(codigo="4684201", denominacao="w", similarity=top_sim - 0.15),
        CnaeCandidate(codigo="4789099", denominacao="v", similarity=top_sim - 0.20),
    ]


@pytest.mark.asyncio
async def test_auto_path_when_top_similarity_high():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.90))
    curator = AsyncMock()
    result = await classify_cluster(
        "parafusos",
        voyage=voyage,
        retrieval=retrieval,
        curator_pick=curator,
    )
    assert isinstance(result, ClassificationResult)
    assert result.cnae == "4744001"
    assert result.cnae_metodo == "retrieval"
    assert result.cnae_confianca == pytest.approx(0.90)
    curator.assert_not_called()


@pytest.mark.asyncio
async def test_curator_path_when_medium_similarity():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.75))
    curator = AsyncMock(return_value=CnaePick(cnae="4673700", confidence=0.85, reasoning="x"))
    result = await classify_cluster(
        "atacado madeira",
        voyage=voyage,
        retrieval=retrieval,
        curator_pick=curator,
    )
    assert result.cnae == "4673700"
    assert result.cnae_metodo == "curator"
    assert result.cnae_confianca == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_curator_fallback_uses_retrieval_top1():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.75))
    curator = AsyncMock(side_effect=RuntimeError("api down"))
    result = await classify_cluster(
        "x",
        voyage=voyage,
        retrieval=retrieval,
        curator_pick=curator,
    )
    assert result.cnae == "4744001"
    assert result.cnae_metodo == "retrieval_fallback"


@pytest.mark.asyncio
async def test_manual_pending_when_low_similarity():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.50))
    curator = AsyncMock()
    result = await classify_cluster(
        "totally ambiguous",
        voyage=voyage,
        retrieval=retrieval,
        curator_pick=curator,
    )
    assert result.cnae == "4744001"
    assert result.cnae_metodo == "manual_pending"
    assert result.cnae_confianca == pytest.approx(0.50)
    curator.assert_not_called()
