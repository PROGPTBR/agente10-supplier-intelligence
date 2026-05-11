# Sprint 0 — Setup & Fundação — Design

**Projeto:** Agente 10 — Supplier Intelligence (IAgentics / ICA)
**Sprint:** 0 de 6
**Data:** 2026-05-11
**Status:** Aprovado para implementação
**Briefing-pai:** [BRIEFING_TECNICO.md](../../../BRIEFING_TECNICO.md)

---

## 1. Objetivo

Entregar um repositório *bootable*: qualquer dev clona, roda `make up`, vê API e frontend respondendo localmente, e CI verde no primeiro push. Zero código de domínio — apenas infra, ferramentas e o esqueleto rodável que valida o pipeline ponta-a-ponta.

### Definition of done

- `git clone && cp .env.example .env && make up` →
  - API em `http://localhost:8000/health` retorna `{"status":"ok","db":"ok","redis":"ok"}`
  - Frontend em `http://localhost:3000` mostra placeholder Next.js com branding IAgentics
- `make test` → roda smoke test backend (1 teste) + smoke test frontend (1 teste), ambos passam
- `make lint` → `ruff check`, `black --check`, `eslint` passam
- `make migrate` → aplica migration `0001_create_tenants.py` sem erros
- Push em qualquer branch → CI roda lint+test em paralelo (workflow backend + workflow frontend), bloqueia merge na `main` se qualquer um falhar
- README permite onboarding de dev novo em <5min

### O que NÃO faz parte do Sprint 0

- Schema completo (apenas `tenants` no Sprint 0; restante é Sprint 1)
- Ingestão Receita Federal (Sprint 1)
- Endpoints REST além de `/health` (Sprint 2+)
- Multi-tenancy ativa / RLS policies (Sprint 1)
- Integrações Anthropic, Voyage, Arquivei, Econodata, Serasa, CEIS/CNEP (Sprint 2+)
- Autenticação JWT (Sprint 2)
- Deploy em OCI (Sprint 6)
- Observabilidade (Langfuse) (Sprint 6)
- Páginas de upload, dashboard, shortlist, settings (Sprints 2-5)

---

## 2. Decisões fixadas

| Decisão | Escolha | Justificativa |
|---|---|---|
| Git hosting | GitHub (org/user: `rodrigo386`) | Ecossistema, Actions, integração CLI |
| CI | GitHub Actions | Free para repo privado nos limites do MVP; marketplace amplo |
| Python version | 3.12 | Performance > 3.11, suportado por todas libs do briefing |
| Python package manager | `uv` | 10-100x mais rápido que pip/poetry; lock determinístico; `uv sync` simplifica setup |
| Node version | 20 LTS | Default Next.js 14 |
| Frontend package manager | `pnpm` | Disk-efficient, padrão de fato em projetos Next.js novos |
| Pre-commit framework | `pre-commit` (Python) | Mesmos hooks rodam local e CI |
| Repo layout | Monorepo flat: `backend/`, `frontend/` na raiz | Lock files separados; CI por path |
| Docker on Windows | Docker Desktop + WSL2 backend | Performance bind-mount aceitável |
| Migration inicial | Apenas tabela `tenants` (sem RLS) | Valida pipeline alembic sem entrar em decisões de schema do Sprint 1 |
| Health check | `/health` retorna `{status, db, redis}`; HTTP 503 se qualquer dep falhar | Smoke test no CI valida boot completo |

---

## 3. Estrutura de diretórios

