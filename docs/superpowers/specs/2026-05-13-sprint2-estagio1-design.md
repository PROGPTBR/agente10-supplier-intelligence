# Sprint 2 — Estágio 1 (catálogo) + Estágio 3: Pipeline ponta-a-ponta

**Data:** 2026-05-13
**Modo do produto:** catálogo (piloto). Modo transacional fica fora de escopo.

---

## 0. Contexto

Sprint 1.1 fixou o schema (10 tabelas + RLS). Sprint 1.2 carregou 28.992.547 empresas ATIVAS no Postgres com helper `find_empresas_by_cnae` (recall@25=1.0 sobre 10 CNPJs notórios). Sprint 1.3 carregou 1331 subclasses CNAE 2.3 com embeddings Voyage-3 e helper `top_k_cnaes` (recall@5=0.867).

Sprint 2 é a **primeira fatia vertical funcional** do produto: cliente faz upload de catálogo de materiais → pipeline classifica → gera shortlist de fornecedores por categoria. Conecta as 3 sprints anteriores num único fluxo end-to-end.

### Estágios do briefing aplicados
- **Estágio 1 (catálogo):** cluster as linhas + atribuir um CNAE por cluster
- **Estágio 2 (HHI):** vestigial em modo catálogo, ignorado
- **Estágio 3:** para cada cluster com CNAE, gerar top-10 fornecedores
- **Estágio 4 (curator Serasa):** fora de escopo (depende de Sprint 1.4 CEIS/CNEP)

---

## 1. Objetivo

Pipeline assíncrono que recebe um upload de CSV catálogo e produz, sem intervenção humana:

1. `spend_linhas` populadas com cluster_id + cnae denormalizado
2. `spend_clusters` populados com cnae + cnae_confianca + cnae_metodo + nome_cluster
3. `supplier_shortlists` populadas com top-10 fornecedores por cluster (ranked por LLM curator)
4. `spend_uploads.status = done` quando completo, com `progresso_pct` ao vivo

Surface dupla: REST API + CLI. Tenant-isolated via RLS.

### Definition of Done
- `make migrate` aplica `0007_spend_clusters_shortlist_flag.py` sem erro
- `POST /api/v1/uploads` aceita CSV de 5k linhas → status=done em <10min
- `python scripts/run_pipeline.py` produz output completo com summary
- CSV sintético (50 linhas) → 100% linhas com cluster_id; 100% clusters com cnae (auto OR curator OR manual_pending); ≥1 supplier_shortlist por cluster classificado
- Pipeline recall@10 golden ≥ 0.80 (CSV piloto de 10 categorias notórias)
- Tenant isolation: 2 tenants uploadando simultaneamente, RLS bloqueia leitura cruzada
- 22+ testes Sprint 1.2/1.3 ainda passing (no regressions)
- `make lint` zero warnings

### Fora de escopo
- Frontend UI (lista clusters, tela revisão, shortlist) — Sprint 3
- Scoring multi-dimensional (`scores_por_dimensao` JSONB) — Sprint 3
- HHI / Estágio 2 — Sprint transacional futura
- Curator Serasa Estágio 4 — Sprint 4 (depois de 1.4)
- S3/MinIO storage (filesystem local por enquanto)
- JWT auth (header X-Tenant-ID por enquanto)
- Background worker robusto (Celery) — FastAPI BackgroundTasks suficiente
- Re-classificação proativa em mudança de CSV — manual via PATCH

---

## 2. Arquitetura

```
┌─────────────────┐
│  CLI ou POST    │
│  /api/v1/uploads│
└────────┬────────┘
         │ upload CSV
         ▼
┌─────────────────────────────────────────────────────────┐
│  spend_uploads.status: pending → processing → done/failed │
└─────────────────────────────────────────────────────────┘
         │
         ▼ (FastAPI BackgroundTask)
┌──────────────────────────────────────────────────────────────┐
│  PIPELINE (async, dentro de 1 tarefa)                         │
│                                                                │
│  1. parse_csv  ────► spend_linhas (descricao + agrupamento)   │
│                                                                │
│  2. cluster    ────► spend_clusters (agrupamento OU embedding)│
│                                                                │
│  3. cnae       ────► spend_clusters.cnae + confianca + metodo │
│      (hybrid)         > 0.85 → retrieval                       │
│                       0.60-0.85 → curator (LLM Haiku 4.5)      │
│                       < 0.60 → manual_pending                  │
│                                                                │
│  4. shortlist  ────► supplier_shortlists (top-10 ranked)      │
│      (estágio 3)      find_empresas_by_cnae(25) + curator     │
│                                                                │
│  5. denormalize ───► spend_linhas.cnae ← cluster.cnae          │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
   status = done
```

