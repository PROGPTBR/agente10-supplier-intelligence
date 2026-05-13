# Sprint 2 — Estágio 1 (catálogo) + Estágio 3: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first vertical product slice: CSV catalog upload → cluster lines → assign CNAE per cluster → generate top-10 supplier shortlist per cluster. End-to-end async pipeline with REST + CLI surfaces.

**Architecture:** FastAPI BackgroundTask runs a 5-stage pipeline (parse → cluster → cnae → shortlist → denorm). Hybrid clustering (agrupamento field if present, HDBSCAN embeddings otherwise). Hybrid CNAE assignment (retrieval if sim≥0.85, Claude Haiku curator if 0.60-0.85, manual_pending if <0.60). Shortlist via Claude Haiku rerank of `find_empresas_by_cnae(25)` → top-10.

**Tech Stack:** FastAPI + asyncpg + voyage-3 + Claude Haiku 4.5 (anthropic SDK) + HDBSCAN + scikit-learn (TF-IDF) + openpyxl + chardet. Reuses Sprint 1.1 `tenant_context`, Sprint 1.2 `find_empresas_by_cnae`, Sprint 1.3 `top_k_cnaes` + `VoyageClient`.

**Spec:** [`docs/superpowers/specs/2026-05-13-sprint2-estagio1-design.md`](../specs/2026-05-13-sprint2-estagio1-design.md)

---

## Task 1: Migration 0007 + dependencies

**Files:**
- Create: `backend/alembic/versions/0007_spend_clusters_shortlist_flag.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Create migration file**

```python
"""empresas: spend_clusters.shortlist_gerada idempotency flag

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spend_clusters",
        sa.Column(
            "shortlist_gerada",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("spend_clusters", "shortlist_gerada")
```

- [ ] **Step 2: Add runtime deps to pyproject.toml**

Add to `[project] dependencies`:

```toml
    "anthropic>=0.39",
    "hdbscan>=0.8.40",
    "scikit-learn>=1.5",
    "chardet>=5.2",
    "openpyxl>=3.1",
```

Note: openpyxl is currently dev-only; move it (or add to main).

- [ ] **Step 3: Sync deps + apply migration**

```bash
docker compose run --rm backend uv sync
make migrate
```

Expected: alembic ends with `Running upgrade 0006 -> 0007`.

- [ ] **Step 4: Verify column exists**

```bash
docker exec agente-supplierdiscovery-postgres-1 psql -U agente10 -d agente10 -c \
  "\d spend_clusters" | grep shortlist_gerada
```

Expected: `shortlist_gerada | boolean | not null default false`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0007_spend_clusters_shortlist_flag.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(backend): migration 0007 + sprint 2 deps (anthropic/hdbscan/sklearn/chardet/openpyxl)"
```

---

## Task 2: CSV parser

**Files:**
- Create: `backend/src/agente10/estagio1/__init__.py` (empty marker)
- Create: `backend/src/agente10/estagio1/csv_parser.py`
- Test: `backend/tests/unit/test_csv_parser.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_csv_parser.py
import io
from pathlib import Path

import pytest

from agente10.estagio1.csv_parser import (
    CsvParseError,
    ParsedRow,
    parse_catalog_bytes,
)


def test_parses_minimal_csv():
    csv = "descricao_original\nParafuso M8\nGerador a diesel\n".encode("utf-8")
    rows = list(parse_catalog_bytes(csv, "catalogo.csv"))
    assert len(rows) == 2
    assert rows[0].descricao_original == "Parafuso M8"
    assert rows[0].agrupamento is None
    assert rows[0].extras == {}


def test_parses_full_catalog_columns():
    csv = (
        "descricao_original,agrupamento,id_linha_origem,valor_total,obs_cliente\n"
        "Parafuso M8,Parafusos,L1,150.50,Comprar mais\n"
    ).encode("utf-8")
    [row] = list(parse_catalog_bytes(csv, "c.csv"))
    assert row.descricao_original == "Parafuso M8"
    assert row.agrupamento == "Parafusos"
    assert row.id_linha_origem == "L1"
    assert row.valor_total == "150.50"
    assert row.extras == {"obs_cliente": "Comprar mais"}


def test_missing_required_column_raises():
    csv = "agrupamento\nParafusos\n".encode("utf-8")
    with pytest.raises(CsvParseError, match="descricao_original"):
        list(parse_catalog_bytes(csv, "c.csv"))


def test_empty_descricao_raises():
    csv = "descricao_original\n\nParafuso\n".encode("utf-8")
    with pytest.raises(CsvParseError, match="line 2"):
        list(parse_catalog_bytes(csv, "c.csv"))


def test_cp1252_encoding_auto_detected():
    text = "descricao_original\nManutenção\n"
    csv_cp1252 = text.encode("cp1252")
    [row] = list(parse_catalog_bytes(csv_cp1252, "c.csv"))
    assert row.descricao_original == "Manutenção"


def test_xlsx_format(tmp_path: Path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["descricao_original", "agrupamento"])
    ws.append(["Parafuso M8", "Parafusos"])
    xlsx_path = tmp_path / "c.xlsx"
    wb.save(xlsx_path)
    rows = list(parse_catalog_bytes(xlsx_path.read_bytes(), "c.xlsx"))
    assert len(rows) == 1
    assert rows[0].agrupamento == "Parafusos"
```

- [ ] **Step 2: Run test (should fail)**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_csv_parser.py -q
```

Expected: 6 failing tests with `ModuleNotFoundError`.

- [ ] **Step 3: Implement parser**

```python
# backend/src/agente10/estagio1/csv_parser.py
"""Parse client catalog CSV/XLSX into Pydantic ParsedRow objects.

Required column: descricao_original.
Optional columns map 1:1 to spend_linhas fields; unknown columns → extras JSONB.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Any

import chardet
from openpyxl import load_workbook
from pydantic import BaseModel


class CsvParseError(ValueError):
    """Raised when the catalog file is malformed."""


_KNOWN_COLUMNS = {
    "descricao_original",
    "agrupamento",
    "id_linha_origem",
    "fornecedor_atual",
    "cnpj_fornecedor",
    "valor_total",
    "quantidade",
    "uf_solicitante",
    "municipio_solicitante",
    "centro_custo",
    "data_compra",
}


class ParsedRow(BaseModel):
    """One line of the client catalog, ready to insert into spend_linhas."""

    descricao_original: str
    agrupamento: str | None = None
    id_linha_origem: str | None = None
    fornecedor_atual: str | None = None
    cnpj_fornecedor: str | None = None
    valor_total: str | None = None
    quantidade: str | None = None
    uf_solicitante: str | None = None
    municipio_solicitante: str | None = None
    centro_custo: str | None = None
    data_compra: str | None = None
    extras: dict[str, Any] = {}


def _decode(raw: bytes) -> str:
    """Decode bytes using chardet to detect encoding (cp1252/utf-8 mostly)."""
    detection = chardet.detect(raw)
    encoding = detection.get("encoding") or "utf-8"
    try:
        return raw.decode(encoding)
    except (UnicodeDecodeError, LookupError) as exc:
        raise CsvParseError(f"unable to decode file (detected {encoding!r}): {exc}") from exc


