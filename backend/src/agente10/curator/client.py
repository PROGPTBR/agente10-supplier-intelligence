"""Thin async wrapper around Anthropic SDK for JSON-output curator calls."""

from __future__ import annotations

import json
import re
from typing import Any

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agente10.core.config import get_settings

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class CuratorClient:
    """Wraps anthropic.AsyncAnthropic for curator calls that return JSON.

    Use ``ask_json`` for structured outputs. Retries 3× on APIConnectionError
    or RateLimitError with exponential backoff (2/4/8s).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=8),
        retry=retry_if_exception_type((anthropic.APIConnectionError, anthropic.RateLimitError)),
        reraise=True,
    )
    async def ask_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
    ) -> Any:
        """Send a single user message and parse the response body as JSON."""
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text.strip()
        fence = _FENCE_RE.match(text)
        if fence:
            text = fence.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"curator response not valid JSON: {text[:200]!r}") from exc