### Componentes (1 módulo por responsabilidade)

| Módulo | Responsabilidade |
|---|---|
| `agente10.estagio1.csv_parser` | Parse CSV/XLSX → valida → cria spend_linhas |
| `agente10.estagio1.clusterizador` | Híbrido: agrupamento + embeddings HDBSCAN |
| `agente10.estagio1.classificador_cnae` | Retrieval + curator (3 paths) |
| `agente10.estagio3.shortlist_generator` | Discovery + curator rerank |
| `agente10.estagio1.pipeline` | Orquestra os 4 estágios + status updates |
| `agente10.api.uploads` | POST/GET endpoints |
| `agente10.curator.cnae_picker` | LLM call para escolha CNAE entre top-5 |
| `agente10.curator.shortlist_reranker` | LLM call para rerank 25 → 10 |
| `scripts/run_pipeline.py` | CLI wrapper que reutiliza o pipeline.processar_upload |

---

## 3. Pipeline stages (detalhe)

### 3.1 CSV Parser
**Input contrato**:
- **Obrigatórias**: `descricao_original`
- **Opcionais**: `id_linha_origem`, `agrupamento`, `fornecedor_atual`, `cnpj_fornecedor`, `valor_total`, `quantidade`, `uf_solicitante`, `municipio_solicitante`, `centro_custo`, `data_compra`
- **Extras** (colunas não-mapeadas) → `extras` JSONB

**Formatos**: CSV (encoding auto-detect: cp1252 → utf-8 fallback) e XLSX (via openpyxl).

**Validação hard (aborta upload)**: linhas sem `descricao_original` não-vazia, encoding indecodificável, arquivo >50MB.

**Output**: N rows em `spend_linhas` (descricao_original + agrupamento + extras opcionais). cluster_id e cnae permanecem NULL até estágios subsequentes.

### 3.2 Clusterizador (híbrido)
```
Para cada linha:
  se row.agrupamento (não-null e não-vazio):
    agrupa em cluster com nome = trim(lower(agrupamento))
  senão:
    → bucket "sem_agrupamento"

Para bucket "sem_agrupamento":
  embeddings = voyage_client.embed(descricoes, batch_size=128, model="voyage-3")
  HDBSCAN(min_cluster_size=3, metric='cosine').fit(embeddings)
  noise points (label -1) → 1 cluster individual cada
  nome_cluster = top-3 termos TF-IDF da cluster (português, stopwords)
```

**Saída**:
- N rows em `spend_clusters` (nome_cluster, num_linhas, upload_id, tenant_id)
- N updates em `spend_linhas.cluster_id`

**Dependências**: voyage-3 client (já existe Sprint 1.3), `sklearn.feature_extraction.text.TfidfVectorizer`, `hdbscan` (nova dep).

### 3.3 Classificador CNAE (híbrido)
```
Para cada cluster:
  candidatos = top_k_cnaes(nome_cluster, k=5)  # Sprint 1.3 helper
  similaridade_top1 = candidatos[0].similarity

  se similaridade_top1 >= 0.85:
    cluster.cnae = candidatos[0].cnae
    cluster.cnae_confianca = similaridade_top1
    cluster.cnae_metodo = 'retrieval'

  elif similaridade_top1 >= 0.60:
    try:
      escolhido = curator_pick(nome_cluster, candidatos)  # Claude Haiku 4.5
      cluster.cnae = escolhido.cnae
      cluster.cnae_confianca = escolhido.confidence
      cluster.cnae_metodo = 'curator'
    except RetryError after 3:
      cluster.cnae = candidatos[0].cnae
      cluster.cnae_confianca = similaridade_top1
      cluster.cnae_metodo = 'retrieval_fallback'

  else:
    cluster.cnae = candidatos[0].cnae  # palpite, mas flagged
    cluster.cnae_confianca = similaridade_top1
    cluster.cnae_metodo = 'manual_pending'
    cluster.revisado_humano = false
```