def _is_xlsx(filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xlsm"))


def _row_from_dict(line_num: int, raw: dict[str, str]) -> ParsedRow:
    descricao = (raw.get("descricao_original") or "").strip()
    if not descricao:
        raise CsvParseError(f"empty descricao_original at line {line_num}")
    extras = {k: v for k, v in raw.items() if k and k not in _KNOWN_COLUMNS and v}
    known = {k: (v.strip() if isinstance(v, str) else v) or None for k, v in raw.items() if k in _KNOWN_COLUMNS}
    known["descricao_original"] = descricao  # already trimmed
    return ParsedRow(**known, extras=extras)


def _parse_csv_text(text: str) -> Iterator[ParsedRow]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "descricao_original" not in reader.fieldnames:
        raise CsvParseError("missing required column 'descricao_original'")
    for i, raw in enumerate(reader, start=2):  # line 1 = header
        yield _row_from_dict(i, raw)


def _parse_xlsx(data: bytes) -> Iterator[ParsedRow]:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers or "descricao_original" not in headers:
        raise CsvParseError("missing required column 'descricao_original'")
    headers = [str(h) if h is not None else "" for h in headers]
    for i, values in enumerate(rows, start=2):
        raw = {h: ("" if v is None else str(v)) for h, v in zip(headers, values, strict=False)}
        yield _row_from_dict(i, raw)


def parse_catalog_bytes(data: bytes, filename: str) -> Iterator[ParsedRow]:
    """Yield ParsedRow objects from a CSV or XLSX file's raw bytes."""
    if _is_xlsx(filename):
        yield from _parse_xlsx(data)
    else:
        yield from _parse_csv_text(_decode(data))
```

- [ ] **Step 4: Create estagio1 package marker**

```python
# backend/src/agente10/estagio1/__init__.py
"""Estágio 1 (catálogo): parse → cluster → CNAE classification."""
```

- [ ] **Step 5: Run tests, expect 6 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_csv_parser.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/agente10/estagio1/__init__.py backend/src/agente10/estagio1/csv_parser.py backend/tests/unit/test_csv_parser.py
git commit -m "feat(backend): estagio1 csv parser (CSV+XLSX, encoding auto-detect, extras JSONB)"
```

---

## Task 3: Curator client (Anthropic wrapper)

**Files:**
- Create: `backend/src/agente10/curator/__init__.py`
- Create: `backend/src/agente10/curator/client.py`
- Test: `backend/tests/unit/test_curator_client.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_curator_client.py
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
```

- [ ] **Step 2: Run test, expect ModuleNotFoundError**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_curator_client.py -q
```

- [ ] **Step 3: Implement client**

```python
# backend/src/agente10/curator/__init__.py
"""LLM curator clients for CNAE picking and supplier shortlist reranking."""
```

```python
# backend/src/agente10/curator/client.py
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
        retry=retry_if_exception_type(
            (anthropic.APIConnectionError, anthropic.RateLimitError)
        ),
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
```

- [ ] **Step 4: Add anthropic_api_key to settings**

In `backend/src/agente10/core/config.py`, add field to Settings:

```python
    anthropic_api_key: str = ""
```

- [ ] **Step 5: Run tests, expect 3 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_curator_client.py -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/agente10/curator/ backend/src/agente10/core/config.py backend/tests/unit/test_curator_client.py
git commit -m "feat(backend): curator client (anthropic JSON wrapper + 3x retry tenacity)"
```

---

## Task 4: cnae_picker curator

**Files:**
- Create: `backend/src/agente10/curator/cnae_picker.py`
- Test: `backend/tests/unit/test_cnae_picker.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_cnae_picker.py
from unittest.mock import AsyncMock

import pytest

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick, pick_cnae


@pytest.mark.asyncio
async def test_picks_cnae_from_top5():
    candidates = [
        CnaeCandidate(codigo="4744001", denominacao="Comércio ferragens", similarity=0.72),
        CnaeCandidate(codigo="4673700", denominacao="Atacado madeira", similarity=0.68),
        CnaeCandidate(codigo="4674500", denominacao="Atacado material", similarity=0.65),
        CnaeCandidate(codigo="4684201", denominacao="Atacado produtos químicos", similarity=0.62),
        CnaeCandidate(codigo="4789099", denominacao="Comércio varejista diverso", similarity=0.60),
    ]
    client = AsyncMock()
    client.ask_json.return_value = {
        "cnae": "4744001",
        "confidence": 0.88,
        "reasoning": "parafusos são ferragens",
    }
    pick = await pick_cnae(client, "parafusos m8", candidates)
    assert isinstance(pick, CnaePick)
    assert pick.cnae == "4744001"
    assert pick.confidence == 0.88
    assert "parafusos" in pick.reasoning.lower()


@pytest.mark.asyncio
async def test_rejects_cnae_not_in_candidates():
    candidates = [
        CnaeCandidate(codigo="4744001", denominacao="x", similarity=0.7),
    ]
    client = AsyncMock()
    client.ask_json.return_value = {
        "cnae": "9999999",  # not in candidates → should raise
        "confidence": 0.9,
        "reasoning": "",
    }
    with pytest.raises(ValueError, match="not in candidates"):
        await pick_cnae(client, "x", candidates)
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_cnae_picker.py -q
```

- [ ] **Step 3: Implement cnae_picker**

```python
# backend/src/agente10/curator/cnae_picker.py
"""LLM curator: pick the best CNAE for a cluster name from top-K retrieval candidates."""

from __future__ import annotations

from pydantic import BaseModel

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.client import CuratorClient

_SYSTEM = """\
Você é um classificador especialista em CNAE 2.3 brasileira. Dado o nome
de uma categoria de materiais/serviços e até 5 candidatos CNAE, escolha
o mais apropriado e retorne JSON puro no formato:

{"cnae": "<codigo 7 digitos>", "confidence": <0.0-1.0>, "reasoning": "<breve>"}

Regras:
- O cnae escolhido DEVE estar entre os candidatos fornecidos.
- confidence reflete o quanto você está seguro (0.5 = chute educado, 0.9 = óbvio).
- reasoning em 1-2 frases.
"""


class CnaePick(BaseModel):
    """LLM choice over top-K CNAE candidates."""

    cnae: str
    confidence: float
    reasoning: str


def _format_user_prompt(cluster_name: str, candidates: list[CnaeCandidate]) -> str:
    lines = [f"Categoria: {cluster_name}", "", "Candidatos CNAE:"]
    for i, c in enumerate(candidates, start=1):
        lines.append(f"{i}. {c.codigo} — {c.denominacao} (sim={c.similarity:.3f})")
    return "\n".join(lines)


async def pick_cnae(
    client: CuratorClient,
    cluster_name: str,
    candidates: list[CnaeCandidate],
) -> CnaePick:
    """Ask the curator to pick the best CNAE from the candidates."""
    user = _format_user_prompt(cluster_name, candidates)
    raw = await client.ask_json(_SYSTEM, user)
    pick = CnaePick.model_validate(raw)
    valid_codes = {c.codigo for c in candidates}
    if pick.cnae not in valid_codes:
        raise ValueError(f"curator returned cnae {pick.cnae!r} not in candidates {valid_codes}")
    return pick
```

- [ ] **Step 4: Run tests, expect 2 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_cnae_picker.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/curator/cnae_picker.py backend/tests/unit/test_cnae_picker.py
git commit -m "feat(backend): curator cnae_picker (top-K → LLM pick with validation)"
```

---

## Task 5: shortlist_reranker curator

**Files:**
- Create: `backend/src/agente10/curator/shortlist_reranker.py`
- Test: `backend/tests/unit/test_shortlist_reranker.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_shortlist_reranker.py
from datetime import date
from unittest.mock import AsyncMock

import pytest

from agente10.curator.shortlist_reranker import RankedSupplier, rerank_top10
from agente10.empresas.discovery import EmpresaCandidate


def _candidate(cnpj: str, capital: int = 1_000_000) -> EmpresaCandidate:
    return EmpresaCandidate(
        cnpj=cnpj,
        razao_social=f"EMP {cnpj}",
        nome_fantasia=None,
        cnae_primario="4744001",
        primary_match=True,
        uf="SP",
        municipio="Sao Paulo",
        data_abertura=date(2000, 1, 1),
    )


@pytest.mark.asyncio
async def test_reranker_returns_top10_in_order():
    candidates = [_candidate(str(i).zfill(14)) for i in range(25)]
    client = AsyncMock()
    client.ask_json.return_value = [
        {"cnpj": str(i).zfill(14), "rank": i + 1, "reasoning": f"r{i}"}
        for i in range(10)
    ]
    top10 = await rerank_top10(client, "parafusos m8", candidates)
    assert len(top10) == 10
    assert isinstance(top10[0], RankedSupplier)
    assert top10[0].cnpj == "00000000000000"
    assert top10[0].rank == 1
    assert top10[9].rank == 10


@pytest.mark.asyncio
async def test_reranker_validates_all_cnpjs_in_input():
    candidates = [_candidate(str(i).zfill(14)) for i in range(5)]
    client = AsyncMock()
    client.ask_json.return_value = [
        {"cnpj": "99999999999999", "rank": 1, "reasoning": "fake"},
    ]
    with pytest.raises(ValueError, match="not in input candidates"):
        await rerank_top10(client, "x", candidates)
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_shortlist_reranker.py -q
```

- [ ] **Step 3: Implement reranker**

```python
# backend/src/agente10/curator/shortlist_reranker.py
"""LLM curator: rerank find_empresas_by_cnae candidates → top-10."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from agente10.curator.client import CuratorClient
from agente10.empresas.discovery import EmpresaCandidate

_SYSTEM = """\
Você é um especialista em supply chain B2B Brasil. Dado o nome de uma
categoria de materiais/serviços e até 25 fornecedores candidatos
(razão social, capital social, UF, idade), retorne os 10 melhores em
ordem decrescente de relevância como JSON puro:

[
  {"cnpj": "<14 digitos>", "rank": <1-10>, "reasoning": "<breve>"},
  ...
]

Regras:
- Exatamente 10 itens (ou menos se input tem <10).
- Cada cnpj DEVE estar entre os candidatos.
- Priorize fornecedores claramente especializados na categoria, com
  capital social compatível com o ticket esperado.
"""


class RankedSupplier(BaseModel):
    cnpj: str
    rank: int
    reasoning: str


def _format_user_prompt(cluster_name: str, candidates: list[EmpresaCandidate]) -> str:
    today = date.today()
    lines = [f"Categoria: {cluster_name}", "", "Candidatos:"]
    for i, c in enumerate(candidates, start=1):
        idade = (today - c.data_abertura).days // 365 if c.data_abertura else "N/A"
        lines.append(
            f"{i}. {c.cnpj} — {c.razao_social} | UF={c.uf} | idade={idade}a"
        )
    return "\n".join(lines)


async def rerank_top10(
    client: CuratorClient,
    cluster_name: str,
    candidates: list[EmpresaCandidate],
) -> list[RankedSupplier]:
    """Ask curator to rerank to top-10. Returns sorted by rank ascending."""
    user = _format_user_prompt(cluster_name, candidates)
    raw = await client.ask_json(_SYSTEM, user, max_tokens=2048)
    ranked = [RankedSupplier.model_validate(item) for item in raw]
    valid_cnpjs = {c.cnpj for c in candidates}
    bad = [r.cnpj for r in ranked if r.cnpj not in valid_cnpjs]
    if bad:
        raise ValueError(f"reranker returned cnpjs not in input candidates: {bad}")
    return sorted(ranked, key=lambda r: r.rank)
```

- [ ] **Step 4: Run tests, expect 2 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_shortlist_reranker.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/curator/shortlist_reranker.py backend/tests/unit/test_shortlist_reranker.py
git commit -m "feat(backend): curator shortlist_reranker (25→top-10 LLM pick)"
```

---

## Task 6: Clusterizador (hybrid)

**Files:**
- Create: `backend/src/agente10/estagio1/clusterizador.py`
- Test: `backend/tests/unit/test_clusterizador.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_clusterizador.py
from unittest.mock import AsyncMock

import pytest

from agente10.estagio1.clusterizador import ClusterAssignment, cluster_rows
from agente10.estagio1.csv_parser import ParsedRow


def _row(descricao: str, agrupamento: str | None = None) -> ParsedRow:
    return ParsedRow(descricao_original=descricao, agrupamento=agrupamento)


@pytest.mark.asyncio
async def test_agrupamento_groups_preserve_input():
    rows = [
        _row("Parafuso M8", "Parafusos"),
        _row("Parafuso M10", "Parafusos"),
        _row("Gerador 5kVA", "Geradores"),
    ]
    voyage = AsyncMock()
    result = await cluster_rows(rows, voyage)
    cluster_names = sorted(set(a.cluster_name for a in result))
    assert cluster_names == ["geradores", "parafusos"]
    voyage.embed_documents.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_path_used_when_no_agrupamento():
    rows = [
        _row("Parafuso M8"),
        _row("Parafuso M10"),
        _row("Parafuso M12"),
    ]
    voyage = AsyncMock()
    # 3D vectors close together → 1 cluster
    voyage.embed_documents.return_value = [
        [1.0, 0.0, 0.0],
        [0.99, 0.01, 0.0],
        [0.98, 0.02, 0.0],
    ]
    result = await cluster_rows(rows, voyage, min_cluster_size=2)
    assert len(set(a.cluster_name for a in result)) == 1


@pytest.mark.asyncio
async def test_hybrid_handles_mixed_rows():
    rows = [
        _row("Parafuso M8", "Parafusos"),
        _row("Cabo elétrico 2.5mm"),  # no agrupamento → embedding bucket
    ]
    voyage = AsyncMock()
    voyage.embed_documents.return_value = [[1.0, 0.0]]
    result = await cluster_rows(rows, voyage, min_cluster_size=1)
    cluster_names = {a.cluster_name for a in result}
    assert "parafusos" in cluster_names
    assert len(cluster_names) == 2  # agrupamento cluster + 1 noise/singleton
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_clusterizador.py -q
```

- [ ] **Step 3: Implement clusterizador**

```python
# backend/src/agente10/estagio1/clusterizador.py
"""Hybrid clustering: trust client's `agrupamento` field; HDBSCAN on the rest.

Output: one ClusterAssignment per input row. Cluster names come from
agrupamento (lowercased/trimmed) or top-3 TF-IDF terms for embedding clusters.
"""

from __future__ import annotations

from collections.abc import Sequence

import hdbscan
import numpy as np
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer

from agente10.estagio1.csv_parser import ParsedRow
from agente10.integrations.voyage import VoyageClient


class ClusterAssignment(BaseModel):
    """One row → its cluster name (or 'unassigned' if clustering failed)."""

    row_index: int
    cluster_name: str


def _agrupamento_clusters(rows: Sequence[ParsedRow]) -> tuple[list[ClusterAssignment], list[int]]:
    """Return assignments for rows with agrupamento + indices of rows without."""
    assigned: list[ClusterAssignment] = []
    no_agrup: list[int] = []
    for i, row in enumerate(rows):
        if row.agrupamento and row.agrupamento.strip():
            assigned.append(
                ClusterAssignment(row_index=i, cluster_name=row.agrupamento.strip().lower())
            )
        else:
            no_agrup.append(i)
    return assigned, no_agrup


def _tfidf_label(texts: Sequence[str], top_n: int = 3) -> str:
    """Pick the top-N TF-IDF terms across a cluster's descriptions, joined."""
    if not texts:
        return "unnamed"
    if len(texts) == 1:
        return texts[0].strip().lower()[:60]
    vec = TfidfVectorizer(max_features=200, ngram_range=(1, 1), lowercase=True)
    matrix = vec.fit_transform(texts)
    scores = matrix.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    top_idx = scores.argsort()[::-1][:top_n]
    return " ".join(terms[i] for i in top_idx)


async def _embedding_clusters(
    rows: Sequence[ParsedRow],
    indices: Sequence[int],
    voyage: VoyageClient,
    min_cluster_size: int,
) -> list[ClusterAssignment]:
    if not indices:
        return []
    texts = [rows[i].descricao_original for i in indices]
    embeddings = await voyage.embed_documents(texts)
    matrix = np.asarray(embeddings, dtype=np.float32)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=max(min_cluster_size, 2),
        metric="euclidean",  # cosine via pre-normalized vectors
    )
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)  # avoid div-by-zero
    normalized = matrix / norms
    labels = clusterer.fit_predict(normalized)

    # Group row indices by cluster label
    label_to_indices: dict[int, list[int]] = {}
    for local_idx, label in enumerate(labels):
        label_to_indices.setdefault(int(label), []).append(local_idx)

    out: list[ClusterAssignment] = []
    for label, local_indices in label_to_indices.items():
        if label == -1:
            # Noise → each row becomes its own singleton cluster
            for li in local_indices:
                row_idx = indices[li]
                out.append(
                    ClusterAssignment(
                        row_index=row_idx,
                        cluster_name=rows[row_idx].descricao_original.strip().lower()[:60],
                    )
                )
        else:
            texts_for_label = [rows[indices[li]].descricao_original for li in local_indices]
            name = _tfidf_label(texts_for_label)
            for li in local_indices:
                out.append(ClusterAssignment(row_index=indices[li], cluster_name=name))
    return out


