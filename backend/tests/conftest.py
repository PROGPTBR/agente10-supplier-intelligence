import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(monkeypatch):
    """ASGI client with mocked DB/Redis dependencies."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@x/x")
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("ENV", "local")

    # Import after env is set so Settings() reads our overrides
    from agente10 import main as main_module

    # Patch the engine/redis pingers so the test doesn't need real services
    async def _ok_db_ping() -> str:
        return "ok"

    async def _ok_redis_ping() -> str:
        return "ok"

    monkeypatch.setattr(main_module, "_db_ping", _ok_db_ping)
    monkeypatch.setattr(main_module, "_redis_ping", _ok_redis_ping)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
