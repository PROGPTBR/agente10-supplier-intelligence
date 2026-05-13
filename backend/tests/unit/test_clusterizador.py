# backend/tests/unit/test_clusterizador.py
from unittest.mock import AsyncMock

import pytest

from agente10.estagio1.clusterizador import cluster_rows
from agente10.estagio1.csv_parser import ParsedRow


def _row(descricao: str, agrupamento: str | None = None) -> ParsedRow:
    return ParsedRow(descricao_original=descricao, agrupamento=agrupamento)


@pytest.mark.asyncio
async def test_agrupamento_groups_preserve_input():
    rows = [
        _row("Parafuso M8", "Parafusos"),
        _row("Parafuso M10", "Parafusos"),
        _row("Gerador 5kVA", "Geradores"),
    ]
    voyage = AsyncMock()
    result = await cluster_rows(rows, voyage)
    cluster_names = sorted(set(a.cluster_name for a in result))
    assert cluster_names == ["geradores", "parafusos"]
    voyage.embed_documents.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_path_used_when_no_agrupamento():
    rows = [
        _row("Parafuso M8"),
        _row("Parafuso M10"),
        _row("Parafuso M12"),
    ]
    voyage = AsyncMock()
    # 3D vectors close together → 1 cluster
    voyage.embed_documents.return_value = [
        [1.0, 0.0, 0.0],
        [0.99, 0.01, 0.0],
        [0.98, 0.02, 0.0],
    ]
    result = await cluster_rows(rows, voyage, min_cluster_size=2)
    assert len(set(a.cluster_name for a in result)) == 1


@pytest.mark.asyncio
async def test_hybrid_handles_mixed_rows():
    rows = [
        _row("Parafuso M8", "Parafusos"),
        _row("Cabo elétrico 2.5mm"),  # no agrupamento → embedding bucket
    ]
    voyage = AsyncMock()
    voyage.embed_documents.return_value = [[1.0, 0.0]]
    result = await cluster_rows(rows, voyage, min_cluster_size=1)
    cluster_names = {a.cluster_name for a in result}
    assert "parafusos" in cluster_names
    assert len(cluster_names) == 2  # agrupamento cluster + 1 noise/singleton