async def cluster_rows(
    rows: Sequence[ParsedRow],
    voyage: VoyageClient,
    min_cluster_size: int = 3,
) -> list[ClusterAssignment]:
    """Hybrid: agrupamento path + HDBSCAN embedding path. Returns 1 assignment per row."""
    assigned, no_agrup = _agrupamento_clusters(rows)
    embedded = await _embedding_clusters(rows, no_agrup, voyage, min_cluster_size)
    return sorted(assigned + embedded, key=lambda a: a.row_index)
```

- [ ] **Step 4: Run tests, expect 3 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_clusterizador.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/estagio1/clusterizador.py backend/tests/unit/test_clusterizador.py
git commit -m "feat(backend): estagio1 clusterizador (hybrid agrupamento + HDBSCAN+TF-IDF)"
```

---

## Task 7: Classificador CNAE (3-path)

**Files:**
- Create: `backend/src/agente10/estagio1/classificador_cnae.py`
- Test: `backend/tests/unit/test_classificador_cnae.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_classificador_cnae.py
from unittest.mock import AsyncMock

import pytest

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.estagio1.classificador_cnae import (
    ClassificationResult,
    classify_cluster,
)


def _candidates(top_sim: float) -> list[CnaeCandidate]:
    return [
        CnaeCandidate(codigo="4744001", denominacao="x", similarity=top_sim),
        CnaeCandidate(codigo="4673700", denominacao="y", similarity=top_sim - 0.05),
        CnaeCandidate(codigo="4674500", denominacao="z", similarity=top_sim - 0.10),
        CnaeCandidate(codigo="4684201", denominacao="w", similarity=top_sim - 0.15),
        CnaeCandidate(codigo="4789099", denominacao="v", similarity=top_sim - 0.20),
    ]


@pytest.mark.asyncio
async def test_auto_path_when_top_similarity_high():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.90))
    curator = AsyncMock()
    result = await classify_cluster(
        "parafusos", voyage=voyage, retrieval=retrieval, curator_pick=curator,
    )
    assert isinstance(result, ClassificationResult)
    assert result.cnae == "4744001"
    assert result.cnae_metodo == "retrieval"
    assert result.cnae_confianca == pytest.approx(0.90)
    curator.assert_not_called()


@pytest.mark.asyncio
async def test_curator_path_when_medium_similarity():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.75))
    curator = AsyncMock(return_value=CnaePick(cnae="4673700", confidence=0.85, reasoning="x"))
    result = await classify_cluster(
        "atacado madeira", voyage=voyage, retrieval=retrieval, curator_pick=curator,
    )
    assert result.cnae == "4673700"
    assert result.cnae_metodo == "curator"
    assert result.cnae_confianca == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_curator_fallback_uses_retrieval_top1():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.75))
    curator = AsyncMock(side_effect=RuntimeError("api down"))
    result = await classify_cluster(
        "x", voyage=voyage, retrieval=retrieval, curator_pick=curator,
    )
    assert result.cnae == "4744001"
    assert result.cnae_metodo == "retrieval_fallback"


@pytest.mark.asyncio
async def test_manual_pending_when_low_similarity():
    voyage = AsyncMock()
    voyage.embed_query.return_value = [0.1] * 1024
    retrieval = AsyncMock(return_value=_candidates(0.50))
    curator = AsyncMock()
    result = await classify_cluster(
        "totally ambiguous", voyage=voyage, retrieval=retrieval, curator_pick=curator,
    )
    assert result.cnae == "4744001"
    assert result.cnae_metodo == "manual_pending"
    assert result.cnae_confianca == pytest.approx(0.50)
    curator.assert_not_called()
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_classificador_cnae.py -q
```

