# Sprint 0 — Setup & Fundação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the Agente 10 monorepo so that `git clone && cp .env.example .env && make up && make migrate` produces a working FastAPI `/health` endpoint, a Next.js placeholder page, a passing CI on GitHub, and `make test` / `make lint` both green.

**Architecture:** Monorepo flat (`backend/`, `frontend/` at root) on GitHub with two independent GitHub Actions workflows scoped by `paths`. Backend is Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic, managed by `uv`. Frontend is Next.js 14 (App Router) + TypeScript + Tailwind + shadcn, managed by `pnpm`. Postgres custom image extends `pgvector/pgvector:pg16` with PostGIS; Redis 7 alpine. All services orchestrated via `docker compose` for local dev.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, asyncpg, Alembic, Pydantic Settings, Redis, pytest, ruff, black, uv | Next.js 14, TypeScript, Tailwind, shadcn/ui, vitest, @testing-library/react, pnpm | Docker, docker-compose, GitHub Actions, pre-commit.

**Spec:** [`docs/superpowers/specs/2026-05-11-sprint0-setup-design.md`](../specs/2026-05-11-sprint0-setup-design.md)

---

## File Structure

Files created in this plan (in dependency order):

```
.gitignore
README.md                                  # final pass at end
Makefile
.env.example
.pre-commit-config.yaml
docker-compose.yml

docker/postgres/Dockerfile
docker/postgres/init/01-extensions.sql

backend/pyproject.toml
backend/uv.lock                            # generated
backend/Dockerfile
backend/.dockerignore
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/0001_create_tenants.py
backend/src/agente10/__init__.py
backend/src/agente10/main.py
backend/src/agente10/core/__init__.py
backend/src/agente10/core/config.py
backend/src/agente10/core/db.py
backend/src/agente10/db/__init__.py
backend/src/agente10/db/base.py
backend/src/agente10/db/models/__init__.py
backend/src/agente10/db/models/tenant.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_config.py
backend/tests/test_health.py

frontend/package.json                      # via create-next-app
frontend/pnpm-lock.yaml                    # generated
frontend/Dockerfile
frontend/.dockerignore
frontend/next.config.mjs
frontend/tailwind.config.ts
frontend/tsconfig.json
frontend/vitest.config.ts
frontend/vitest.setup.ts
frontend/app/layout.tsx                    # modified
frontend/app/page.tsx                      # modified
frontend/app/globals.css                   # modified
frontend/tests/smoke.test.tsx
frontend/components/ui/button.tsx          # via shadcn

.github/workflows/backend.yml
.github/workflows/frontend.yml

docs/superpowers/specs/                    # already exists
docs/superpowers/plans/                    # already exists
docs/decisoes/.gitkeep
```

Each file has a single responsibility (config, db engine, model, migration, endpoint, test). The split mirrors the spec section 3.

---

## Task 1: Git init + repo skeleton

**Files:**
- Create: `.gitignore`
- Create: `docs/decisoes/.gitkeep`
- Modify: (init) git repo

- [ ] **Step 1: Initialize git repo**

Run from project root (`c:\Users\rgoal\Desktop\IAgentics\Agente - SUpplier Discovery`):

```bash
git init -b main
git config user.name "Rodrigo Costa"
git config user.email "rgoalves@gmail.com"
```

Expected: `Initialized empty Git repository in .../.git/`

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore` at repo root with this exact content:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# uv
.python-version

# Node
node_modules/
.next/
out/
dist/
build/
*.tsbuildinfo

# Env
.env
.env.local
.env.*.local
!.env.example

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Coverage / test artifacts
coverage/
htmlcov/
.coverage
.nyc_output/
```

- [ ] **Step 3: Create empty docs dir placeholder**

```bash
mkdir -p docs/decisoes
touch docs/decisoes/.gitkeep
```

- [ ] **Step 4: First commit**

```bash
git add .gitignore docs/
git status
git commit -m "chore: initial repo skeleton"
```

Expected: commit succeeds with 2 files (`.gitignore`, `docs/decisoes/.gitkeep`). Note: `BRIEFING_TECNICO.md` and the existing `docs/superpowers/` files will be added in subsequent commits as their related work lands.

