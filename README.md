# Agente 10 — Supplier Intelligence

Plataforma de descoberta de fornecedores qualificados a partir da análise de spend histórico. Parte da ICA (Inteligência de Compras Autônoma) da IAgentics.

Briefing técnico completo: [`BRIEFING_TECNICO.md`](./BRIEFING_TECNICO.md)
Specs por sprint: [`docs/superpowers/specs/`](./docs/superpowers/specs/)
Planos de implementação: [`docs/superpowers/plans/`](./docs/superpowers/plans/)

---

## Pré-requisitos

- Docker Desktop com WSL2 (Windows) ou Docker Engine (Linux/Mac)
- Git
- Make (Linux/Mac nativo; Windows via `winget install ezwinports.make`)
- Node 20+ e pnpm 9+ (apenas se for rodar frontend fora do Docker)
- Python 3.12 + uv (apenas se for rodar backend fora do Docker)
- pre-commit (`uv tool install pre-commit` ou `pipx install pre-commit`)

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
├── frontend/          # Next.js 16 + Tailwind v4 + shadcn
├── docker/postgres/   # imagem custom com pgvector + postgis
├── docs/              # specs, plans, decisões
├── .github/workflows/ # CI (backend + frontend)
├── docker-compose.yml
├── Makefile
└── BRIEFING_TECNICO.md
```

## Persistência de dados

- `docker compose down` preserva o volume `pg_data` (dados do Postgres sobrevivem reinícios)
- `docker compose down -v` (ou `make down`/`make clean`) **APAGA** o volume — use só quando quiser resetar do zero

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