- [ ] **Step 3: Implement classificador_cnae**

```python
# backend/src/agente10/estagio1/classificador_cnae.py
"""Hybrid CNAE classification: retrieval / curator / manual_pending."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.integrations.voyage import VoyageClient

AUTO_THRESHOLD = 0.85
CURATOR_THRESHOLD = 0.60


class ClassificationResult(BaseModel):
    cnae: str
    cnae_confianca: float
    cnae_metodo: str  # 'retrieval' | 'curator' | 'retrieval_fallback' | 'manual_pending'


CandidatesFn = Callable[[list[float]], Awaitable[list[CnaeCandidate]]]
CuratorPickFn = Callable[[str, list[CnaeCandidate]], Awaitable[CnaePick]]


async def classify_cluster(
    cluster_name: str,
    *,
    voyage: VoyageClient,
    retrieval: CandidatesFn,
    curator_pick: CuratorPickFn,
) -> ClassificationResult:
    """Classify one cluster following the three-path rule.

    - top_sim ≥ 0.85 → retrieval top-1, method='retrieval'
    - 0.60 ≤ top_sim < 0.85 → LLM curator picks from top-5, method='curator'
        (on curator failure, falls back to retrieval top-1, method='retrieval_fallback')
    - top_sim < 0.60 → retrieval top-1 + flag manual_pending
    """
    embedding = await voyage.embed_query(cluster_name)
    candidates = await retrieval(embedding)
    if not candidates:
        raise RuntimeError("retrieval returned 0 candidates — taxonomy not loaded?")

    top = candidates[0]
    top_sim = top.similarity

    if top_sim >= AUTO_THRESHOLD:
        return ClassificationResult(
            cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="retrieval"
        )

    if top_sim >= CURATOR_THRESHOLD:
        try:
            pick = await curator_pick(cluster_name, candidates)
            return ClassificationResult(
                cnae=pick.cnae, cnae_confianca=pick.confidence, cnae_metodo="curator"
            )
        except Exception:
            return ClassificationResult(
                cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="retrieval_fallback"
            )

    return ClassificationResult(
        cnae=top.codigo, cnae_confianca=top_sim, cnae_metodo="manual_pending"
    )
```

- [ ] **Step 4: Run tests, expect 4 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_classificador_cnae.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/estagio1/classificador_cnae.py backend/tests/unit/test_classificador_cnae.py
git commit -m "feat(backend): estagio1 classificador_cnae (3-path: retrieval/curator/manual_pending)"
```

---

## Task 8: Shortlist generator (Estágio 3)

**Files:**
- Create: `backend/src/agente10/estagio3/__init__.py`
- Create: `backend/src/agente10/estagio3/shortlist_generator.py`
- Test: `backend/tests/unit/test_shortlist_generator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_shortlist_generator.py
from datetime import date
from unittest.mock import AsyncMock

import pytest

from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.empresas.discovery import EmpresaCandidate
from agente10.estagio3.shortlist_generator import (
    ShortlistEntry,
    generate_shortlist,
)


def _emp(cnpj: str) -> EmpresaCandidate:
    return EmpresaCandidate(
        cnpj=cnpj, razao_social="x", nome_fantasia=None,
        cnae_primario="4744001", primary_match=True,
        uf="SP", municipio="Sao Paulo", data_abertura=date(2000, 1, 1),
    )


@pytest.mark.asyncio
async def test_uses_curator_rerank_when_available():
    discovery = AsyncMock(return_value=[_emp(str(i).zfill(14)) for i in range(25)])
    rerank = AsyncMock(return_value=[
        RankedSupplier(cnpj=str(9 - i).zfill(14), rank=i + 1, reasoning="x")
        for i in range(10)
    ])
    result = await generate_shortlist(
        "parafusos", "4744001", discovery=discovery, rerank=rerank,
    )
    assert len(result) == 10
    assert isinstance(result[0], ShortlistEntry)
    assert result[0].cnpj == "00000000000009"
    assert result[0].rank_estagio3 == 1


@pytest.mark.asyncio
async def test_falls_back_to_helper_order_on_rerank_failure():
    discovery = AsyncMock(return_value=[_emp(str(i).zfill(14)) for i in range(25)])
    rerank = AsyncMock(side_effect=RuntimeError("api down"))
    result = await generate_shortlist(
        "x", "4744001", discovery=discovery, rerank=rerank,
    )
    assert len(result) == 10
    assert result[0].cnpj == "00000000000000"
    assert result[0].rank_estagio3 == 1
    assert result[9].rank_estagio3 == 10
```

- [ ] **Step 2: Run test, expect ImportError**

- [ ] **Step 3: Implement shortlist_generator**

```python
# backend/src/agente10/estagio3/__init__.py
"""Estágio 3: per-cluster supplier shortlist via discovery + curator rerank."""
```

```python
# backend/src/agente10/estagio3/shortlist_generator.py
"""Estágio 3: per cluster (cnae) → top-10 supplier shortlist."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.empresas.discovery import EmpresaCandidate

SHORTLIST_SIZE = 10
RETRIEVAL_POOL = 25

DiscoveryFn = Callable[[str], Awaitable[list[EmpresaCandidate]]]
RerankFn = Callable[[str, list[EmpresaCandidate]], Awaitable[list[RankedSupplier]]]


class ShortlistEntry(BaseModel):
    cnpj: str
    rank_estagio3: int


async def generate_shortlist(
    cluster_name: str,
    cnae: str,
    *,
    discovery: DiscoveryFn,
    rerank: RerankFn,
) -> list[ShortlistEntry]:
    """Return top-10 supplier shortlist. Curator rerank with fallback to helper order."""
    candidates = await discovery(cnae)
    if not candidates:
        return []
    try:
        ranked = await rerank(cluster_name, candidates)
        return [
            ShortlistEntry(cnpj=r.cnpj, rank_estagio3=r.rank)
            for r in ranked[:SHORTLIST_SIZE]
        ]
    except Exception:
        return [
            ShortlistEntry(cnpj=c.cnpj, rank_estagio3=i + 1)
            for i, c in enumerate(candidates[:SHORTLIST_SIZE])
        ]
```

- [ ] **Step 4: Run tests, expect 2 passing**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_shortlist_generator.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/estagio3/ backend/tests/unit/test_shortlist_generator.py
git commit -m "feat(backend): estagio3 shortlist_generator (curator rerank + fallback)"
```

---

## Task 9: Pipeline orchestrator

**Files:**
- Create: `backend/src/agente10/estagio1/pipeline.py`
- Test: `backend/tests/integration/test_pipeline_e2e.py`
- Test: `backend/tests/unit/test_pipeline_state.py`

- [ ] **Step 1: Write unit test for state transitions**

```python
# backend/tests/unit/test_pipeline_state.py
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from agente10.estagio1.pipeline import _set_status


@pytest.mark.asyncio
async def test_set_status_records_transition(monkeypatch):
    # Pure functional test of helper. Use a mock session.
    from unittest.mock import AsyncMock

    session = AsyncMock()
    upload_id = uuid4()
    await _set_status(session, upload_id, "processing")
    args, kwargs = session.execute.call_args
    assert "UPDATE spend_uploads" in str(args[0])
    assert kwargs is None or kwargs == {} or "processing" in str(args[1])
```

- [ ] **Step 2: Run unit test, expect ImportError**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_pipeline_state.py -q
```

- [ ] **Step 3: Implement pipeline.py**

```python
# backend/src/agente10/estagio1/pipeline.py
"""Estágio 1 + Estágio 3 orchestrator.