**Curator prompt** (`cnae_picker`): cluster_name + top-5 (cnae + descricao_completa + secao + divisao) → response JSON `{"cnae": "...", "confidence": 0.85, "reasoning": "..."}`. Model: Claude Haiku 4.5 (~$0.001/call). Retry: tenacity 3× exponential backoff (2s, 4s, 8s).

### 3.4 Shortlist generator (Estágio 3)
```
Para cada cluster com cnae não-null (inclui manual_pending):
  candidatos = find_empresas_by_cnae(cluster.cnae, limit=25)  # Sprint 1.2
  try:
    top10 = curator_rerank(cluster.nome_cluster, candidatos)
  except RetryError after 3:
    top10 = candidatos[:10]  # fallback: ordem do helper (capital_social DESC)

  Para cada empresa em top10 (rank 1..10):
    INSERT supplier_shortlists (
      tenant_id, concentracao_id=NULL, cnae=cluster.cnae,
      cnpj_fornecedor, score_total=NULL, scores_por_dimensao=NULL,
      rank_estagio3=i+1, enriquecimento_completo=false, handoff_rfx=false
    )

  cluster.shortlist_gerada = true  # idempotency flag (migration 0007)
```

**Curator rerank prompt** (`shortlist_reranker`): cluster description + 25 candidatos (cnpj + razao_social + nome_fantasia + capital_social + uf + idade_anos) → response JSON `[{"cnpj": "...", "rank": 1, "reasoning": "..."}, ...]` (10 items). Model: Claude Haiku 4.5 (~$0.002/call).

### 3.5 Denormalização final
`UPDATE spend_linhas SET cnae = c.cnae, cnae_confianca = c.cnae_confianca, cnae_metodo = c.cnae_metodo FROM spend_clusters c WHERE spend_linhas.cluster_id = c.id` — 1 UPDATE SQL único.

---

## 4. Idempotência + recovery

### Transações
Cada estágio em transação separada (commit entre estágios). LLM calls levam minutos; segurar txn aberta com 5k rows gera deadlock.

### Estados de spend_uploads.status
```
pending → processing → done
                    ↘ failed (erro hard, erro = traceback em metadados.erro)
```

### Re-run após crash
Cada estágio detecta progresso prévio:
- **Parse**: se `spend_linhas WHERE upload_id=X COUNT > 0` → skip
- **Cluster**: se `spend_clusters WHERE upload_id=X COUNT > 0` → skip
- **CNAE**: só processa clusters com `cnae IS NULL`
- **Shortlist**: só processa clusters com `cnae IS NOT NULL AND shortlist_gerada = false`
- **Denorm**: idempotente por construção (UPDATE com WHERE cluster_id)

### LLM failures
- Curator CNAE → fallback retrieval top-1 + `cnae_metodo='retrieval_fallback'`
- Curator shortlist rerank → fallback ordem helper (capital_social DESC) + `score_total=NULL`
- Erro de parse CSV → status=failed (não há fallback razoável)
- Erro de Voyage embedding → status=failed (sem ele não há cluster do "sem_agrupamento" bucket)

### Migration 0007 (necessária)
```sql
ALTER TABLE spend_clusters
  ADD COLUMN shortlist_gerada BOOLEAN NOT NULL DEFAULT false;
```

---

## 5. API + CLI

### REST endpoints