---

## Task 2: Postgres custom image (pgvector + PostGIS)

**Files:**
- Create: `docker/postgres/Dockerfile`
- Create: `docker/postgres/init/01-extensions.sql`

- [ ] **Step 1: Create extensions init SQL**

Create `docker/postgres/init/01-extensions.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

- [ ] **Step 2: Create custom Postgres Dockerfile**

Create `docker/postgres/Dockerfile`:

```dockerfile
FROM pgvector/pgvector:pg16

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/
```

- [ ] **Step 3: Verify the image builds**

```bash
docker build -t agente10-postgres:dev ./docker/postgres
```

Expected: build succeeds, final image tagged. Should print `Successfully tagged agente10-postgres:dev`.

- [ ] **Step 4: Smoke-test the image**

```bash
docker run --rm -d --name pg-smoke \
  -e POSTGRES_PASSWORD=smoke \
  -p 55432:5432 \
  agente10-postgres:dev

# wait for healthy
sleep 8

docker exec pg-smoke psql -U postgres -c "SELECT extname FROM pg_extension ORDER BY extname;"

docker stop pg-smoke
```

Expected output includes rows: `plpgsql`, `postgis`, `uuid-ossp`, `vector`.

- [ ] **Step 5: Commit**

```bash
git add docker/
git commit -m "feat: postgres custom image with pgvector + postgis"
```

---

## Task 3: Backend pyproject + Dockerfile + lock

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.dockerignore`
- Create: `backend/Dockerfile`
- Create: `backend/uv.lock` (generated)

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "agente10"
version = "0.1.0"
description = "Agente 10 — Supplier Intelligence backend"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "redis[hiredis]>=5.2",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "ruff>=0.7",
    "black>=24.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agente10"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B"]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `backend/.dockerignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
tests/
.env
.env.*
```

- [ ] **Step 3: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "uvicorn", "agente10.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Install uv locally (if missing) and generate lock**

If `uv` is not installed:

```bash
# Windows PowerShell:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# OR (bash on Windows / WSL):
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then from `backend/`:

```bash
cd backend
uv lock
ls uv.lock
```

Expected: `uv.lock` created.

- [ ] **Step 5: Verify uv sync works**

```bash
uv sync
uv run python -c "import fastapi, sqlalchemy, alembic, redis; print('deps ok')"
```

Expected: `deps ok` printed.

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/pyproject.toml backend/uv.lock backend/.dockerignore backend/Dockerfile
git commit -m "feat(backend): pyproject + uv lock + Dockerfile"
```

---

## Task 4: Backend config module (TDD)

**Files:**
- Create: `backend/src/agente10/__init__.py`
- Create: `backend/src/agente10/core/__init__.py`
- Create: `backend/src/agente10/core/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Create package `__init__` files**

```bash
mkdir -p backend/src/agente10/core
mkdir -p backend/tests
touch backend/src/agente10/__init__.py
touch backend/src/agente10/core/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 2: Write failing test `backend/tests/test_config.py`**

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agente10.core.config'`.

- [ ] **Step 4: Implement `backend/src/agente10/core/config.py`**

```python
from typing import Literal

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


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/src/agente10/__init__.py backend/src/agente10/core/ backend/tests/__init__.py backend/tests/test_config.py
git commit -m "feat(backend): config module with env loading"
```

---

## Task 5: Backend db module + Tenant model

**Files:**
- Create: `backend/src/agente10/core/db.py`
- Create: `backend/src/agente10/db/__init__.py`
- Create: `backend/src/agente10/db/base.py`
- Create: `backend/src/agente10/db/models/__init__.py`
- Create: `backend/src/agente10/db/models/tenant.py`

- [ ] **Step 1: Create package dirs**

```bash
mkdir -p backend/src/agente10/db/models
touch backend/src/agente10/db/__init__.py
touch backend/src/agente10/db/models/__init__.py
```

- [ ] **Step 2: Create `backend/src/agente10/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
```

- [ ] **Step 3: Create `backend/src/agente10/db/models/tenant.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
```

- [ ] **Step 4: Update `backend/src/agente10/db/models/__init__.py`**

