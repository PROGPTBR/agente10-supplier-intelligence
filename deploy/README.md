# Deploy — Hetzner VPS + Vercel (caminho alternativo)

> **Caminho ativo:** o piloto está sendo deployado em [RAILWAY.md](RAILWAY.md).
> Este documento descreve um caminho alternativo via VPS próprio — útil se
> futuramente quisermos sair do Railway por custo (Hetzner + DuckDNS sai a
> ~€6.50/mês contra ~$25-30/mês Railway).

Production deploy do Agente 10 para piloto. Custo: **€6.50/mês** (Hetzner) + Vercel grátis.

## Arquitetura

```
Browser → Vercel (Next.js)
              ↓ HTTPS
         Caddy :443 → Backend :8000 (FastAPI)
                          ↓
                   Postgres + Redis (docker-compose)
```

Frontend no Vercel (CDN global, grátis). Backend + DB + Redis num único VPS Hetzner com `docker-compose.prod.yml`. Caddy gera TLS automático via Let's Encrypt.

## Pré-requisitos

- Domínio próprio (Cloudflare/Registro.br/Namecheap) com acesso ao DNS
- Conta Hetzner Cloud ([hetzner.com/cloud](https://www.hetzner.com/cloud))
- Conta Vercel ([vercel.com](https://vercel.com)) — login com GitHub
- Repo deste projeto no GitHub

## Passo 1 — Provisionar VPS Hetzner

1. Hetzner Cloud Console → **Add Server**
2. Location: **Falkenstein** ou **Nuremberg** (EU, latência baixa pro Brasil ~200ms)
3. Image: **Ubuntu 24.04**
4. Type: **CX32** (4 vCPU, 8GB RAM, 80GB SSD, €6.50/mo)
   - Por que CX32 e não CX22? CX22 só tem 40GB — não cabe o dataset de 30GB + intermediários (~60GB durante ingestão).
   - Se previr crescer multi-cliente: **CX42** (16GB RAM, 160GB, €11.90/mo).
5. SSH Key: cole sua chave pública (`~/.ssh/id_ed25519.pub`)
6. Nome: `agente10-prod`
7. Create & Buy

Anote o **IP público** (ex: `49.13.xxx.xxx`).

## Passo 2 — DNS

No painel do seu domínio, cria um A record:

```
api.seudominio.com  A  49.13.xxx.xxx
```

Aguarda propagação (~1-5min). Verifica:
```bash
dig +short api.seudominio.com
```

## Passo 3 — Setup inicial do VPS

```bash
ssh root@49.13.xxx.xxx

# Update
apt update && apt upgrade -y

# Docker + compose
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin git

# Firewall (Hetzner já tem firewall externo, mas reforça)
ufw allow 22
ufw allow 80
ufw allow 443
ufw --force enable
```

## Passo 4 — Clone e configura o repo

```bash
cd /opt
git clone https://github.com/rodrigo386/agente-10.git agente10
cd agente10

# Copia template e edita
cp .env.prod.example .env.prod
nano .env.prod
```

Preenche `.env.prod`:
- `POSTGRES_PASSWORD`: gera senha forte (`openssl rand -base64 32`)
- `DOMAIN`: `api.seudominio.com`
- `CORS_ALLOW_ORIGINS`: URL do Vercel (ex: `https://agente10.vercel.app`)
- `VOYAGE_API_KEY` / `ANTHROPIC_API_KEY`: se usar embeddings/LLM

## Passo 5 — Build e start

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Acompanha logs:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f
```

Aguarda Caddy emitir certificado TLS (~30s). Testa:
```bash
curl https://api.seudominio.com/health
```

Deve retornar `{"status":"ok","db":"ok","redis":"ok"}`.

## Passo 6 — Migrar schema e carregar dados de referência

```bash
# Migrations
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head

# CNAE taxonomy (rápido)
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend uv run python scripts/load_cnae_taxonomy.py
```

## Passo 7 — Carregar dataset CNPJ (1-3 horas)

Isto baixa a base da Receita Federal direto na VPS (não precisa subir do seu PC):

```bash
# 1. Ingestão RF → SQLite (~1-2h, baixa ~5GB, gera ~30GB SQLite)
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend bash backend/scripts/run_cnpj_sqlite.sh

# 2. SQLite → Postgres empresas (~30-60min)
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend uv run python scripts/load_empresas.py
```

Roda em screen/tmux pra não perder se o SSH cair:
```bash
apt install -y tmux
tmux new -s ingest
# ... roda os comandos acima ...
# Ctrl+B depois D pra detachar
# tmux attach -t ingest pra voltar
```

## Passo 8 — Deploy do frontend no Vercel

1. [vercel.com/new](https://vercel.com/new) → Import Project → seu repo
2. **Root Directory:** `frontend`
3. **Framework Preset:** Next.js (auto-detectado)
4. **Environment Variables** (Production):
   - `NEXT_PUBLIC_API_BASE_URL` = `https://api.seudominio.com`
   - `NEXT_PUBLIC_TENANT_ID` = `a7b8c9d0-1234-5678-9abc-def012345678`
5. Deploy

Após primeiro deploy, copia a URL `https://agente10-xxx.vercel.app` e:
- Atualiza `CORS_ALLOW_ORIGINS` no `.env.prod` da VPS
- `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d` pra recarregar backend
- (Opcional) configura domínio customizado no Vercel (Settings → Domains)

## Passo 9 — Smoke test

Abre `https://agente10-xxx.vercel.app` no browser:
1. Dashboard carrega
2. Sobe um CSV em Uploads → Novo
3. Aguarda pipeline (depende do tamanho)
4. Confere clusters + shortlists

## Operação

**Reiniciar serviços:**
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml restart backend
```

**Atualizar código (após git push):**
```bash
cd /opt/agente10
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build backend
```

**Backup do banco:**
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec postgres pg_dump -U agente10 agente10 | gzip > /opt/backups/agente10-$(date +%F).sql.gz
```

Agendar via cron (`crontab -e`):
```cron
0 3 * * * cd /opt/agente10 && docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T postgres pg_dump -U agente10 agente10 | gzip > /opt/backups/agente10-$(date +\%F).sql.gz
```

## Troubleshooting

**Caddy não pega certificado:** verifica DNS apontando pro IP correto + portas 80/443 abertas no firewall Hetzner (externo).

**Backend 503:** `docker compose ... logs backend` — geralmente DB ainda subindo ou env var faltando.

**CORS error no frontend:** confere `CORS_ALLOW_ORIGINS` no `.env.prod` inclui a URL exata do Vercel (com `https://`).

**Disk full durante ingest:** sobe pra CX42 ou anexa Hetzner Volume (€4 por 100GB) e move `/var/lib/docker/volumes` pra lá.