```
POST /api/v1/uploads
  Headers: X-Tenant-ID: <uuid>   # MVP simples, sem JWT
  Body: multipart/form-data
    file: <csv ou xlsx>
    nome_arquivo: string
    modo: "catalogo" (default)
  Response 202: { upload_id, status: "pending" }
  Errors: 400 (CSV inválido), 415 (formato), 413 (>50MB)

GET /api/v1/uploads/{id}
  Response 200: {
    upload_id, status, linhas_total, linhas_classificadas,
    data_upload, erro?, metadados, progresso_pct
  }

GET /api/v1/uploads/{id}/clusters
  Query: ?revisado=true|false&metodo=retrieval|curator|manual_pending
  Response 200: [
    { id, nome_cluster, cnae, cnae_descricao, cnae_confianca,
      cnae_metodo, num_linhas, revisado_humano, shortlist_size }, ...
  ]

GET /api/v1/clusters/{id}/shortlist
  Response 200: [
    { cnpj, razao_social, nome_fantasia, capital_social, uf, municipio,
      rank_estagio3, score_total }, ...
  ]

PATCH /api/v1/clusters/{id}
  Body: { cnae?, notas_revisor?, revisado_humano?: true }
  Response 200: cluster atualizado
  Side effect: se cnae mudou → re-trigger shortlist (background)
```

### Storage
Arquivo CSV salvo em `backend/data/uploads/<tenant_id>/<upload_id>.csv`. `spend_uploads.object_storage_path` armazena path absoluto. S3/MinIO fica Sprint futura.

### Auth
FastAPI dependency `get_tenant_id_from_header()` lê `X-Tenant-ID`, valida formato UUID, injeta no handler. Cada handler abre transação e usa `async with tenant_context(session, tenant_id):` (helper Sprint 1.1) para escopo RLS. Sem JWT/OAuth no MVP. Sprint futura troca por bearer token + roles.

### CLI
```bash
python scripts/run_pipeline.py \
    --csv path/to/catalogo.csv \
    --tenant <uuid> \
    --nome "Catálogo piloto Q2 2026"
```

Wrapper:
1. Cria spend_upload row (status=pending)
2. Copia CSV para storage path
3. Chama `await pipeline.processar_upload(upload_id)` sincronamente
4. Imprime progresso por estágio + summary final (N linhas, M clusters, K shortlists, custo LLM)

---

## 6. Testing strategy

### Unit tests (sem DB)
- `test_csv_parser`: cp1252/utf-8, missing column, extras→JSONB, XLSX, >50MB rejeitado
- `test_clusterizador`: agrupamento path (preserva), embedding path (HDBSCAN mockado), híbrido split, noise points isolados
- `test_classificador_cnae`: 3 paths (auto >0.85, curator, manual_pending), curator mockado, fallback após retry
- `test_shortlist_curator`: mock Anthropic, parse JSON response, fallback ordem retrieval
- `test_pipeline_state_machine`: status transitions, idempotency checks

### Integration tests (real Postgres + Voyage)
Marker `integration`:
- `test_pipeline_e2e_catalogo`: CSV sintético 50 linhas (com/sem agrupamento) → pipeline completo → asserts spend_clusters/supplier_shortlists/denorm
- `test_idempotencia_reexecucao`: roda 2× mesmo upload_id → resultado idêntico
- `test_curator_fallback`: mockar Anthropic falhando 3× → fallback aplicado, status=done com warnings
- `test_tenant_isolation`: 2 tenants → RLS bloqueia leitura cruzada de spend_clusters
- `test_api_endpoints`: POST upload, GET status, GET clusters, GET shortlist, PATCH cluster

Marker `rf_ingested`:
- `test_pipeline_recall_golden`: CSV com 10 categorias notórias → ≥80% recebem CNAE correto + shortlist contém o esperado CNPJ no top-10

### Synthetic fixtures
- `backend/tests/fixtures/catalogo_sintetico.csv` — 50 linhas: 30 com agrupamento (5 grupos: parafusos, geradores, uniformes, químicos, elétricos) + 20 sem agrupamento (descrições variadas)
- `backend/tests/fixtures/catalogo_golden.csv` — 10 categorias com cnpj_esperado e cnae_esperado para recall@10 test

### Métricas de custo LLM
- Curator CNAE: ~$0.001 por cluster ambíguo (Haiku 4.5)
- Curator shortlist: ~$0.002 por cluster classificado
- Total estimado piloto (1k linhas → ~100 clusters, ~30 ambíguos): ~$0.30 / upload

---

## 7. Decisões fixadas

