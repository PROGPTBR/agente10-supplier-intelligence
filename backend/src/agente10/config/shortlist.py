"""User-facing config that controls shortlist generation for a single upload.

Stored as JSON inside spend_uploads.metadados.shortlist_config. Applied at
pipeline time (in _shortlist_stage) so the curator reranks the right pool —
not just at view time.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ShortlistSize = Literal[10, 20, 50, 100]


class ShortlistConfig(BaseModel):
    size: ShortlistSize = 10
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    municipio: str | None = Field(default=None, min_length=1, max_length=80)
    only_matriz: bool = False
    min_capital: float | None = Field(default=None, ge=0)

    @field_validator("uf")
    @classmethod
    def uf_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else None

    @field_validator("municipio")
    @classmethod
    def municipio_upper(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None


def parse_from_metadados(metadados: dict[str, Any] | None) -> ShortlistConfig:
    """Defaults-friendly extraction. Missing key = ShortlistConfig() (top-10, no filters)."""
    if not metadados:
        return ShortlistConfig()
    raw = metadados.get("shortlist_config")
    if not raw:
        return ShortlistConfig()
    return ShortlistConfig.model_validate(raw)
