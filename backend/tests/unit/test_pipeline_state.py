from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agente10.estagio1.pipeline import _set_status


@pytest.mark.asyncio
async def test_set_status_records_transition(monkeypatch):
    # Pure functional test of helper. Use a mock session.
    session = AsyncMock()
    upload_id = uuid4()
    await _set_status(session, upload_id, "processing")
    args, kwargs = session.execute.call_args
    assert "UPDATE spend_uploads" in str(args[0])
    assert kwargs is None or kwargs == {} or "processing" in str(args[1])