```
agente10-supplier-intelligence/
├── README.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       ├── backend.yml
│       └── frontend.yml
├── docker/
│   └── postgres/
│       ├── Dockerfile           # estende pgvector/pgvector:pg16 + instala postgis
│       └── init/
│           └── 01-extensions.sql # CREATE EXTENSION pgvector, postgis, uuid-ossp
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_create_tenants.py
│   ├── src/
│   │   └── agente10/
│   │       ├── __init__.py
│   │       ├── main.py          # FastAPI app + /health
│   │       ├── core/
│   │       │   ├── __init__.py
│   │       │   ├── config.py    # Pydantic Settings
│   │       │   └── db.py        # async engine, session factory
│   │       └── db/
│   │           └── models/
│   │               ├── __init__.py
│   │               └── tenant.py
│   └── tests/
│       ├── conftest.py
│       └── test_health.py
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── Dockerfile
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx             # placeholder "Agente 10 — em construção"
│   ├── components/
│   │   └── ui/                  # shadcn placeholder (apenas Button)
│   └── tests/
│       └── smoke.test.tsx
└── docs/
    ├── superpowers/
    │   ├── specs/               # design docs (este arquivo)
    │   └── plans/               # implementation plans (Sprint 0 plan virá aqui)
    └── decisoes/                # ADRs (vazio neste Sprint)
```

Pastas mencionadas no briefing mas **NÃO criadas no Sprint 0** (responsabilidade de sprints futuros): `backend/src/agente10/api/`, `stages/`, `integrations/`, `ingestion/`, `llm/`, `utils/`, `schemas/`, `scripts/`.

---

## 4. Componentes

### 4.1 `backend/pyproject.toml`

Dependências de runtime mínimas:

- `fastapi` (web)
- `uvicorn[standard]` (server)
- `sqlalchemy[asyncio]` + `asyncpg` (DB async)
- `alembic` (migrations)
- `pydantic-settings` (config via env)
- `redis[hiredis]` (cliente)

Dependências de dev:

- `pytest` + `pytest-asyncio` + `httpx` (testes)
- `ruff` + `black` (lint/format)
- `mypy` (type check — strict-mode off no Sprint 0; ativar gradualmente)

Configuração:

- `[tool.ruff]`: `line-length = 100`, `target-version = "py312"`, `select = ["E","F","I","N","W","UP","B"]`
- `[tool.black]`: `line-length = 100`, `target-version = ["py312"]`
- `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`

### 4.2 `backend/src/agente10/main.py`

FastAPI app com:

- `lifespan` context que abre `AsyncEngine` (Postgres) e `Redis` no startup, fecha no shutdown
- Endpoint `GET /health` que:
  - Executa `SELECT 1` no Postgres
  - Executa `PING` no Redis
  - Retorna `{"status":"ok","db":"ok","redis":"ok"}` (200)
  - Em caso de falha em qualquer dep, retorna HTTP 503 com `{"status":"error","db":"<status>","redis":"<status>"}`

Nenhum outro endpoint, middleware, autenticação ou business logic.

### 4.3 `backend/src/agente10/core/config.py`

`Settings(BaseSettings)` com:

- `database_url: str` (obrigatório)
- `redis_url: str` (obrigatório)
- `env: Literal["local","staging","production"]` (default `"local"`)

Lê de variáveis de ambiente e `.env` (via `pydantic-settings`).

### 4.4 `backend/src/agente10/core/db.py`

- `create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)`
- `async_sessionmaker(engine, expire_on_commit=False)`
- Helper `get_session()` (dependency injection FastAPI)

### 4.5 `backend/alembic/versions/0001_create_tenants.py`

```python
def upgrade():
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

def downgrade():
    op.drop_table("tenants")
```

`alembic/env.py` configurado para async (template `async`), lê `DATABASE_URL` de `Settings`, importa `agente10.db.models.Base` para autogenerate funcionar nos sprints futuros.

### 4.6 `frontend/`

Gerado via `pnpm create next-app@latest frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"`.

`app/page.tsx`:

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#1D9E75] to-[#6B46C1]">
      <h1 className="text-4xl font-bold text-white">
        Agente 10 — em construção
      </h1>
    </main>
  )
}
```

shadcn/ui inicializado (`pnpx shadcn@latest init`) com tema neutro + variáveis CSS para `#1D9E75` (primary) e `#6B46C1` (secondary). Apenas componente `Button` instalado como placeholder.

`vitest` + `@testing-library/react` + `jsdom` configurados para o smoke test.

### 4.7 `Makefile`

