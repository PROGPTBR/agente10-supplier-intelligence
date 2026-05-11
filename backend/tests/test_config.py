import os

from agente10.core.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ENV", "local")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
    assert settings.redis_url == "redis://h:6379/0"
    assert settings.env == "local"


def test_settings_env_defaults_to_local(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.delenv("ENV", raising=False)

    settings = Settings()

    assert settings.env == "local"
