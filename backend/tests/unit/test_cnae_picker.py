from unittest.mock import AsyncMock

import pytest

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick, pick_cnae


@pytest.mark.asyncio
async def test_picks_cnae_from_top5():
    candidates = [
        CnaeCandidate(codigo="4744001", denominacao="Comércio ferragens", similarity=0.72),
        CnaeCandidate(codigo="4673700", denominacao="Atacado madeira", similarity=0.68),
        CnaeCandidate(codigo="4674500", denominacao="Atacado material", similarity=0.65),
        CnaeCandidate(codigo="4684201", denominacao="Atacado produtos químicos", similarity=0.62),
        CnaeCandidate(codigo="4789099", denominacao="Comércio varejista diverso", similarity=0.60),
    ]
    client = AsyncMock()
    client.ask_json.return_value = {
        "cnae": "4744001",
        "confidence": 0.88,
        "reasoning": "parafusos são ferragens",
    }
    pick = await pick_cnae(client, "parafusos m8", candidates)
    assert isinstance(pick, CnaePick)
    assert pick.cnae == "4744001"
    assert pick.confidence == 0.88
    assert "parafusos" in pick.reasoning.lower()


@pytest.mark.asyncio
async def test_rejects_cnae_not_in_candidates():
    candidates = [
        CnaeCandidate(codigo="4744001", denominacao="x", similarity=0.7),
    ]
    client = AsyncMock()
    client.ask_json.return_value = {
        "cnae": "9999999",  # not in candidates → should raise
        "confidence": 0.9,
        "reasoning": "",
    }
    with pytest.raises(ValueError, match="not in candidates"):
        await pick_cnae(client, "x", candidates)