```makefile
.PHONY: up down logs test lint fmt migrate install-hooks

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose run --rm backend uv run alembic upgrade head

test:
	docker compose run --rm backend uv run pytest -q
	cd frontend && pnpm test

lint:
	docker compose run --rm backend uv run ruff check src tests
	docker compose run --rm backend uv run black --check src tests
	cd frontend && pnpm lint

fmt:
	docker compose run --rm backend uv run ruff check --fix src tests
	docker compose run --rm backend uv run black src tests
	cd frontend && pnpm format

install-hooks:
	pre-commit install
```

---

## 5. `docker-compose.yml`

Quatro serviços, todos com healthchecks:

```yaml
services:
  postgres:
    build: ./docker/postgres        # estende pgvector/pgvector:pg16 + postgis
    environment:
      POSTGRES_USER: agente10
      POSTGRES_PASSWORD: agente10_dev
      POSTGRES_DB: agente10
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agente10"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
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
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    command: pnpm dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports: ["3000:3000"]

volumes:
  pg_data:
```

### 5.1 Imagem custom do Postgres

`docker/postgres/Dockerfile`:

```dockerfile
FROM pgvector/pgvector:pg16
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-postgis-3 \
    && rm -rf /var/lib/apt/lists/*
COPY init/ /docker-entrypoint-initdb.d/
```

`docker/postgres/init/01-extensions.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

**Trade-off considerado:** usar `postgis/postgis:16-3.4` + instalar pgvector. Rejeitado porque a imagem postgis é maior e a comunidade pgvector está iterando mais rápido — preferimos partir da imagem oficial pgvector.

### 5.2 `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev    # produção: prod deps only
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
CMD ["uv", "run", "uvicorn", "agente10.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Para dev local, o compose sobrescreve `command` com `--reload` e monta o source via volume.

### 5.3 `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine
WORKDIR /app
RUN npm install -g pnpm
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
CMD ["pnpm", "dev"]
```

---

## 6. CI — GitHub Actions

Dois workflows independentes disparados por `paths`:

### 6.1 `.github/workflows/backend.yml`

```yaml
name: backend
on:
  push: { branches: [main] }
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
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test
      REDIS_URL: redis://localhost:6379/0
    defaults:
      run: { working-directory: backend }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { python-version: "3.12" }
      - run: uv sync --frozen
      - run: uv run ruff check src tests
      - run: uv run black --check src tests
      - run: psql "postgresql://postgres:test@localhost:5432/test" -c "CREATE EXTENSION IF NOT EXISTS vector;"
      - run: uv run alembic upgrade head
      - run: uv run pytest -q
```

**Nota:** PostGIS não é necessário no CI do Sprint 0 (só usado a partir do Sprint 1). O `pgvector/pgvector:pg16` cobre o que o smoke test precisa.

### 6.2 `.github/workflows/frontend.yml`

```yaml
name: frontend
on:
  push: { branches: [main] }
  pull_request:
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"
jobs:
  lint-test:
    runs-on: ubuntu-latest
    defaults:
      run: { working-directory: frontend }
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm test
      - run: pnpm build  # garante que o app compila
```

### 6.3 Branch protection (configuração manual)

Pós-setup, ativar no GitHub UI:

- `main` protegida
- Require pull request before merging
- Require status checks: `backend / lint-test`, `frontend / lint-test`
- Require branches to be up to date

Documentar no README como passo manual.

---

## 7. Testes (smoke)

### 7.1 Backend — `backend/tests/test_health.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from agente10.main import app

@pytest.mark.asyncio
async def test_health_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "redis": "ok"}
```

`conftest.py` faz o setup do lifespan (chama `app.router.lifespan_context`) para garantir que engine e Redis estão inicializados antes do teste.

### 7.2 Frontend — `frontend/tests/smoke.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import Home from "@/app/page";

describe("Home page", () => {
  test("renders heading", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Agente 10/i);
  });
});
```

---

## 8. Pre-commit

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-merge-conflict
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
        files: ^backend/
      - id: ruff-format
        files: ^backend/
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
        files: ^backend/
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        files: ^frontend/
```