```python
from agente10.db.models.tenant import Tenant

__all__ = ["Tenant"]
```

- [ ] **Step 5: Create `backend/src/agente10/core/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agente10.core.config import Settings

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> None:
    """Initialize the global async engine and session factory."""
    global _engine, _sessionmaker
    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    """Dispose the global engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_engine():
    if _engine is None:
        raise RuntimeError("Engine not initialized — call init_engine() first.")
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("Sessionmaker not initialized.")
    async with _sessionmaker() as session:
        yield session
```

- [ ] **Step 6: Sanity check imports**

```bash
cd backend
uv run python -c "from agente10.db.models import Tenant; from agente10.core.db import init_engine; print('imports ok')"
```

Expected: `imports ok`.

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend/src/agente10/core/db.py backend/src/agente10/db/
git commit -m "feat(backend): db engine + Tenant model"
```

---

## Task 6: Alembic config + initial migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_create_tenants.py`

- [ ] **Step 1: Create `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = src
version_path_separator = os
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `backend/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: Create `backend/alembic/env.py` (async-compatible)**

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from agente10.core.config import get_settings
from agente10.db.base import Base
from agente10.db.models import *  # noqa: F401,F403  -- ensure models register on Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create migration `backend/alembic/versions/0001_create_tenants.py`**

```python
"""create tenants table

Revision ID: 0001
Revises:
Create Date: 2026-05-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("nome", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("tenants")
```

- [ ] **Step 5: Verify migration syntax (offline check)**

From `backend/` directory, with a dummy URL so config doesn't blow up:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://x:x@x/x" REDIS_URL="redis://x" \
  uv run alembic check 2>&1 || true
DATABASE_URL="postgresql+asyncpg://x:x@x/x" REDIS_URL="redis://x" \
  uv run alembic history
```

Expected: `alembic history` prints `0001 (head), create tenants table`. (The `check` may error connecting to the fake DB — that's fine; we just want to confirm the migration parses.)

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/alembic.ini backend/alembic/
git commit -m "feat(backend): alembic config + 0001 create tenants"
```

---

## Task 7: Health endpoint (TDD)

**Files:**
- Create: `backend/src/agente10/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write failing test `backend/tests/conftest.py`**

```python
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
```

- [ ] **Step 2: Write failing test `backend/tests/test_health.py`**

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_health.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agente10.main'` (or similar).

- [ ] **Step 4: Implement `backend/src/agente10/main.py`**

```python
from contextlib import asynccontextmanager

import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from agente10.core.config import get_settings
from agente10.core.db import dispose_engine, get_engine, init_engine

_redis_client: redis_asyncio.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine(settings)

    global _redis_client
    _redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)

    yield

    if _redis_client is not None:
        await _redis_client.aclose()
    await dispose_engine()


app = FastAPI(title="Agente 10", version="0.1.0", lifespan=lifespan)


async def _db_ping() -> str:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


async def _redis_ping() -> str:
    try:
        if _redis_client is None:
            return "error: not initialized"
        pong = await _redis_client.ping()
        return "ok" if pong else "error: no pong"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


@app.get("/health")
async def health() -> JSONResponse:
    db = await _db_ping()
    rd = await _redis_ping()
    ok = db == "ok" and rd == "ok"
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "error", "db": db, "redis": rd},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_health.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -v
```

Expected: 4 tests PASS (2 from test_config + 2 from test_health).

- [ ] **Step 7: Lint check**

```bash
uv run ruff check src tests
uv run black --check src tests
```

Expected: zero warnings.

- [ ] **Step 8: Commit**

```bash
cd ..
git add backend/src/agente10/main.py backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): /health endpoint with DB/Redis checks"
```

---

## Task 8: docker-compose.yml + .env.example + verify boot

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example`**

```bash
# Backend
DATABASE_URL=postgresql+asyncpg://agente10:agente10_dev@postgres:5432/agente10
REDIS_URL=redis://redis:6379/0
ENV=local