Drives spend_uploads.status: pending → processing → done|failed.
Each stage commits independently for idempotent re-run.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agente10.cnae.retrieval import top_k_cnaes
from agente10.core.tenancy import tenant_context
from agente10.curator.client import CuratorClient
from agente10.curator.cnae_picker import pick_cnae
from agente10.curator.shortlist_reranker import rerank_top10
from agente10.empresas.discovery import find_empresas_by_cnae
from agente10.estagio1.classificador_cnae import classify_cluster
from agente10.estagio1.clusterizador import cluster_rows
from agente10.estagio1.csv_parser import parse_catalog_bytes
from agente10.estagio3.shortlist_generator import generate_shortlist
from agente10.integrations.voyage import VoyageClient

log = logging.getLogger(__name__)


async def _set_status(
    session: AsyncSession,
    upload_id: UUID,
    status: str,
    erro: str | None = None,
) -> None:
    await session.execute(
        text(
            "UPDATE spend_uploads SET status = :s, erro = :e WHERE id = :id"
        ),
        {"s": status, "e": erro, "id": str(upload_id)},
    )


async def _parse_stage(
    session: AsyncSession, upload_id: UUID, tenant_id: UUID, csv_path: Path
) -> int:
    existing = await session.scalar(
        text("SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u"),
        {"u": str(upload_id)},
    )
    if existing and existing > 0:
        log.info("parse stage: %d rows already present, skipping", existing)
        return int(existing)

    raw = csv_path.read_bytes()
    rows = list(parse_catalog_bytes(raw, csv_path.name))
    for row in rows:
        await session.execute(
            text(
                """
                INSERT INTO spend_linhas (
                    tenant_id, upload_id, descricao_original, agrupamento,
                    id_linha_origem, fornecedor_atual, cnpj_fornecedor,
                    valor_total, quantidade, uf_solicitante, municipio_solicitante,
                    centro_custo, data_compra, extras
                ) VALUES (
                    :t, :u, :d, :a, :ilo, :fa, :cf, :v, :q, :uf, :m, :cc, :dc, CAST(:ex AS jsonb)
                )
                """
            ),
            {
                "t": str(tenant_id),
                "u": str(upload_id),
                "d": row.descricao_original,
                "a": row.agrupamento,
                "ilo": row.id_linha_origem,
                "fa": row.fornecedor_atual,
                "cf": row.cnpj_fornecedor,
                "v": row.valor_total,
                "q": row.quantidade,
                "uf": row.uf_solicitante,
                "m": row.municipio_solicitante,
                "cc": row.centro_custo,
                "dc": row.data_compra,
                "ex": __import__("json").dumps(row.extras),
            },
        )
    await session.execute(
        text("UPDATE spend_uploads SET linhas_total = :n WHERE id = :u"),
        {"n": len(rows), "u": str(upload_id)},
    )
    return len(rows)


async def _cluster_stage(
    session: AsyncSession,
    upload_id: UUID,
    tenant_id: UUID,
    voyage: VoyageClient,
) -> None:
    existing = await session.scalar(
        text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u"),
        {"u": str(upload_id)},
    )
    if existing and existing > 0:
        log.info("cluster stage: %d clusters already exist, skipping", existing)
        return

    result = await session.execute(
        text(
            "SELECT id, descricao_original, agrupamento "
            "FROM spend_linhas WHERE upload_id = :u ORDER BY id"
        ),
        {"u": str(upload_id)},
    )
    rows = result.all()

    from agente10.estagio1.csv_parser import ParsedRow

    parsed = [
        ParsedRow(descricao_original=r.descricao_original, agrupamento=r.agrupamento)
        for r in rows
    ]
    assignments = await cluster_rows(parsed, voyage)

    name_to_cluster_id: dict[str, str] = {}
    for assignment in assignments:
        name = assignment.cluster_name
        if name not in name_to_cluster_id:
            row = await session.execute(
                text(
                    "INSERT INTO spend_clusters (tenant_id, upload_id, nome_cluster, num_linhas) "
                    "VALUES (:t, :u, :n, 0) RETURNING id"
                ),
                {"t": str(tenant_id), "u": str(upload_id), "n": name},
            )
            name_to_cluster_id[name] = str(row.scalar())
        cluster_id = name_to_cluster_id[name]
        await session.execute(
            text("UPDATE spend_linhas SET cluster_id = :c WHERE id = :i"),
            {"c": cluster_id, "i": str(rows[assignment.row_index].id)},
        )

    await session.execute(
        text(
            "UPDATE spend_clusters SET num_linhas = sub.cnt "
            "FROM (SELECT cluster_id, COUNT(*) AS cnt FROM spend_linhas "
            "      WHERE upload_id = :u GROUP BY cluster_id) sub "
            "WHERE spend_clusters.id = sub.cluster_id"
        ),
        {"u": str(upload_id)},
    )


async def _cnae_stage(
    session: AsyncSession,
    upload_id: UUID,
    voyage: VoyageClient,
    curator: CuratorClient,
) -> None:
    result = await session.execute(
        text(
            "SELECT id, nome_cluster FROM spend_clusters "
            "WHERE upload_id = :u AND cnae IS NULL"
        ),
        {"u": str(upload_id)},
    )
    clusters = result.all()
    for c in clusters:
        outcome = await classify_cluster(
            c.nome_cluster,
            voyage=voyage,
            retrieval=lambda emb: top_k_cnaes(session, emb, k=5),
            curator_pick=partial(pick_cnae, curator),
        )
        await session.execute(
            text(
                "UPDATE spend_clusters SET cnae=:cnae, cnae_confianca=:c, cnae_metodo=:m "
                "WHERE id=:i"
            ),
            {
                "cnae": outcome.cnae,
                "c": outcome.cnae_confianca,
                "m": outcome.cnae_metodo,
                "i": str(c.id),
            },
        )


async def _shortlist_stage(
    session: AsyncSession,
    tenant_id: UUID,
    upload_id: UUID,
    curator: CuratorClient,
) -> None:
    result = await session.execute(
        text(
            "SELECT id, nome_cluster, cnae FROM spend_clusters "
            "WHERE upload_id = :u AND cnae IS NOT NULL AND shortlist_gerada = false"
        ),
        {"u": str(upload_id)},
    )
    clusters = result.all()
    for c in clusters:
        entries = await generate_shortlist(
            c.nome_cluster,
            c.cnae,
            discovery=lambda cnae: find_empresas_by_cnae(session, cnae, limit=25),
            rerank=partial(rerank_top10, curator),
        )
        for entry in entries:
            await session.execute(
                text(
                    "INSERT INTO supplier_shortlists "
                    "(tenant_id, cnae, cnpj_fornecedor, rank_estagio3) "
                    "VALUES (:t, :cnae, :cnpj, :r)"
                ),
                {
                    "t": str(tenant_id),
                    "cnae": c.cnae,
                    "cnpj": entry.cnpj,
                    "r": entry.rank_estagio3,
                },
            )
        await session.execute(
            text("UPDATE spend_clusters SET shortlist_gerada = true WHERE id = :i"),
            {"i": str(c.id)},
        )


async def _denorm_stage(session: AsyncSession, upload_id: UUID) -> None:
    await session.execute(
        text(
            "UPDATE spend_linhas SET "
            "  cnae = c.cnae, "
            "  cnae_confianca = c.cnae_confianca, "
            "  cnae_metodo = c.cnae_metodo "
            "FROM spend_clusters c "
            "WHERE spend_linhas.cluster_id = c.id AND spend_linhas.upload_id = :u"
        ),
        {"u": str(upload_id)},
    )
    await session.execute(
        text(
            "UPDATE spend_uploads SET linhas_classificadas = "
            "(SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u AND cnae IS NOT NULL) "
            "WHERE id = :u"
        ),
        {"u": str(upload_id)},
    )


