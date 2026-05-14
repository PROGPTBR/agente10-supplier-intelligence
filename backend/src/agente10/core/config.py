from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    redis_url: str
    env: Literal["local", "staging", "production"] = "local"

    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3"

    anthropic_api_key: str = ""

    # Comma-separated list of origins allowed by CORS. Defaults to local dev.
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("voyage_api_key", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v or None

    @field_validator("database_url", mode="before")
    @classmethod
    def _ensure_asyncpg_driver(cls, v: str) -> str:
        # Railway/Heroku-style DATABASE_URL uses `postgres://` and omits the
        # asyncpg driver; SQLAlchemy's async engine requires `+asyncpg`.
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://") :]
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