# Reserved for Sprint 2+ (placeholders, not used in Sprint 0):
# ANTHROPIC_API_KEY=
# ANTHROPIC_MODEL_HAIKU=claude-haiku-4-5
# ANTHROPIC_MODEL_SONNET=claude-sonnet-4-6
# VOYAGE_API_KEY=
# VOYAGE_MODEL=voyage-3
# JWT_SECRET=
```

- [ ] **Step 2: Copy `.env.example` to `.env`**

```bash
cp .env.example .env
```

- [ ] **Step 3: Create `docker-compose.yml` at repo root**

```yaml
services:
  postgres:
    build: ./docker/postgres
    environment:
      POSTGRES_USER: agente10
      POSTGRES_PASSWORD: agente10_dev
      POSTGRES_DB: agente10
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agente10"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    command: uv run uvicorn agente10.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql+asyncpg://agente10:agente10_dev@postgres:5432/agente10
      REDIS_URL: redis://redis:6379/0
      ENV: local
    volumes:
      - ./backend/src:/app/src
      - ./backend/tests:/app/tests
      - ./backend/alembic:/app/alembic
      - ./backend/alembic.ini:/app/alembic.ini
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"

volumes:
  pg_data:
```

Note: `frontend` service is added in Task 11 (after frontend is scaffolded). For now we verify backend boots.

- [ ] **Step 4: Build and start the stack**

```bash
docker compose build
docker compose up -d
docker compose ps
```

Expected: `postgres`, `redis`, `backend` all listed as `Up` / `healthy`.

- [ ] **Step 5: Apply migration**

```bash
docker compose run --rm backend uv run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 0001, create tenants table`.

- [ ] **Step 6: Verify tenants table exists**

```bash
docker compose exec postgres psql -U agente10 -c "\dt"
docker compose exec postgres psql -U agente10 -c "SELECT * FROM tenants;"
```

Expected: `\dt` lists `tenants`; `SELECT *` returns 0 rows.

- [ ] **Step 7: Verify `/health`**

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok","db":"ok","redis":"ok"}`.

- [ ] **Step 8: Tear down**

```bash
docker compose down
```

- [ ] **Step 9: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: docker-compose with postgres + redis + backend + /health verified"
```

---

## Task 9: Frontend scaffold

**Files:**
- Create: `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/tsconfig.json`, `frontend/next.config.mjs`, `frontend/tailwind.config.ts`, `frontend/app/*` (via create-next-app)
- Modify: `frontend/app/page.tsx`
- Create: `frontend/components/ui/button.tsx` (via shadcn)

- [ ] **Step 1: Install pnpm if not present**

```bash
node --version   # should be 20.x — install Node 20 LTS if older
npm install -g pnpm@9
pnpm --version
```

Expected: `pnpm` version >= 9.

- [ ] **Step 2: Scaffold Next.js into `frontend/`**

From repo root:

```bash
pnpm create next-app@latest frontend \
  --typescript --tailwind --app --no-src-dir \
  --import-alias "@/*" --use-pnpm --eslint --no-turbopack
```

When prompted (if any) accept defaults. Expected: `frontend/` populated with Next.js 14+ project.

- [ ] **Step 3: Sanity check frontend builds**

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

Expected: `Compiled successfully`.

- [ ] **Step 4: Initialize shadcn/ui**

```bash
pnpm dlx shadcn@latest init --yes --defaults
pnpm dlx shadcn@latest add button --yes
```

If interactive prompts appear, accept defaults: TypeScript, App Router, slate base color, CSS variables yes.

Expected: `components/ui/button.tsx` exists, `lib/utils.ts` exists, `tailwind.config.ts` updated with shadcn theme.

- [ ] **Step 5: Replace `frontend/app/page.tsx` with branded placeholder**

Overwrite `frontend/app/page.tsx`:

```tsx
export default function Home() {
  return (
    <main
      className="flex min-h-screen items-center justify-center bg-gradient-to-br p-8"
      style={{
        backgroundImage: "linear-gradient(135deg, #1D9E75 0%, #6B46C1 100%)",
      }}
    >
      <div className="text-center">
        <h1 className="text-5xl font-bold text-white drop-shadow-lg">
          Agente 10 — em construção
        </h1>
        <p className="mt-4 text-lg text-white/90">
          IAgentics · Supplier Intelligence
        </p>
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Verify build still works**

```bash
pnpm build
```

Expected: `Compiled successfully`.

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat(frontend): scaffold Next.js 14 + shadcn + IAgentics placeholder"
```

---

## Task 10: Frontend test setup (vitest) + smoke test

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/tests/smoke.test.tsx`

- [ ] **Step 1: Install vitest + testing deps**

```bash
cd frontend
pnpm add -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom jsdom @types/react @types/react-dom
```

- [ ] **Step 2: Create `frontend/vitest.config.ts`**

```typescript
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
```

- [ ] **Step 3: Create `frontend/vitest.setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Add scripts to `frontend/package.json`**

Open `frontend/package.json`. Inside the `"scripts"` block, ensure these entries exist (add or update — do NOT remove existing scripts like `dev`, `build`, `start`, `lint` that `create-next-app` produced):

```json
"test": "vitest run",
"test:watch": "vitest",
"format": "prettier --write \"**/*.{ts,tsx,json,md}\""
```

- [ ] **Step 5: Install prettier**

```bash
pnpm add -D prettier
```

- [ ] **Step 6: Write failing smoke test `frontend/tests/smoke.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import Home from "@/app/page";