- Confidence thresholds: 0.85 (auto retrieval), 0.60 (curator vs manual_pending split)
- Modelo LLM: Claude Haiku 4.5 (custo + latência)
- Clustering: HDBSCAN min_cluster_size=3, metric='cosine'
- Shortlist size: top-10
- `cnae_metodo` enum: `retrieval`, `curator`, `manual_pending`, `retrieval_fallback`, `revisado_humano`
- Storage: filesystem local (`backend/data/uploads/<tenant>/<upload>.csv`)
- Auth: header X-Tenant-ID (sem JWT no MVP)
- Background: FastAPI BackgroundTasks (sem Celery)

---

## 8. Risco / mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Voyage rate limit em batch grande | Média | Médio | Batch 128 com tenacity retry; piloto cabe em 1 batch |
| HDBSCAN não converge em descrições muito heterogêneas | Baixa | Baixo | Noise points viram clusters individuais (1 linha cada); pior caso = clustering inútil mas pipeline conclui |
| Curator LLM JSON malformado | Baixa | Baixo | Pydantic validation no parse; fallback explícito |
| Threshold 0.85/0.60 mal calibrado | Média | Médio | Documenta como decisão configurável; ajusta após primeiro piloto real |
| spend_uploads.linhas_classificadas drift | Baixa | Baixo | Estágio 5 (denorm) recalcula no fim |
| Tenant context não setado no worker async | Alta | Crítico | Middleware obrigatório + tests RLS isolation em CI |

---

## 9. Migrations

- `0007_spend_clusters_shortlist_flag.py` — `ALTER TABLE spend_clusters ADD COLUMN shortlist_gerada BOOLEAN NOT NULL DEFAULT false`

Sem outras migrations necessárias — schema Sprint 1.1 cobre o resto.

---

## 10. Dependências novas (pyproject)

Todas estas precisam ser adicionadas (verificado: nenhuma está em `pyproject.toml`):
- `hdbscan>=0.8.40` (clustering)
- `scikit-learn>=1.5` (TfidfVectorizer)
- `openpyxl>=3.1` (XLSX parse)
- `anthropic>=0.39` (curator LLM client)
- `chardet>=5.2` (CSV encoding detect)

---

## 11. Estrutura de arquivos

```
backend/
├── alembic/versions/
│   └── 0007_spend_clusters_shortlist_flag.py             # ★ NOVO
├── src/agente10/
│   ├── estagio1/
│   │   ├── __init__.py                                   # ★ NOVO
│   │   ├── csv_parser.py                                 # ★ NOVO
│   │   ├── clusterizador.py                              # ★ NOVO
│   │   ├── classificador_cnae.py                         # ★ NOVO
│   │   └── pipeline.py                                   # ★ NOVO (orquestrador)
│   ├── estagio3/
│   │   ├── __init__.py                                   # ★ NOVO
│   │   └── shortlist_generator.py                        # ★ NOVO
│   ├── curator/
│   │   ├── __init__.py                                   # ★ NOVO
│   │   ├── client.py                                     # ★ NOVO (Anthropic wrapper)
│   │   ├── cnae_picker.py                                # ★ NOVO
│   │   └── shortlist_reranker.py                         # ★ NOVO
│   └── api/
│       ├── __init__.py                                   # estender
│       └── uploads.py                                    # ★ NOVO
├── scripts/
│   └── run_pipeline.py                                   # ★ NOVO (CLI)
└── tests/
    ├── unit/
    │   ├── test_csv_parser.py                            # ★ NOVO
    │   ├── test_clusterizador.py                         # ★ NOVO
    │   ├── test_classificador_cnae.py                    # ★ NOVO
    │   └── test_pipeline_state.py                        # ★ NOVO
    ├── integration/
    │   ├── test_pipeline_e2e.py                          # ★ NOVO
    │   ├── test_api_uploads.py                           # ★ NOVO
    │   └── test_pipeline_recall_golden.py                # ★ NOVO (rf_ingested)
    └── fixtures/
        ├── catalogo_sintetico.csv                        # ★ NOVO
        └── catalogo_golden.csv                           # ★ NOVO
```