Setup: `make install-hooks`.

---

## 9. `.env.example`

```bash
# Backend
DATABASE_URL=postgresql+asyncpg://agente10:agente10_dev@postgres:5432/agente10
REDIS_URL=redis://redis:6379/0
ENV=local

# Reservados para sprints futuros (mantém placeholders documentados)
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
```

Variáveis dos Sprints 1-5 (Anthropic, Voyage, Arquivei, etc.) ficam como placeholders comentados no `.env.example` para sinalizar o caminho mas não bloqueiam o boot.

---

## 10. README

Conteúdo mínimo:

1. **O que é** (1 parágrafo, link para briefing)
2. **Pré-requisitos**: Docker Desktop com WSL2, Git, Make
3. **Setup em <5min**: `git clone` → `cp .env.example .env` → `make up` → `make migrate` → abrir `http://localhost:3000` e `http://localhost:8000/health`
4. **Comandos diários** (`make` targets)
5. **Estrutura do repo** (referência rápida)
6. **Configurar branch protection** (passo manual pós-primeiro-push)
7. **Roadmap** (link para briefing, indicando que Sprint 0 está done quando o checklist da seção 1 deste spec é satisfeito)

---

## 11. Riscos & mitigações

| Risco | Mitigação |
|---|---|
| Build da imagem postgres custom (pgvector+postgis) lenta no CI | Após Sprint 1, publicar em `ghcr.io/rodrigo386/agente10-postgres` e fazer pull em vez de build. No Sprint 0, ainda fazemos build local (aceitável: ~2min). |
| Hot reload Next.js + bind-mount lento no Windows | Documentar WSL2 backend no README; alternativa documentada: rodar `pnpm dev` fora do compose (`cd frontend && pnpm dev`) |
| `uv` ainda jovem (lib < 1.0) | Pin de versão exata (`uv 0.4.x`) no Dockerfile e workflow; fallback documentado para pip+pip-tools se quebrar |
| Race condition Postgres no CI | `services.postgres.options` com `--health-cmd` + GitHub Actions já espera healthy antes de rodar steps |
| Branch protection esquecida | Checklist explícito no README; PR de Sprint 0 inclui screenshot ou nota de confirmação |
| Conflito de versão Python local vs Docker | uv lock garante reprodução; README orienta a usar Docker para tudo, dev local Python opcional |

---

## 12. Critérios de aceite (validação final do Sprint 0)

Checklist que o desenvolvedor (você) executa antes de marcar Sprint 0 como done:

- [ ] Repo GitHub criado em `github.com/rodrigo386/agente10-supplier-intelligence` (privado)
- [ ] `git clone` + `cp .env.example .env` + `make up` → tudo sobe sem erro em <5min (com cache de imagens)
- [ ] `make migrate` aplica `0001_create_tenants` sem erro; `psql -c "SELECT * FROM tenants;"` retorna 0 linhas (tabela existe)
- [ ] `curl http://localhost:8000/health` → `200 {"status":"ok","db":"ok","redis":"ok"}`
- [ ] `http://localhost:3000` no browser → tela com gradient IAgentics e heading "Agente 10 — em construção"
- [ ] `make test` → 1 teste backend pass, 1 teste frontend pass
- [ ] `make lint` → zero warnings
- [ ] `make fmt` é idempotente (rodar 2x não muda nada)
- [ ] Pre-commit instalado e bloqueia commit com erro de lint
- [ ] Push numa branch de feature → ambos CI workflows verdes (`backend`, `frontend`)
- [ ] Branch protection ativada manualmente na `main`
- [ ] README permite onboarding de um dev novo em <5min (validar pedindo para Ronaldo ou Jesse rodar o setup)

Quando todos os checks acima passam, Sprint 0 está done e Sprint 1 (Fundação de dados) pode começar.

---

**Próximo passo:** invocar `superpowers:writing-plans` para gerar o plano de implementação detalhado deste spec.