describe("Home page", () => {
  test("renders Agente 10 heading", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Agente 10/i }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run the test**

```bash
pnpm test
```

Expected: 1 test PASS.

- [ ] **Step 8: Run lint and format**

```bash
pnpm lint
pnpm format
```

Expected: lint passes (zero warnings); format makes no changes (or makes idempotent changes).

- [ ] **Step 9: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat(frontend): vitest setup + smoke test"
```

---

## Task 11: Frontend Dockerfile + add to docker-compose

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create `frontend/.dockerignore`**

```
node_modules
.next
out
dist
.git
.env
.env.local
Dockerfile
.dockerignore
```

- [ ] **Step 2: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine

RUN corepack enable && corepack prepare pnpm@9.12.3 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000

CMD ["pnpm", "dev"]
```

- [ ] **Step 3: Add `frontend` service to `docker-compose.yml`**

Append this service definition under `services:` (before `volumes:`):

```yaml
  frontend:
    build: ./frontend
    command: pnpm dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    ports:
      - "3000:3000"
    environment:
      WATCHPACK_POLLING: "true"
```

The final `docker-compose.yml` should now have 4 services: `postgres`, `redis`, `backend`, `frontend`.

- [ ] **Step 4: Build and verify full stack boots**

```bash
docker compose build frontend
docker compose up -d
docker compose ps
```

Expected: all 4 services `Up`; postgres/redis `healthy`.

- [ ] **Step 5: Verify frontend responds**

```bash
# wait for Next.js dev server to be ready (~10-20s on first run)
sleep 20
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```

Expected: `200`.

- [ ] **Step 6: Verify backend still responds**

```bash
docker compose run --rm backend uv run alembic upgrade head
curl -s http://localhost:8000/health
```

Expected: migration runs (idempotent — "Already at head" if previously applied); `/health` returns `{"status":"ok","db":"ok","redis":"ok"}`.

- [ ] **Step 7: Tear down**

```bash
docker compose down
```

- [ ] **Step 8: Commit**

```bash
git add frontend/Dockerfile frontend/.dockerignore docker-compose.yml
git commit -m "feat(frontend): Dockerfile + add to compose"
```

---

## Task 12: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create `Makefile` at repo root**

Note: tabs (not spaces) are required for Makefile recipes.

```makefile
.PHONY: help up down logs build test test-backend test-frontend lint lint-backend lint-frontend fmt migrate install-hooks clean

help:
	@echo "Targets:"
	@echo "  up              start the full dev stack (postgres, redis, backend, frontend)"
	@echo "  down            stop and remove containers + volumes"
	@echo "  logs            tail logs of all services"
	@echo "  build           rebuild images"
	@echo "  test            run backend + frontend tests"
	@echo "  test-backend    run backend tests only"
	@echo "  test-frontend   run frontend tests only"
	@echo "  lint            run all linters"
	@echo "  fmt             apply formatters"
	@echo "  migrate         apply alembic migrations"
	@echo "  install-hooks   install pre-commit hooks"

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

build:
	docker compose build

migrate:
	docker compose run --rm backend uv run alembic upgrade head

test-backend:
	docker compose run --rm backend uv run pytest -q

test-frontend:
	cd frontend && pnpm test

test: test-backend test-frontend

lint-backend:
	docker compose run --rm backend uv run ruff check src tests
	docker compose run --rm backend uv run black --check src tests

lint-frontend:
	cd frontend && pnpm lint

lint: lint-backend lint-frontend

fmt:
	docker compose run --rm backend uv run ruff check --fix src tests
	docker compose run --rm backend uv run black src tests
	cd frontend && pnpm format

install-hooks:
	pre-commit install

clean:
	docker compose down -v
	docker image prune -f
```

- [ ] **Step 2: Verify each target**

```bash
make help
make up
make migrate
make test
make lint
make down
```

Expected: each target runs without error.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: Makefile with up/down/test/lint/fmt/migrate"
```

---

## Task 13: Pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Install `pre-commit` locally**

```bash
# Use pipx or pip — pick one
pipx install pre-commit
# OR: pip install --user pre-commit
pre-commit --version
```

Expected: version >= 3.7.

- [ ] **Step 2: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=1000"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix]
        files: ^backend/(src|tests)/.*\.py$
      - id: ruff-format
        files: ^backend/(src|tests)/.*\.py$

  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        files: ^backend/(src|tests)/.*\.py$

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        files: ^frontend/.*\.(ts|tsx|js|jsx|json|md|css)$
        exclude: ^frontend/(node_modules|\.next|pnpm-lock\.yaml)
```

- [ ] **Step 3: Install hooks**

```bash
pre-commit install
```

Expected: `pre-commit installed at .git/hooks/pre-commit`.

- [ ] **Step 4: Run hooks against all files**

```bash
pre-commit run --all-files
```

Expected: all hooks pass. If any auto-fix files, stage and commit the changes.

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml
# include any auto-fixes:
git add -u
git commit -m "chore: pre-commit hooks (ruff, black, prettier)"
```

---

## Task 14: GitHub Actions — backend workflow

**Files:**
- Create: `.github/workflows/backend.yml`

- [ ] **Step 1: Create workflow file**

```yaml
name: backend

on:
  push:
    branches: [main]
  pull_request:
    paths:
      - "backend/**"
      - ".github/workflows/backend.yml"

jobs:
  lint-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - "5432:5432"
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports:
          - "6379:6379"
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test
      REDIS_URL: redis://localhost:6379/0
      ENV: local
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with:
          version: "0.4.30"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install deps
        run: uv sync --frozen

      - name: Ruff
        run: uv run ruff check src tests

      - name: Black
        run: uv run black --check src tests

      - name: Ensure pgvector extension in CI database
        run: |
          sudo apt-get update -y
          sudo apt-get install -y postgresql-client
          PGPASSWORD=test psql -h localhost -U postgres -d test -c "CREATE EXTENSION IF NOT EXISTS vector;"
          PGPASSWORD=test psql -h localhost -U postgres -d test -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"

      - name: Alembic upgrade
        run: uv run alembic upgrade head

      - name: Pytest
        run: uv run pytest -q
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/backend.yml
git commit -m "ci: backend workflow (lint + test + migrations)"
```

---

## Task 15: GitHub Actions — frontend workflow

**Files:**
- Create: `.github/workflows/frontend.yml`

- [ ] **Step 1: Create workflow file**

```yaml
name: frontend

on:
  push:
    branches: [main]
  pull_request:
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"

jobs:
  lint-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9.12.3

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install
        run: pnpm install --frozen-lockfile

      - name: Lint
        run: pnpm lint

      - name: Test
        run: pnpm test

      - name: Build
        run: pnpm build
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/frontend.yml
git commit -m "ci: frontend workflow (lint + test + build)"
```

---

## Task 16: README + GitHub repo + push + branch protection

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md` at repo root**

```markdown
# Agente 10 — Supplier Intelligence

Plataforma de descoberta de fornecedores qualificados a partir da análise de spend histórico. Parte da ICA (Inteligência de Compras Autônoma) da IAgentics.

Briefing técnico completo: [`BRIEFING_TECNICO.md`](./BRIEFING_TECNICO.md)
Specs por sprint: [`docs/superpowers/specs/`](./docs/superpowers/specs/)
Planos de implementação: [`docs/superpowers/plans/`](./docs/superpowers/plans/)

---

## Pré-requisitos

- Docker Desktop com WSL2 (Windows) ou Docker Engine (Linux/Mac)
- Git
- Make (Linux/Mac nativo; Windows via Git Bash, WSL, ou `choco install make`)
- Node 20 + pnpm 9 (apenas se for rodar frontend fora do Docker)
- Python 3.12 + uv (apenas se for rodar backend fora do Docker)

## Setup em 5 minutos

```bash
git clone git@github.com:rodrigo386/agente10-supplier-intelligence.git
cd agente10-supplier-intelligence
cp .env.example .env
make up
make migrate
```

Validar:

- Backend: http://localhost:8000/health → `{"status":"ok","db":"ok","redis":"ok"}`
- Frontend: http://localhost:3000 → placeholder Agente 10

## Comandos diários

| Comando | O que faz |
|---|---|
| `make up` | Sobe toda a stack (postgres + redis + backend + frontend) |
| `make down` | Para tudo e remove volumes |
| `make logs` | Tail dos logs |
| `make migrate` | Aplica migrations alembic |
| `make test` | Roda testes backend + frontend |
| `make lint` | Lint backend + frontend |
| `make fmt` | Formata todo o código |
| `make install-hooks` | Instala pre-commit hooks (uma vez) |

## Estrutura do repositório

```
agente10-supplier-intelligence/
├── backend/           # FastAPI + SQLAlchemy + Alembic
├── frontend/          # Next.js 14 + Tailwind + shadcn
├── docker/postgres/   # imagem custom com pgvector + postgis
├── docs/              # specs, plans, decisões
├── .github/workflows/ # CI (backend + frontend)
├── docker-compose.yml
├── Makefile
└── BRIEFING_TECNICO.md
```

## CI

Dois workflows independentes no GitHub Actions, disparados por path:

- [`backend.yml`](.github/workflows/backend.yml) — quando algo em `backend/` muda
- [`frontend.yml`](.github/workflows/frontend.yml) — quando algo em `frontend/` muda

## Configuração pós-primeiro-push (manual)

Após o primeiro push para o GitHub:

1. Settings → Branches → Add branch protection rule para `main`:
   - Require pull request before merging
   - Require status checks: `backend / lint-test`, `frontend / lint-test`
   - Require branches to be up to date

## Roadmap

Sprint 0 (este) entrega a fundação. Sprints 1-6 implementam os 4 estágios do Agente 10 conforme o briefing.

Status atual: **Sprint 0 — Setup & Fundação** (concluído quando todos os critérios da seção 12 do spec passam).
```

- [ ] **Step 2: Commit README**

```bash
git add README.md
git commit -m "docs: README with setup instructions"
```

- [ ] **Step 3: Create GitHub repo (private)**

Using `gh` CLI (install from https://cli.github.com/ if missing):

```bash
gh auth status   # ensure logged in as rodrigo386
gh repo create rodrigo386/agente10-supplier-intelligence \
  --private \
  --source=. \
  --remote=origin \
  --description "Agente 10 — Supplier Intelligence (IAgentics ICA)"
```

Expected: repo created at `https://github.com/rodrigo386/agente10-supplier-intelligence`.

If `gh` is not available, create the repo manually in the GitHub UI (private, no README/license/gitignore) and then:

```bash
git remote add origin git@github.com:rodrigo386/agente10-supplier-intelligence.git
```

- [ ] **Step 4: Push main branch**

```bash
git push -u origin main
```

Expected: branch pushed; GitHub Actions starts running both workflows.

- [ ] **Step 5: Watch CI**

```bash
gh run watch
```

Expected: `backend / lint-test` ✅ and `frontend / lint-test` ✅ both succeed.

If anything fails: read the error, fix locally, commit, push, re-run.

- [ ] **Step 6: Enable branch protection (manual via UI)**

Open `https://github.com/rodrigo386/agente10-supplier-intelligence/settings/branches`:

1. **Add branch protection rule** for `main`
2. Check: **Require a pull request before merging**
3. Check: **Require status checks to pass before merging**
4. Search and select: `backend / lint-test`, `frontend / lint-test`
5. Check: **Require branches to be up to date before merging**
6. Save

Take a screenshot for the Sprint 0 acceptance log.

- [ ] **Step 7: Final acceptance run-through**

Run every check from spec section 12 in order:

```bash
# Clean slate
make down
docker volume prune -f

# Cold boot
make up
sleep 30
make migrate

# Validate endpoints
curl -s http://localhost:8000/health
# expect: {"status":"ok","db":"ok","redis":"ok"}

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
# expect: 200

# Tests
make test
# expect: 4 backend tests pass, 1 frontend test pass

# Lint
make lint
# expect: zero warnings

# Format is idempotent
make fmt
git status
# expect: no changes (or only files you'd expect)

# Pre-commit
pre-commit run --all-files
# expect: all hooks pass

make down
```

If everything passes, mark Sprint 0 as done.

- [ ] **Step 8: Final commit (if any cleanup needed)**

```bash
git status
# if anything was changed by fmt or pre-commit:
git add -u
git commit -m "chore: final Sprint 0 cleanup"
git push
```

---

## Self-Review (run after writing this plan; results below)

**Spec coverage check** (mapping each spec section to tasks):

| Spec section | Task(s) |
|---|---|
| 1. DoD: `make up`/`make migrate`/`make test`/`make lint`/CI/README | Tasks 8, 11, 12, 16 |
| 2. Decisions (uv, pnpm, etc.) | All — fixed in pyproject.toml (T3), package.json (T9-10), Dockerfiles (T2, T3, T11) |
| 3. Directory structure | T1 (skeleton), T4-T7 (backend), T9-T11 (frontend), T14-T15 (CI) |
| 4.1 pyproject.toml | T3 |
| 4.2 main.py + /health | T7 |
| 4.3 config.py | T4 |
| 4.4 db.py | T5 |
| 4.5 0001 migration | T6 |
| 4.6 Frontend page + shadcn | T9 |
| 4.7 Makefile | T12 |
| 5. docker-compose | T8 (postgres+redis+backend), T11 (frontend appended) |
| 5.1 Postgres custom image | T2 |
| 5.2 Backend Dockerfile | T3 |
| 5.3 Frontend Dockerfile | T11 |
| 6.1 backend.yml CI | T14 |
| 6.2 frontend.yml CI | T15 |
| 6.3 Branch protection (manual) | T16 step 6 |
| 7.1 backend smoke test | T7 |
| 7.2 frontend smoke test | T10 |
| 8. Pre-commit | T13 |
| 9. .env.example | T8 step 1 |
| 10. README | T16 step 1 |
| 11. Riscos (uv pin, postgres image, etc.) | T3 (uv pin), T2 (image), T14 (CI extension setup) |
| 12. Critérios de aceite | T16 step 7 (full run-through) |

No gaps. Every spec requirement is covered by at least one task.

**Placeholder scan:** No "TBD"/"TODO"/"implement later"/"similar to" found. All steps contain concrete code or commands.

**Type consistency check:**
- `Settings` fields (`database_url`, `redis_url`, `env`) match across T4 (definition), T5 (consumer), T7 (test setup).
- `Tenant` model uses `nome` (not `name`) consistently with T6 migration and spec.
- `init_engine` / `dispose_engine` / `get_engine` / `get_session` defined in T5 are imported in T7 by `main.py`. ✓
- `_db_ping` / `_redis_ping` defined in T7's `main.py` are monkeypatched in T7's `conftest.py`. ✓
- Migration revision `"0001"` matches filename `0001_create_tenants.py`. ✓
- `pgvector/pgvector:pg16` image tag used identically in T2 Dockerfile and T14 CI service. ✓

Plan is internally consistent. Ready to execute.

---

## Execution

When ready to execute, choose:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Uses `superpowers:subagent-driven-development`.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch with checkpoints.
