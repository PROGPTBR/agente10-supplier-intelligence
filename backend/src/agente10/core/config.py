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

    @field_validator("voyage_api_key", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v or None


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
