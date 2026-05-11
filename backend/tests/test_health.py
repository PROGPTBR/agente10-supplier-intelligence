import pytest


@pytest.mark.asyncio
async def test_health_returns_ok_when_deps_up(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_health_returns_503_when_db_down(client, monkeypatch):
    from agente10 import main as main_module

    async def _fail_db() -> str:
        return "error: connection refused"

    monkeypatch.setattr(main_module, "_db_ping", _fail_db)

    r = await client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "error"
    assert body["db"].startswith("error")
    assert body["redis"] == "ok"