async def processar_upload(
    upload_id: UUID,
    tenant_id: UUID,
    csv_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    voyage: VoyageClient,
    curator: CuratorClient,
) -> None:
    """Run the full Estágio 1 + Estágio 3 pipeline for one upload."""
    stages = [
        ("parse", _parse_stage, (upload_id, tenant_id, csv_path)),
        ("cluster", _cluster_stage, (upload_id, tenant_id, voyage)),
        ("cnae", _cnae_stage, (upload_id, voyage, curator)),
        ("shortlist", _shortlist_stage, (tenant_id, upload_id, curator)),
        ("denorm", _denorm_stage, (upload_id,)),
    ]
    async with session_factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await _set_status(session, upload_id, "processing")

    try:
        for name, fn, args in stages:
            log.info("pipeline upload=%s stage=%s starting", upload_id, name)
            async with session_factory() as session, session.begin():
                async with tenant_context(session, tenant_id):
                    await fn(session, *args)

        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                await _set_status(session, upload_id, "done")
    except Exception:
        log.exception("pipeline upload=%s failed", upload_id)
        async with session_factory() as session, session.begin():
            async with tenant_context(session, tenant_id):
                await _set_status(session, upload_id, "failed", erro=traceback.format_exc()[:4000])
```

- [ ] **Step 4: Run unit test, expect pass**

```bash
docker compose run --rm backend uv run pytest backend/tests/unit/test_pipeline_state.py -q
```

- [ ] **Step 5: Write E2E integration test**

```python
# backend/tests/integration/test_pipeline_e2e.py
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.empresas.discovery import EmpresaCandidate
from agente10.estagio1.pipeline import processar_upload

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested]


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> Path:
    csv_text = (
        "descricao_original,agrupamento\n"
        "Parafuso M8,Parafusos\n"
        "Parafuso M10,Parafusos\n"
        "Gerador 5kVA,Geradores\n"
        "Cabo elétrico 2.5mm\n"
        "Cabo elétrico 4mm\n"
    )
    p = tmp_path / "catalogo.csv"
    p.write_text(csv_text, encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_e2e_pipeline_populates_all_tables(
    db_engine, two_tenants, synthetic_csv, monkeypatch
):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    voyage = AsyncMock()
    voyage.embed_query.side_effect = lambda t: [0.1] * 1024  # 1024-d
    voyage.embed_documents.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]

    curator = AsyncMock()
    # CNAE picker returns the first candidate's code (whatever it is)
    async def fake_pick(name, cands):
        return CnaePick(cnae=cands[0].codigo, confidence=0.9, reasoning="x")
    async def fake_rerank(name, cands):
        return [RankedSupplier(cnpj=c.cnpj, rank=i+1, reasoning="x")
                for i, c in enumerate(cands[:10])]
    monkeypatch.setattr("agente10.estagio1.pipeline.pick_cnae", fake_pick)
    monkeypatch.setattr("agente10.estagio1.pipeline.rerank_top10", fake_rerank)

    tenant_id, _ = two_tenants
    upload_id = uuid.uuid4()

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, object_storage_path) "
                "VALUES (:i, :t, :n, :p)"
            ),
            {"i": str(upload_id), "t": str(tenant_id),
             "n": "catalogo.csv", "p": str(synthetic_csv)},
        )

    await processar_upload(
        upload_id=upload_id, tenant_id=tenant_id, csv_path=synthetic_csv,
        session_factory=factory, voyage=voyage, curator=curator,
    )

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        status = await session.scalar(
            text("SELECT status FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
        linhas = await session.scalar(
            text("SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u"),
            {"u": str(upload_id)},
        )
        clusters = await session.scalar(
            text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u AND cnae IS NOT NULL"),
            {"u": str(upload_id)},
        )
        shortlist = await session.scalar(
            text(
                "SELECT COUNT(*) FROM supplier_shortlists s "
                "JOIN spend_clusters c ON c.cnae = s.cnae "
                "WHERE c.upload_id = :u AND c.tenant_id = :t"
            ),
            {"u": str(upload_id), "t": str(tenant_id)},
        )
        denormed = await session.scalar(
            text(
                "SELECT COUNT(*) FROM spend_linhas "
                "WHERE upload_id = :u AND cnae IS NOT NULL"
            ),
            {"u": str(upload_id)},
        )

    assert status == "done"
    assert linhas == 5
    assert clusters >= 2  # Parafusos, Geradores (Cabo elétrico bucket may merge or split)
    assert shortlist >= 10
    assert denormed == 5
```

- [ ] **Step 6: Run E2E test (requires rf_ingested + Voyage already populated)**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest backend/tests/integration/test_pipeline_e2e.py -v
```

Expected: PASSED

- [ ] **Step 7: Commit**

```bash
git add backend/src/agente10/estagio1/pipeline.py backend/tests/unit/test_pipeline_state.py backend/tests/integration/test_pipeline_e2e.py
git commit -m "feat(backend): pipeline orchestrator (5 stages, per-stage txn, status state machine)"
```

---

## Task 10: API + CLI

**Files:**
- Create: `backend/src/agente10/api/uploads.py`
- Modify: `backend/src/agente10/api/__init__.py` (register router)
- Create: `backend/scripts/run_pipeline.py`
- Test: `backend/tests/integration/test_api_uploads.py`

- [ ] **Step 1: Write failing integration test for API**

```python
# backend/tests/integration/test_api_uploads.py
import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_post_upload_returns_202_and_id(db_engine, two_tenants):
    from agente10 import main as main_module
    tenant_id, _ = two_tenants

    csv_bytes = b"descricao_original\nParafuso M8\n"
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/uploads",
            files={"file": ("c.csv", csv_bytes, "text/csv")},
            data={"nome_arquivo": "c.csv"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "upload_id" in body
    assert body["status"] == "pending"

    # Cleanup
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": body["upload_id"]},
        )


@pytest.mark.asyncio
async def test_get_upload_returns_status(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(text("DELETE FROM spend_uploads WHERE id = :u"), {"u": str(upload_id)})
```

- [ ] **Step 2: Implement uploads API**

```python
# backend/src/agente10/api/uploads.py
"""REST endpoints for spend upload lifecycle."""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import text

from agente10.core.config import get_settings
from agente10.core.db import get_session_factory
from agente10.core.tenancy import tenant_context
from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.integrations.voyage import VoyageClient

router = APIRouter(prefix="/api/v1", tags=["uploads"])

MAX_BYTES = 50 * 1024 * 1024


async def get_tenant_id(x_tenant_id: str = Header(...)) -> UUID:
    try:
        return UUID(x_tenant_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "invalid X-Tenant-ID") from exc


class UploadCreated(BaseModel):
    upload_id: UUID
    status: str


class UploadStatus(BaseModel):
    upload_id: UUID
    status: str
    linhas_total: int
    linhas_classificadas: int
    erro: str | None


@router.post("/uploads", response_model=UploadCreated, status_code=202)
async def create_upload(
    background: BackgroundTasks,
    tenant_id: UUID = Depends(get_tenant_id),
    file: UploadFile = File(...),
    nome_arquivo: str = Form(...),
    modo: str = Form("catalogo"),
) -> UploadCreated:
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file too large (>50MB)")

    upload_id = uuid.uuid4()
    settings = get_settings()
    storage_dir = Path("/app/data/uploads") / str(tenant_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{upload_id}{Path(nome_arquivo).suffix}"
    storage_path.write_bytes(raw)

    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await session.execute(
                text(
                    "INSERT INTO spend_uploads "
                    "(id, tenant_id, nome_arquivo, object_storage_path, modo, status) "
                    "VALUES (:i, :t, :n, :p, :m, 'pending')"
                ),
                {
                    "i": str(upload_id),
                    "t": str(tenant_id),
                    "n": nome_arquivo,
                    "p": str(storage_path),
                    "m": modo,
                },
            )

    voyage = VoyageClient()
    curator = CuratorClient()
    background.add_task(
        processar_upload,
        upload_id, tenant_id, storage_path, factory, voyage, curator,
    )
    return UploadCreated(upload_id=upload_id, status="pending")


@router.get("/uploads/{upload_id}", response_model=UploadStatus)
async def get_upload(
    upload_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
) -> UploadStatus:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            row = await session.execute(
                text(
                    "SELECT id, status, linhas_total, linhas_classificadas, erro "
                    "FROM spend_uploads WHERE id = :u"
                ),
                {"u": str(upload_id)},
            )
            r = row.first()
    if not r:
        raise HTTPException(404, "upload not found")
    return UploadStatus(
        upload_id=r.id,
        status=r.status,
        linhas_total=r.linhas_total,
        linhas_classificadas=r.linhas_classificadas,
        erro=r.erro,
    )
```

- [ ] **Step 3: Register router in main app**

In `backend/src/agente10/main.py`, add:

```python
from agente10.api.uploads import router as uploads_router
app.include_router(uploads_router)
```

(If `get_session_factory` doesn't exist in `core/db.py`, add it as a thin wrapper around `async_sessionmaker(engine, expire_on_commit=False)`. Verify before editing.)

- [ ] **Step 4: Create CLI**

```python
# backend/scripts/run_pipeline.py
"""CLI to run the full Estágio 1+3 pipeline against a local CSV file.

Usage:
    docker exec agente-supplierdiscovery-backend-1 sh -c \\
        "cd /app && uv run python scripts/run_pipeline.py \\
        --csv tests/fixtures/catalogo_sintetico.csv \\
        --tenant <uuid> --nome 'Catálogo teste'"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agente10.core.tenancy import tenant_context
from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.integrations.voyage import VoyageClient


async def main(args: argparse.Namespace) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    engine = create_async_engine(db_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    tenant_id = uuid.UUID(args.tenant)
    upload_id = uuid.uuid4()
    src = Path(args.csv).resolve()
    if not src.exists():
        print(f"CSV not found: {src}", file=sys.stderr)
        return 2

    storage_dir = Path("/app/data/uploads") / str(tenant_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dst = storage_dir / f"{upload_id}{src.suffix}"
    shutil.copy(src, dst)

    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await session.execute(
                text(
                    "INSERT INTO spend_uploads "
                    "(id, tenant_id, nome_arquivo, object_storage_path, status) "
                    "VALUES (:i, :t, :n, :p, 'pending')"
                ),
                {
                    "i": str(upload_id), "t": str(tenant_id),
                    "n": args.nome, "p": str(dst),
                },
            )
    print(f"upload_id = {upload_id}")
    await processar_upload(
        upload_id=upload_id, tenant_id=tenant_id, csv_path=dst,
        session_factory=factory,
        voyage=VoyageClient(), curator=CuratorClient(),
    )

    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            row = await session.execute(
                text(
                    "SELECT status, linhas_total, linhas_classificadas, "
                    "(SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u) AS clusters, "
                    "(SELECT COUNT(*) FROM supplier_shortlists s "
                    "  WHERE s.cnae IN (SELECT cnae FROM spend_clusters c "
                    "                    WHERE c.upload_id = :u)) AS shortlists "
                    "FROM spend_uploads WHERE id = :u"
                ),
                {"u": str(upload_id)},
            )
            summary = row.one()
    print(
        f"Done: status={summary.status} "
        f"linhas={summary.linhas_total} classificadas={summary.linhas_classificadas} "
        f"clusters={summary.clusters} shortlists={summary.shortlists}"
    )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--nome", default="CLI upload")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
```

- [ ] **Step 5: Run all 2 API tests**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest backend/tests/integration/test_api_uploads.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/agente10/api/uploads.py backend/src/agente10/main.py backend/scripts/run_pipeline.py backend/tests/integration/test_api_uploads.py
git commit -m "feat(backend): api uploads (POST/GET) + CLI run_pipeline.py"
```

---

## Task 11: Synthetic fixture + golden recall

**Files:**
- Create: `backend/tests/fixtures/catalogo_sintetico.csv`
- Create: `backend/tests/fixtures/catalogo_golden.csv`
- Create: `backend/tests/integration/test_pipeline_recall_golden.py`

- [ ] **Step 1: Create synthetic 50-row CSV**

```csv
# backend/tests/fixtures/catalogo_sintetico.csv
descricao_original,agrupamento
Parafuso sextavado M8,Parafusos
Parafuso allen M10,Parafusos
Parafuso phillips M6,Parafusos
Porca sextavada M8,Parafusos
Arruela lisa 8mm,Parafusos
Arruela pressão 10mm,Parafusos
Gerador a diesel 5kVA,Geradores
Gerador a gasolina 3kVA,Geradores
Locação gerador 100kVA,Geradores
Manutenção gerador,Geradores
Uniforme NR-10,Uniformes
Camisa polo manga curta,Uniformes
Calça brim azul,Uniformes
Bota de segurança nº 42,Uniformes
Capacete classe B,Uniformes
Tinta látex 18L branca,Químicos
Solvente PPG 5L,Químicos
Diluente nitrocelulose,Químicos
Lixa d'água nº 200,Químicos
Massa corrida 1.5kg,Químicos
Cabo elétrico 2.5mm 100m,Elétricos
Cabo elétrico 4mm 100m,Elétricos
Disjuntor 25A monofásico,Elétricos
Disjuntor 40A bifásico,Elétricos
Tomada 2P+T 10A,Elétricos
Café em pó 500g
Açúcar refinado 1kg
Filtro de café 103
Coador de café reutilizável
Açucareiro inox
Papel sulfite A4 75g
Caneta esferográfica azul
Lápis preto HB
Borracha branca
Pasta plástica A4
Marcador de quadro branco
Apagador para lousa
Régua 30cm acrílica
Calculadora simples
Grampeador 26/6
Toner laser preto
Cartucho jato de tinta
Resma A3
Pasta sanfonada
Caixa arquivo morto
Mouse óptico USB
Teclado USB português
Monitor 24 polegadas
Cabo HDMI 2m
Hub USB 4 portas
```

- [ ] **Step 2: Create golden CSV (10 categories with expected CNPJ + CNAE)**

```csv
# backend/tests/fixtures/catalogo_golden.csv
descricao,categoria,cnae_esperado,cnpj_esperado
Petroleo bruto e gas,combustivel,0600001,33000167000101
Minerio de ferro,mineracao,0710301,33592510000154
Cerveja em lata,bebidas,1113502,07526557000100
Comercio varejista de eletronicos,varejo,4713004,47960950000121
Frigorifico carne bovina,carne,1011201,02916265000160
Cosmeticos atacado,cosmeticos,4646001,71673990000177
Fabricacao aviao,aerospacial,3041500,07689002000189
Bolsa de valores,financeiro,6611803,09346601000125
Banco comercial DF,banco,6422100,00000000000191
Banco multiplo,banco,6421200,60701190000104
```

- [ ] **Step 3: Write golden recall test**

```python
# backend/tests/integration/test_pipeline_recall_golden.py
"""Golden recall@10: 10 known categories → pipeline should put expected CNPJ in top-10."""

import csv
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.integrations.voyage import VoyageClient

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested, pytest.mark.voyage]

GOLDEN_CSV = Path(__file__).parent.parent / "fixtures" / "catalogo_golden.csv"
MIN_RECALL = 0.80


@pytest.mark.asyncio
async def test_pipeline_recall_golden(db_engine, two_tenants, tmp_path):
    """Upload 10-row catalog → pipeline → assert expected CNPJ in top-10 shortlist."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    rows = list(csv.DictReader(GOLDEN_CSV.open(encoding="utf-8")))
    assert len(rows) == 10

    # Build upload CSV with cluster names = categoria
    upload_csv = tmp_path / "golden_upload.csv"
    with upload_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["descricao_original", "agrupamento"])
        for r in rows:
            w.writerow([r["descricao"], r["categoria"]])

    tenant_id, _ = two_tenants
    upload_id = uuid.uuid4()
    storage = Path("/app/data/uploads") / str(tenant_id) / f"{upload_id}.csv"
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_bytes(upload_csv.read_bytes())

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'golden', :p, 'pending')"
            ),
            {"i": str(upload_id), "t": str(tenant_id), "p": str(storage)},
        )

    await processar_upload(
        upload_id=upload_id, tenant_id=tenant_id, csv_path=storage,
        session_factory=factory,
        voyage=VoyageClient(), curator=CuratorClient(),
    )

    # Check: for each category, expected CNPJ should appear in shortlist (top-10)
    hits = 0
    misses: list[tuple[str, str, list[str]]] = []
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        for r in rows:
            cluster = await session.execute(
                text(
                    "SELECT id, cnae FROM spend_clusters "
                    "WHERE upload_id = :u AND nome_cluster = :c"
                ),
                {"u": str(upload_id), "c": r["categoria"].lower()},
            )
            cluster_row = cluster.first()
            if not cluster_row:
                misses.append((r["categoria"], r["cnpj_esperado"], []))
                continue
            shortlist = await session.execute(
                text(
                    "SELECT cnpj_fornecedor FROM supplier_shortlists "
                    "WHERE cnae = :cnae AND tenant_id = :t "
                    "ORDER BY rank_estagio3 LIMIT 10"
                ),
                {"cnae": cluster_row.cnae, "t": str(tenant_id)},
            )
            cnpjs = [row.cnpj_fornecedor for row in shortlist.all()]
            if r["cnpj_esperado"] in cnpjs:
                hits += 1
            else:
                misses.append((r["categoria"], r["cnpj_esperado"], cnpjs[:5]))

    recall = hits / len(rows)
    if misses:
        report = "\n".join(
            f"  - {cat}: esperado {cnpj}, top-5 = {top}" for cat, cnpj, top in misses
        )
        print(f"\nMisses ({len(misses)}/{len(rows)}):\n{report}")
    assert recall >= MIN_RECALL, f"recall@10 = {recall:.2f}, esperado >= {MIN_RECALL}"
```

- [ ] **Step 4: Run golden test**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  -e VOYAGE_API_KEY=$VOYAGE_API_KEY \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  backend uv run pytest backend/tests/integration/test_pipeline_recall_golden.py -v
```

Expected: PASSED with recall ≥ 0.80.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/fixtures/catalogo_sintetico.csv backend/tests/fixtures/catalogo_golden.csv backend/tests/integration/test_pipeline_recall_golden.py
git commit -m "test(backend): synthetic catalog fixture + golden recall@10 (10 known categories)"
```

---

## Task 12: Tenant isolation + idempotency tests + final DoD

**Files:**
- Test: `backend/tests/integration/test_pipeline_isolation.py`
- Test: `backend/tests/integration/test_pipeline_idempotency.py`
- Modify: `Makefile` (add `test-sprint2` target)

- [ ] **Step 1: Write tenant isolation test**

```python
# backend/tests/integration/test_pipeline_isolation.py
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from agente10.cnae.retrieval import CnaeCandidate
from agente10.curator.cnae_picker import CnaePick
from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.estagio1.pipeline import processar_upload

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested]


@pytest.mark.asyncio
async def test_two_tenants_data_isolated(db_engine, two_tenants, tmp_path, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    voyage = AsyncMock()
    voyage.embed_query.side_effect = lambda t: [0.1] * 1024
    voyage.embed_documents.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]
    curator = AsyncMock()
    async def fake_pick(name, cands):
        return CnaePick(cnae=cands[0].codigo, confidence=0.9, reasoning="x")
    async def fake_rerank(name, cands):
        return [RankedSupplier(cnpj=c.cnpj, rank=i+1, reasoning="x")
                for i, c in enumerate(cands[:10])]
    monkeypatch.setattr("agente10.estagio1.pipeline.pick_cnae", fake_pick)
    monkeypatch.setattr("agente10.estagio1.pipeline.rerank_top10", fake_rerank)

    tenant_a, tenant_b = two_tenants
    csv_text = "descricao_original,agrupamento\nParafuso,Parafusos\n"

    # Upload as tenant A
    upload_a = uuid.uuid4()
    storage_a = tmp_path / "a.csv"
    storage_a.write_text(csv_text, encoding="utf-8")
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_a)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, object_storage_path, status) "
                "VALUES (:i, :t, 'a', :p, 'pending')"
            ),
            {"i": str(upload_a), "t": str(tenant_a), "p": str(storage_a)},
        )
    await processar_upload(
        upload_a, tenant_a, storage_a, factory, voyage, curator,
    )

    # Query as tenant B → MUST see 0 clusters from tenant A
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_b)},
        )
        count = await session.scalar(
            text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u"),
            {"u": str(upload_a)},
        )
    assert count == 0, "tenant B saw tenant A's clusters (RLS broken!)"
```

- [ ] **Step 2: Write idempotency test**

```python
# backend/tests/integration/test_pipeline_idempotency.py
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from agente10.curator.cnae_picker import CnaePick
from agente10.curator.shortlist_reranker import RankedSupplier
from agente10.estagio1.pipeline import processar_upload

pytestmark = [pytest.mark.integration, pytest.mark.rf_ingested]


@pytest.mark.asyncio
async def test_pipeline_idempotent_on_rerun(db_engine, two_tenants, tmp_path, monkeypatch):
    """Running the same upload twice must produce identical state, no duplicates."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    voyage = AsyncMock()
    voyage.embed_query.side_effect = lambda t: [0.1] * 1024
    voyage.embed_documents.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]
    curator = AsyncMock()
    async def fake_pick(name, cands):
        return CnaePick(cnae=cands[0].codigo, confidence=0.9, reasoning="x")
    async def fake_rerank(name, cands):
        return [RankedSupplier(cnpj=c.cnpj, rank=i+1, reasoning="x")
                for i, c in enumerate(cands[:10])]
    monkeypatch.setattr("agente10.estagio1.pipeline.pick_cnae", fake_pick)
    monkeypatch.setattr("agente10.estagio1.pipeline.rerank_top10", fake_rerank)

    tenant_id, _ = two_tenants
    upload_id = uuid.uuid4()
    storage = tmp_path / "c.csv"
    storage.write_text(
        "descricao_original,agrupamento\nParafuso,Parafusos\nGerador,Geradores\n",
        encoding="utf-8",
    )
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, object_storage_path, status) "
                "VALUES (:i, :t, 'c', :p, 'pending')"
            ),
            {"i": str(upload_id), "t": str(tenant_id), "p": str(storage)},
        )

    await processar_upload(upload_id, tenant_id, storage, factory, voyage, curator)

    async def counts() -> tuple[int, int, int]:
        async with factory() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            linhas = await session.scalar(
                text("SELECT COUNT(*) FROM spend_linhas WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            clusters = await session.scalar(
                text("SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            shortlists = await session.scalar(
                text(
                    "SELECT COUNT(*) FROM supplier_shortlists s "
                    "JOIN spend_clusters c ON c.cnae = s.cnae "
                    "WHERE c.upload_id = :u"
                ),
                {"u": str(upload_id)},
            )
        return int(linhas), int(clusters), int(shortlists)

    before = await counts()

    # Re-run the pipeline → should be a no-op (idempotent)
    await processar_upload(upload_id, tenant_id, storage, factory, voyage, curator)

    after = await counts()
    assert before == after, f"non-idempotent: before={before} after={after}"
```

- [ ] **Step 3: Add Makefile target**

In `Makefile`, after existing targets:

```makefile
test-sprint2:
	docker compose up -d postgres
	docker compose run --rm \
		-e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
		-e VOYAGE_API_KEY=$$VOYAGE_API_KEY \
		-e ANTHROPIC_API_KEY=$$ANTHROPIC_API_KEY \
		backend uv run pytest -q backend/tests/integration/test_pipeline_e2e.py \
			backend/tests/integration/test_pipeline_isolation.py \
			backend/tests/integration/test_pipeline_idempotency.py \
			backend/tests/integration/test_api_uploads.py \
			backend/tests/integration/test_pipeline_recall_golden.py \
			-m "integration"
```

- [ ] **Step 4: Run full integration suite**

```bash
make test-sprint2
```

Expected: all tests passed.

- [ ] **Step 5: Run full lint**

```bash
make lint
```

Expected: zero warnings.

- [ ] **Step 6: DoD verification**

Run sanity checks:
```bash
# 1. Migration applied
docker exec agente-supplierdiscovery-postgres-1 psql -U agente10 -d agente10 -c "\d spend_clusters" | grep shortlist_gerada
# Expected: shortlist_gerada | boolean | not null default false

# 2. All Sprint 1.2 tests still pass
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest backend/tests/integration/test_discovery.py backend/tests/unit/test_load_empresas.py backend/tests/unit/test_empresas_helpers.py -q

# 3. CLI works end-to-end with synthetic fixture
docker exec agente-supplierdiscovery-backend-1 sh -c \
  "cd /app && uv run python scripts/run_pipeline.py \
    --csv tests/fixtures/catalogo_sintetico.csv \
    --tenant $(uuidgen) --nome 'Synthetic test'"
# Expected: Done: status=done linhas=50 classificadas=50 clusters=>1 shortlists=>10
```

- [ ] **Step 7: Update memory + commit**

Update `MEMORY.md` and `project_agente10.md` with Sprint 2 completion status, then:

```bash
git add backend/tests/integration/test_pipeline_isolation.py backend/tests/integration/test_pipeline_idempotency.py Makefile
git commit -m "test(backend): tenant isolation + idempotency + make test-sprint2"
```

---

## Definition of Done verification

- [ ] `make migrate` applies 0007 cleanly
- [ ] `make test-sprint2` passes (all 5 integration suites + golden recall ≥ 0.80)
- [ ] `make test-backend` passes (all unit tests including the ~17 new ones for Sprint 2)
- [ ] `make lint` zero warnings
- [ ] CLI: `python scripts/run_pipeline.py` produces summary `status=done linhas=N classificadas=N clusters>0 shortlists>0` over the synthetic 50-row fixture
- [ ] API: `POST /api/v1/uploads` accepts CSV → 202, `GET /api/v1/uploads/{id}` reports status
- [ ] Tenant isolation: tenant B cannot read tenant A's clusters or shortlists
- [ ] Idempotency: re-running pipeline on same upload_id produces no duplicates
- [ ] Golden recall@10 ≥ 0.80 over 10 categorias notórias
- [ ] All 22+ Sprint 1.2/1.3 tests still pass (no regressions)
