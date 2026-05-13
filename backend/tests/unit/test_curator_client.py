from unittest.mock import AsyncMock, MagicMock

import pytest

from agente10.curator.client import CuratorClient


@pytest.mark.asyncio
async def test_ask_json_returns_parsed_response(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text='{"answer": 42}')]

    fake_anthropic = MagicMock()
    fake_anthropic.messages.create = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(
        "agente10.curator.client.anthropic.AsyncAnthropic",
        lambda **kwargs: fake_anthropic,
    )
    client = CuratorClient(api_key="test-key")
    result = await client.ask_json("system", "user message")
    assert result == {"answer": 42}


@pytest.mark.asyncio
async def test_ask_json_strips_markdown_fence(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text='```json\n{"x": 1}\n```')]
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "agente10.curator.client.anthropic.AsyncAnthropic",
        lambda **kwargs: fake_anthropic,
    )
    client = CuratorClient(api_key="test-key")
    result = await client.ask_json("s", "u")
    assert result == {"x": 1}


@pytest.mark.asyncio
async def test_ask_json_raises_on_malformed_json(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="not json at all")]
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "agente10.curator.client.anthropic.AsyncAnthropic",
        lambda **kwargs: fake_anthropic,
    )
    client = CuratorClient(api_key="test-key")
    with pytest.raises(ValueError, match="not valid JSON"):
        await client.ask_json("s", "u")
