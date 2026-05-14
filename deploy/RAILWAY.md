# Deploy — Railway (tudo em um projeto)

Deploy do Agente 10 100% no Railway: Postgres, Redis, backend FastAPI e frontend Next.js.
Sem domínio próprio necessário (Railway dá `*.up.railway.app` com HTTPS automático).

## Arquitetura

```
Railway Project "agente10":
  ├── Postgres plugin       (30GB CNPJ + tenant tables)
  ├── Redis plugin
  ├── backend  service      (root: /backend,  Dockerfile)
  └── frontend service      (root: /frontend, Dockerfile)
```

Conexão entre serviços é via Railway internal network (`*.railway.internal`).
Frontend e backend são expostos publicamente.

## Pré-requisitos no seu PC

- `uv` (já tem — managed pelo backend/pyproject.toml)
- `psql` (para restaurar dump grande, mais rápido que Python). Windows:
  `winget install PostgreSQL.PostgreSQL.16` ou só `psql.exe` standalone.
- Railway CLI: `npm install -g @railway/cli`
- Credenciais: `railway login`
- O arquivo `backend/data/cnpj.db` (~39GB SQLite, já gerado)
- `VOYAGE_API_KEY` e `ANTHROPIC_API_KEY`

## Passo 1 — Criar projeto Railway

1. [railway.com/new](https://railway.com/new) → **Deploy from GitHub repo**
2. Selecione `rodrigo386/agente10-supplier-intelligence`
3. Railway detecta **dois** Dockerfiles (`backend/Dockerfile` e `frontend/Dockerfile`)
   e os monorepo configs `railway.toml`. Pode criar 1 serviço por enquanto —
   adicionamos os outros nos próximos passos.

## Passo 2 — Adicionar plugins

No dashboard do projeto:
1. **+ New** → **Database** → **Add PostgreSQL**
2. **+ New** → **Database** → **Add Redis**

Anote o nome interno dos serviços (ex: `Postgres`, `Redis`).

## Passo 3 — Configurar serviço backend

1. **+ New** → **GitHub Repo** → selecione o mesmo repo
2. Settings → **Root Directory** = `backend`
3. Railway lê `backend/railway.toml` automaticamente (Dockerfile + start command).
4. Settings → **Variables**:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Reference Variable) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (Reference Variable) |
| `ENV` | `production` |
| `VOYAGE_API_KEY` | seu key |
| `VOYAGE_MODEL` | `voyage-3` |
| `ANTHROPIC_API_KEY` | seu key |
| `CORS_ALLOW_ORIGINS` | **deixe vazio por enquanto** — preencher após Passo 4 |

5. Settings → **Networking** → **Generate Domain**
   → anote a URL: `https://agente10-backend-production.up.railway.app`

## Passo 4 — Configurar serviço frontend

1. **+ New** → **GitHub Repo** → mesmo repo
2. Settings → **Root Directory** = `frontend`
3. Settings → **Variables** (build-time, necessárias antes do primeiro build):

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | URL do backend do Passo 3 |
| `NEXT_PUBLIC_TENANT_ID` | `a7b8c9d0-1234-5678-9abc-def012345678` |

4. Settings → **Networking** → **Generate Domain**
   → anote: `https://agente10-frontend-production.up.railway.app`

5. **Volte ao backend** (Passo 3) e preencha:
   - `CORS_ALLOW_ORIGINS` = URL do frontend (sem barra no final)
   - Backend faz redeploy automático

## Passo 5 — Migrar schema do Postgres (rodando do seu PC)

Conecte ao Postgres do Railway via tunel CLI:

```bash
# Pega a URL pública do Postgres (com proxy TLS):
railway link  # seleciona o projeto
railway variables -s Postgres   # mostra DATABASE_PUBLIC_URL

# Exporta como env var local:
export DATABASE_URL="postgresql+asyncpg://postgres:xxx@xxx.proxy.rlwy.net:xxx/railway"

# (Windows PowerShell)
# $env:DATABASE_URL = "postgresql+asyncpg://..."

# Roda alembic do seu venv local (sem Docker):
cd backend
uv run alembic upgrade head

# Carrega taxonomia CNAE (rápido, 13MB JSON → 1331 rows com embeddings):
uv run python scripts/load_cnae_taxonomy.py
```

## Passo 6 — Carregar 30GB de empresas (PC → Railway)

Esta é a etapa lenta. O `cnpj.db` SQLite local (39GB) será lido linha-a-linha
e inserido no Postgres do Railway via rede.

```bash
cd backend
uv run python scripts/load_empresas.py
```

**Tempo:** depende da sua banda de upload. Em 50Mbps ≈ 1-2h. Em 10Mbps ≈ 6-10h.
Rode com a máquina ligada. O script é idempotente — se cair, re-rodar resume.

**Alternativa mais rápida (se psql instalado):** gerar pg_dump local + restore.
Mas como o source é SQLite, não Postgres, o caminho Python é o único.

Acompanha:
```bash
railway logs -s Postgres   # se quiser ver
# ou check counts:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM empresas;"
```

## Passo 7 — Smoke test

```bash
# Backend health:
curl https://agente10-backend-production.up.railway.app/health

# Tenant header:
curl -H "X-Tenant-ID: a7b8c9d0-1234-5678-9abc-def012345678" \
     https://agente10-backend-production.up.railway.app/api/v1/uploads
```

Abra o frontend no browser:
- `https://agente10-frontend-production.up.railway.app`
- Dashboard carrega
- Suba um CSV em **Uploads → Novo**
- Aguarda pipeline classificar
- Confira clusters + shortlists não-vazias

## Operação

**Redeploy após push:** Railway redeploy automaticamente quando você dá `git push origin main`.

**Logs:**
```bash
railway logs -s backend
railway logs -s frontend
```

**Postgres backup:** Railway tem snapshot diário automático no Pro plan. Manual:
```bash
pg_dump $DATABASE_URL | gzip > backup-$(date +%F).sql.gz
```

**Custo:** Pro plan $20/mo (inclui $20 credit). 30GB Postgres + 2 services + Redis
deve ficar em ~$25-30/mo total, possivelmente coberto pelo credit no início.

## Troubleshooting

**Backend 503 health:** `railway logs -s backend` — geralmente DATABASE_URL ainda
sem `+asyncpg`. O validator `_ensure_asyncpg_driver` em `core/config.py` converte
automaticamente; verifique se subiu a versão com esse fix.

**Frontend CORS error:** confirme `CORS_ALLOW_ORIGINS` no backend tem a URL exata
do frontend com `https://` e sem `/` no final.

**Build falha por env var ausente:** Next.js precisa `NEXT_PUBLIC_*` no BUILD,
não no runtime. Setar as vars ANTES do primeiro build (já documentado no Passo 4).

**Upload de empresas lento:** verifique se está usando `DATABASE_PUBLIC_URL` (proxy)
em vez de `railway.internal`. Internal só funciona DENTRO do Railway.
