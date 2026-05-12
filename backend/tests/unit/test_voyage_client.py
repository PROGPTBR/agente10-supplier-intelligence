"""Unit tests for the Voyage client wrapper (no API calls)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agente10.integrations.voyage import VoyageClient


@pytest.mark.asyncio
async def test_embed_query_uses_query_input_type():
    client = VoyageClient(api_key="fake-key", model="voyage-3")
    mock_resp = MagicMock(embeddings=[[0.1] * 1024])
    client.client.embed = AsyncMock(return_value=mock_resp)

    result = await client.embed_query("parafuso")

    assert len(result) == 1024
    client.client.embed.assert_awaited_once_with(["parafuso"], model="voyage-3", input_type="query")


@pytest.mark.asyncio
async def test_embed_documents_uses_document_input_type():
    client = VoyageClient(api_key="fake-key", model="voyage-3")
    mock_resp = MagicMock(embeddings=[[0.1] * 1024, [0.2] * 1024])
    client.client.embed = AsyncMock(return_value=mock_resp)

    result = await client.embed_documents(["parafuso", "gerador"])

    assert len(result) == 2
    assert len(result[0]) == 1024
    client.client.embed.assert_awaited_once_with(
        ["parafuso", "gerador"], model="voyage-3", input_type="document"
    )


@pytest.mark.asyncio
async def test_embed_query_handles_unicode_and_special_chars():
    client = VoyageClient(api_key="fake-key", model="voyage-3")
    mock_resp = MagicMock(embeddings=[[0.0] * 1024])
    client.client.embed = AsyncMock(return_value=mock_resp)

    result = await client.embed_query("manutenção corretiva — ar-condicionado")

    assert len(result) == 1024
    args, kwargs = client.client.embed.call_args
    assert args[0] == ["manutenção corretiva — ar-condicionado"]
