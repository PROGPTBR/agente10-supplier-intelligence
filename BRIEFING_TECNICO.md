# Agente 10 — Supplier Intelligence — Briefing Técnico

**Projeto:** Agente 10 — Supplier Intelligence
**Empresa:** IAgentics
**Produto:** ICA — Inteligência de Compras Autônoma
**Vertical:** 4 — Inteligência e Estratégia
**Data:** Maio 2026
**Destinatário:** Claude Code (desenvolvimento)

---

## 1. Contexto e objetivo

O **Agente 10** é um agente especialista da plataforma ICA que descobre fornecedores potenciais qualificados para um cliente, a partir da análise de sua base histórica de spend. Opera em quatro estágios: classificação de spend por CNAE, análise de concentração, descoberta de fornecedores e curadoria de shortlist.

### Objetivo deste documento

Servir como briefing único para o Claude Code iniciar a construção do Agente 10. Decisões de arquitetura já estão tomadas — o desenvolvedor não precisa reabrir trade-offs, apenas executar.

### O que está fora deste MVP

- Integração via API com ERPs (Oracle Fusion, SAP) — entrada será apenas via upload XLSX/CSV
- Agente 03 (RFx) — handoff é apenas via export
- Outreach automatizado a fornecedores — fica para fase 2
- Dashboards avançados de BI — UI será funcional, não premium

---

## 2. Stack técnico (definido)

| Camada | Tecnologia | Versão |
|---|---|---|
| Linguagem backend | Python | 3.11+ |
| Framework backend | FastAPI | latest |
| Orquestração de agentes | LangGraph | latest |
| LLM principal | Claude Haiku (rerank) + Claude Sonnet (análise) | claude-haiku-4-5 / claude-sonnet-4-6 |
| Embeddings | Voyage-3 | API Voyage AI |
| Banco de dados | PostgreSQL | 16+ |
| Vector store | pgvector | 0.7+ |
| Geoespacial | PostGIS | 3.4+ |
| Cache | Redis | 7+ |
| ORM | SQLAlchemy 2.0 + Alembic | latest |
| Validação | Pydantic v2 | latest |
| Frontend | Next.js | 14+ App Router |
| UI components | shadcn/ui + Tailwind | latest |
| Geração de PDF | wkhtmltopdf | system |
| Processamento XLSX | openpyxl + pandas | latest |
| Observabilidade LLM | Langfuse | self-hosted ou cloud |
| Infraestrutura | Oracle Cloud Infrastructure (OCI) | — |
| Storage | OCI Object Storage | — |
| Container | Docker + docker-compose | — |
| Testes | pytest + pytest-asyncio | latest |

### Padrões de código

- Black + Ruff para Python (configuração padrão IAgentics)
- Type hints em 100% das funções públicas
- Docstrings em formato Google
- Tests-first em lógica de negócio (estágios 1-4)
- Pydantic para todos os schemas de I/O
- Async/await por padrão (FastAPI + SQLAlchemy 2.0 async)

---

## 3. Estrutura de diretórios

```
agente10-supplier-intelligence/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── alembic.ini
├── alembic/
│   └── versions/
├── src/
│   ├── agente10/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── main.py                    # FastAPI app
│   │   ├── api/                       # endpoints REST
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                # auth, tenant, db deps
│   │   │   ├── upload.py              # POST /uploads
│   │   │   ├── analysis.py            # GET /analyses, POST /analyses
│   │   │   └── shortlist.py           # GET /shortlists
│   │   ├── core/                      # config, security, logging
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── tenancy.py             # RLS helpers
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── models/                # SQLAlchemy models
│   │   ├── schemas/                   # Pydantic schemas
│   │   ├── stages/                    # ★ os 4 estágios
│   │   │   ├── __init__.py
│   │   │   ├── stage1_tagger.py
│   │   │   ├── stage2_analyzer.py
│   │   │   ├── stage3_discovery.py
│   │   │   └── stage4_curator.py
│   │   ├── integrations/              # APIs externas
│   │   │   ├── __init__.py
│   │   │   ├── arquivei.py
│   │   │   ├── econodata.py
│   │   │   ├── serasa.py
│   │   │   ├── ceis_cnep.py
│   │   │   └── voyage.py
│   │   ├── ingestion/                 # ETL Receita Federal
│   │   │   ├── __init__.py
│   │   │   ├── receita_federal.py
│   │   │   └── geocoding.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py              # Anthropic client wrapper
│   │   │   └── prompts.py             # prompts versionados
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── cnpj.py                # validação alfanumérica
│   │       ├── normalization.py       # normalização de texto
│   │       └── reports.py             # geração de PDF
│   └── frontend/                      # Next.js separado
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       └── spend_rotulado.csv         # base de avaliação
├── scripts/
│   ├── load_cnae_taxonomy.py          # popular cnae_taxonomy + embeddings
│   ├── ingest_receita.py              # baixar e ingerir dump RF
│   └── geocode_companies.py           # geocodificar em lote
└── docs/
    ├── arquitetura.md
    └── decisoes/                      # ADRs
```

---

## 4. Modelo de dados (PostgreSQL)

### 4.1 Tabelas globais (sem RLS)

```sql
-- ======================================================
-- BASE DE EMPRESAS — Receita Federal
-- ======================================================
CREATE TABLE empresas (
    cnpj VARCHAR(14) PRIMARY KEY,  -- ALFANUMÉRICO (jul/2026 ready)
    razao_social TEXT NOT NULL,
    nome_fantasia TEXT,
    cnae_primario VARCHAR(7) NOT NULL,
    cnaes_secundarios VARCHAR(7)[] DEFAULT '{}',
    situacao_cadastral VARCHAR(20),
    data_abertura DATE,
    porte VARCHAR(20),
    capital_social NUMERIC(15,2),
    faixa_funcionarios VARCHAR(20),
    natureza_juridica VARCHAR(10),
    uf CHAR(2),
    municipio TEXT,
    cep VARCHAR(8),
    endereco TEXT,
    geom GEOGRAPHY(POINT, 4326),
    telefone TEXT,
    email TEXT,
    ultima_atualizacao_rf DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_empresas_cnae_primario ON empresas(cnae_primario);
CREATE INDEX idx_empresas_cnaes_secundarios ON empresas USING GIN (cnaes_secundarios);
CREATE INDEX idx_empresas_uf_municipio ON empresas(uf, municipio);
CREATE INDEX idx_empresas_situacao ON empresas(situacao_cadastral);
CREATE INDEX idx_empresas_geom ON empresas USING GIST (geom);

-- ======================================================
-- TAXONOMIA CNAE 2.3
-- ======================================================
CREATE TABLE cnae_taxonomy (
    codigo VARCHAR(7) PRIMARY KEY,
    secao CHAR(1),
    divisao VARCHAR(2),
    grupo VARCHAR(3),
    classe VARCHAR(5),
    denominacao TEXT NOT NULL,
    notas_explicativas TEXT,
    exemplos_atividades TEXT,
    embedding vector(1024)  -- Voyage-3 dimension
);

CREATE INDEX idx_cnae_embedding ON cnae_taxonomy
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- ======================================================
-- CACHE DE ENRIQUECIMENTO (compartilhado entre tenants)
-- ======================================================
CREATE TABLE empresa_signals (
    cnpj VARCHAR(14) PRIMARY KEY REFERENCES empresas(cnpj),
    -- Arquivei
    emite_nfe_categorias VARCHAR(7)[],
    nfe_volume_12m NUMERIC,
    nfe_ultima_emissao DATE,
    arquivei_ttl TIMESTAMPTZ,
    -- Econodata
    faturamento_estimado NUMERIC,
    contatos JSONB,
    site TEXT,
    certificacoes TEXT[],
    econodata_ttl TIMESTAMPTZ,
    -- Serasa
    score_credito INT,
    serasa_ttl TIMESTAMPTZ,
    -- Compliance
    em_ceis BOOLEAN DEFAULT FALSE,
    em_cnep BOOLEAN DEFAULT FALSE,
    compliance_ultima_check TIMESTAMPTZ
);

-- ======================================================
-- CACHE DE CLASSIFICAÇÃO DE SPEND (compartilhado)
-- ======================================================
CREATE TABLE spend_classification_cache (
    descricao_hash CHAR(32) PRIMARY KEY,  -- MD5
    descricao_normalizada TEXT NOT NULL,
    cnae VARCHAR(7) NOT NULL,
    confianca NUMERIC(3,2) NOT NULL,
    metodo VARCHAR(20) NOT NULL,  -- 'embedding_only', 'haiku_rerank'
    ttl TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 Tabelas tenant-específicas (com RLS)

```sql
-- ======================================================
-- TENANTS
-- ======================================================
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome TEXT NOT NULL,
    cnpj VARCHAR(14),
    plano VARCHAR(20) DEFAULT 'standard',
    config JSONB DEFAULT '{}',  -- pesos do score, filtros default
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ======================================================
-- UPLOADS DE SPEND
-- ======================================================
CREATE TABLE spend_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    nome_arquivo TEXT NOT NULL,
    object_storage_path TEXT NOT NULL,
    data_upload TIMESTAMPTZ DEFAULT NOW(),
    linhas_total INT DEFAULT 0,
    linhas_classificadas INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, done, error
    erro TEXT,
    metadados JSONB DEFAULT '{}'
);

ALTER TABLE spend_uploads ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON spend_uploads
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ======================================================
-- LINHAS DE SPEND
-- ======================================================
CREATE TABLE spend_linhas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    upload_id UUID NOT NULL REFERENCES spend_uploads(id),
    id_linha_origem TEXT,  -- ID da linha no arquivo original
    descricao TEXT NOT NULL,
    descricao_normalizada TEXT,
    fornecedor_atual TEXT,
    cnpj_fornecedor VARCHAR(14),
    valor_total NUMERIC(15,2),
    quantidade NUMERIC,
    uf_solicitante CHAR(2),
    municipio_solicitante TEXT,
    centro_custo TEXT,
    data_compra DATE,
    -- Saída do Estágio 1
    cnae VARCHAR(7),
    cnae_confianca NUMERIC(3,2),
    cnae_metodo VARCHAR(20),
    -- Colunas extras preservadas
    extras JSONB DEFAULT '{}'
);

ALTER TABLE spend_linhas ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON spend_linhas
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE INDEX idx_spend_linhas_tenant_cnae ON spend_linhas(tenant_id, cnae);
CREATE INDEX idx_spend_linhas_upload ON spend_linhas(upload_id);

-- ======================================================
-- ANÁLISES DE CONCENTRAÇÃO (Estágio 2)
-- ======================================================
CREATE TABLE concentracao_categorias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    upload_id UUID NOT NULL REFERENCES spend_uploads(id),
    cnae VARCHAR(7) NOT NULL,
    spend_periodo NUMERIC(15,2),
    fornecedores_unicos INT,
    transacoes INT,
    hhi NUMERIC(8,2),
    fornecedor_dominante_cnpj VARCHAR(14),
    fornecedor_dominante_share NUMERIC(3,2),
    diagnostico_tipo VARCHAR(30),  -- diversificacao, consolidacao, ok, risco_compliance
    diagnostico_texto TEXT,
    prioridade NUMERIC(5,2),
    data_calculo TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE concentracao_categorias ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON concentracao_categorias
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ======================================================
-- SHORTLISTS (Estágios 3 e 4)
-- ======================================================
CREATE TABLE supplier_shortlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    concentracao_id UUID REFERENCES concentracao_categorias(id),
    cnae VARCHAR(7) NOT NULL,
    cnpj_fornecedor VARCHAR(14) NOT NULL REFERENCES empresas(cnpj),
    score_total NUMERIC(3,2),
    scores_por_dimensao JSONB,  -- {cnae: 0.9, geo: 0.7, ...}
    rank_estagio3 INT,  -- ranking entre top-100
    rank_estagio4 INT,  -- ranking final entre top-10
    enriquecimento_completo BOOLEAN DEFAULT FALSE,
    handoff_rfx BOOLEAN DEFAULT FALSE,
    notas_internas TEXT,
    data_geracao TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE supplier_shortlists ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON supplier_shortlists
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE INDEX idx_shortlists_tenant_cnae ON supplier_shortlists(tenant_id, cnae);
```

### 4.3 Helpers de tenancy

```python
# src/agente10/core/tenancy.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def tenant_context(session: AsyncSession, tenant_id: str):
    """Define o tenant atual para RLS."""
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": tenant_id}
    )
    yield
```

---

## 5. Estágio 1 — Spend Tagger (escopo MÍNIMO)

**Responsabilidade única:** Para cada linha de spend, atribuir um CNAE primário com score de confiança.

**O que NÃO faz:** análise de concentração, detecção de tail spend, decisão de aprovação/revisão, uso de fornecedor como sinal complementar. Tudo isso é responsabilidade de outros estágios.

### 5.1 Pipeline

```
descricao
    ↓
[normalização]
    ↓
[hash MD5 → cache lookup]
    ↓
    ├─ HIT → retorna cnae + confianca + metodo='cache'
    └─ MISS:
        ↓
        [embedding Voyage-3]
            ↓
        [retrieval top-10 em cnae_taxonomy via pgvector]
            ↓
        [se top-1 score ≥ 0.85: usa direto, metodo='embedding_only']
        [senão: rerank com Haiku, metodo='haiku_rerank']
            ↓
        [grava em cache]
            ↓
        retorna cnae + confianca + metodo
```

### 5.2 Normalização de texto

```python
# src/agente10/utils/normalization.py
import unicodedata
import re

ABREVIACOES = {
    "prf": "parafuso",
    "mat": "material",
    "mnt": "manutencao",
    "svc": "servico",
    "equip": "equipamento",
    "mfg": "manufatura",
    "qtd": "quantidade",
    # expandir conforme observação
}

def normalizar_descricao(texto: str) -> str:
    texto = texto.lower().strip()
    # remove acentos
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    # expande abreviações (palavras inteiras)
    palavras = texto.split()
    palavras = [ABREVIACOES.get(p, p) for p in palavras]
    texto = ' '.join(palavras)
    # remove pontuação excessiva
    texto = re.sub(r'[^\w\s\-]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto
```

### 5.3 Prompt do Haiku (rerank)

```python
# src/agente10/llm/prompts.py
RERANK_CNAE_PROMPT = """Você é um especialista em classificação CNAE 2.3.

Dada uma descrição de item ou serviço comprado e uma lista de candidatos CNAE, escolha o CNAE mais adequado.

DESCRIÇÃO: {descricao}

CANDIDATOS (top-10 por similaridade semântica):
{candidatos}

Retorne APENAS um JSON válido neste formato (sem markdown, sem explicação):
{{"cnae": "XX.XX-X-XX", "confianca": 0.85}}

Onde:
- cnae: código completo no formato XX.XX-X-XX
- confianca: número entre 0.0 e 1.0 indicando sua certeza
"""
```

### 5.4 Implementação esquemática

```python
# src/agente10/stages/stage1_tagger.py
import hashlib
from typing import Literal
from pydantic import BaseModel

class CnaeResult(BaseModel):
    cnae: str
    confianca: float
    metodo: Literal['cache', 'embedding_only', 'haiku_rerank']

async def classificar_linha(
    descricao: str,
    db: AsyncSession,
    embedder: VoyageClient,
    llm: AnthropicClient,
    cache: RedisClient,
) -> CnaeResult:
    descricao_norm = normalizar_descricao(descricao)
    desc_hash = hashlib.md5(descricao_norm.encode()).hexdigest()

    # 1. cache lookup
    cached = await cache.get(f"cnae:{desc_hash}")
    if cached:
        return CnaeResult(**cached, metodo='cache')

    # 2. embedding + retrieval
    emb = await embedder.embed(descricao_norm)
    candidatos = await retrieve_top_k_cnaes(db, emb, k=10)

    # 3. decide se Haiku é necessário
    if candidatos[0].similarity >= 0.85:
        result = CnaeResult(
            cnae=candidatos[0].codigo,
            confianca=candidatos[0].similarity,
            metodo='embedding_only',
        )
    else:
        haiku_resp = await llm.rerank(
            prompt=RERANK_CNAE_PROMPT.format(
                descricao=descricao_norm,
                candidatos=format_candidatos(candidatos),
            ),
            model='claude-haiku-4-5',
            max_tokens=100,
        )
        parsed = json.loads(haiku_resp)
        result = CnaeResult(**parsed, metodo='haiku_rerank')

    # 4. grava cache (90 dias)
    await cache.setex(f"cnae:{desc_hash}", 90 * 86400, result.model_dump_json())

    # 5. grava também no cache persistente (Postgres)
    await db.execute(
        insert(SpendClassificationCache).values(
            descricao_hash=desc_hash,
            descricao_normalizada=descricao_norm,
            cnae=result.cnae,
            confianca=result.confianca,
            metodo=result.metodo,
            ttl=datetime.utcnow() + timedelta(days=90),
        ).on_conflict_do_nothing()
    )

    return result
```

### 5.5 Processamento em lote

Para uploads grandes (50k+ linhas), processar de forma assíncrona com workers e progresso reportável:

- Endpoint `POST /uploads` recebe XLSX/CSV, valida schema, retorna `upload_id` + status `processing`
- Worker assíncrono (background task FastAPI ou Celery) processa em batches de 100 linhas
- Endpoint `GET /uploads/{id}` retorna progresso (`linhas_classificadas / linhas_total`)
- Quando completo, status vira `done` e dispara webhook (opcional) ou notifica via WebSocket

### 5.6 Métricas de aceite

- Top-1 acurácia ≥ 75% em base de avaliação rotulada (`tests/fixtures/spend_rotulado.csv`)
- Cobertura: ≥ 95% das linhas recebem CNAE (mesmo com baixa confiança)
- Throughput: 50.000 linhas em <30 minutos (com 50% de cache hit)
- Custo por linha (cache miss): ≤ R$ 0,005

---

## 6. Estágio 2 — Concentration Analyzer

**Responsabilidade:** Receber spend tagueado e identificar categorias prioritárias para diversificação ou consolidação.

### 6.1 Cálculos

Para cada `cnae` do spend importado:

```python
spend_periodo = SUM(valor_total)
fornecedores_unicos = COUNT(DISTINCT cnpj_fornecedor)
transacoes = COUNT(*)

# HHI (Herfindahl-Hirschman Index)
shares = [valor_fornecedor_i / spend_periodo for i in fornecedores]
hhi = sum(s * s * 10000 for s in shares)
# HHI > 5000: altamente concentrado
# HHI 2500-5000: moderadamente concentrado
# HHI < 2500: competitivo

# Fornecedor dominante (se share > 0.5)
fornecedor_dominante = max(fornecedores, key=lambda f: f.share)
```

### 6.2 Diagnóstico textual via Sonnet

Para cada categoria com `prioridade > threshold`, gerar diagnóstico via Claude Sonnet:

```python
DIAGNOSTICO_PROMPT = """Você é consultor sênior de procurement. Analise esta categoria de spend e produza um diagnóstico curto (máximo 3 frases) com recomendação acionável.

CATEGORIA: {cnae_codigo} — {cnae_descricao}
SPEND ANUAL: R$ {spend:,.2f}
FORNECEDORES ATIVOS: {fornecedores_unicos}
HHI: {hhi:.0f}
FORNECEDOR DOMINANTE: {fornecedor_nome} ({share:.0%} do spend)

Tipos de diagnóstico possíveis:
- DIVERSIFICACAO: HHI alto, single-source ou near-single-source
- CONSOLIDACAO: muitos fornecedores, baixo volume médio (tail spend pulverizado)
- RISCO_COMPLIANCE: fornecedor dominante com problema fiscal/CEIS
- OK: categoria saudável

Retorne JSON: {{"tipo": "DIVERSIFICACAO|CONSOLIDACAO|RISCO_COMPLIANCE|OK", "diagnostico": "...", "num_fornecedores_recomendado": N}}
"""
```

### 6.3 Detecção de "qualidade de dados ruim"

Se uma categoria tem >40% das linhas com `cnae_confianca < 0.6`, gerar diagnóstico tipo `QUALIDADE_DADOS` recomendando spend cleansing antes de prosseguir.

### 6.4 Score de prioridade

```python
prioridade = (
    (hhi / 10000) * 0.4 +           # concentração
    log(spend_periodo) / 20 * 0.3 +  # volume
    risco_compliance * 0.3           # 1.0 se fornecedor dominante em CEIS
)
```

---

## 7. Estágio 3 — Supplier Discovery

**Responsabilidade:** Para cada categoria priorizada, descobrir empresas potenciais qualificadas na base própria.

### 7.1 Query principal

```sql
SELECT
    e.cnpj,
    e.razao_social,
    e.uf,
    e.municipio,
    e.porte,
    e.capital_social,
    e.situacao_cadastral,
    e.data_abertura,
    ST_Distance(e.geom, :ponto_solicitante::geography) / 1000 AS distancia_km,
    -- score por dimensão
    CASE WHEN e.cnae_primario = :cnae THEN 1.0 ELSE 0.6 END AS score_cnae,
    EXP(-ST_Distance(e.geom, :ponto_solicitante::geography) / 200000) AS score_geo,
    -- ... demais dimensões
    s.em_ceis,
    s.em_cnep,
    s.score_credito,
    s.nfe_ultima_emissao
FROM empresas e
LEFT JOIN empresa_signals s ON s.cnpj = e.cnpj
WHERE
    (e.cnae_primario = :cnae OR :cnae = ANY(e.cnaes_secundarios))
    AND e.situacao_cadastral = 'ATIVA'
    AND e.uf = ANY(:ufs_aceitas)
    AND e.data_abertura < NOW() - INTERVAL '6 months'
    AND COALESCE(s.em_ceis, false) = false
    AND COALESCE(s.em_cnep, false) = false
ORDER BY distancia_km
LIMIT 500;
```

### 7.2 Score híbrido

```python
PESOS_DEFAULT = {
    'cnae': 0.25,
    'geo': 0.20,
    'porte': 0.15,
    'saude_fiscal': 0.15,
    'nfe_ativa': 0.15,
    'compliance': 0.10,
}

def calcular_score(empresa: Empresa, contexto: dict, pesos: dict = PESOS_DEFAULT) -> float:
    s = {}
    s['cnae'] = 1.0 if empresa.cnae_primario == contexto['cnae'] else 0.6
    s['geo'] = exp(-empresa.distancia_km / 200)
    s['porte'] = score_porte_match(empresa, contexto['ticket_medio'])
    s['saude_fiscal'] = min(1.0, anos_desde_abertura(empresa) / 5)
    s['nfe_ativa'] = 1.0 if empresa.nfe_ultima_emissao and dias_desde(empresa.nfe_ultima_emissao) < 365 else 0.0
    s['compliance'] = 0.0 if empresa.em_ceis or empresa.em_cnep else 1.0

    return sum(s[k] * pesos[k] for k in pesos), s
```

### 7.3 Output

Top-100 empresas ranqueadas, persistidas em `supplier_shortlists` com `rank_estagio3` preenchido.

---

## 8. Estágio 4 — Shortlist Curator

**Responsabilidade:** Refinar top-100 em shortlist final de 10, com enriquecimento via APIs externas em funil de custo.

### 8.1 Funil de enriquecimento

```
Top-100
   ↓ Arquivei (confirma NF-e na categoria nos últimos 12 meses)
Top-30
   ↓ Econodata (contatos, faturamento, certificações)
Top-15
   ↓ Serasa (score de crédito) + filtros do cliente
Top-10 final
```

### 8.2 Cache TTL por API

| API | TTL |
|---|---|
| Arquivei | 30 dias |
| Econodata | 90 dias |
| Serasa | 60 dias |
| CEIS/CNEP | 7 dias |

Sempre verificar cache antes de chamar API. Persistir em `empresa_signals`.

### 8.3 Filtros customizáveis

Cliente configura via JSON em `tenants.config`:

```json
{
  "filtros": {
    "porte_minimo": "ME",
    "ufs_aceitas": ["SP", "MG", "PR"],
    "tempo_minimo_mercado_anos": 2,
    "score_credito_minimo": 600,
    "exigir_certificacoes": ["ISO 9001"],
    "lista_negra_cnpj": []
  },
  "pesos_score": {
    "cnae": 0.25,
    "geo": 0.20,
    "porte": 0.15,
    "saude_fiscal": 0.15,
    "nfe_ativa": 0.15,
    "compliance": 0.10
  }
}
```

### 8.4 Geração de dossiê PDF

Para cada empresa do top-10 final, gerar PDF de 1-2 páginas com:
- Identificação completa
- Score por dimensão (gráfico radar)
- Histórico de NF-e na categoria
- Contatos comerciais
- Score de crédito
- Indicadores de compliance
- Match com requisitos do cliente

Template HTML em `src/agente10/templates/dossie.html`, renderizado via wkhtmltopdf.

---

## 9. Ingestão da Receita Federal

### 9.1 Fonte

- URL oficial: `https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/`
- Mirror via CDN: `https://dados-abertos-rf-cnpj.casadosdados.com.br/`
- Frequência: mensal (atualização ~dia 10 do mês)
- Volume: ~85GB descompactado, ~60M empresas

### 9.2 Pipeline

```python
# scripts/ingest_receita.py
async def ingest_receita_federal():
    """
    1. Detecta arquivos novos no servidor RF (compara hashes/datas)
    2. Baixa em paralelo (8 workers)
    3. Descompacta
    4. Lê em chunks de 100k linhas
    5. Aplica transformações:
       - Normaliza CEP, UF
       - Combina campos de endereço
       - Geocodifica (em fila separada)
    6. UPSERT em batch no Postgres
    7. Atualiza ultima_atualizacao_rf
    8. Notifica via Slack/email quando completo
    """
```

### 9.3 Schema dos arquivos RF

A Receita disponibiliza vários arquivos:
- `Empresas` — dados cadastrais base (CNPJ básico, razão social, capital, porte)
- `Estabelecimentos` — filiais e matriz com CNAE, endereço (a maioria dos dados que importa para o agente)
- `Socios` — sócios pessoa física (NÃO usar no MVP, LGPD)
- `Simples` — opção pelo Simples Nacional
- Tabelas auxiliares: CNAEs, motivos, naturezas jurídicas, países, qualificações, municípios

**ATENÇÃO:** Layout pode mudar (mudou em janeiro/2026). Implementar com testes de schema na ingestão.

### 9.4 Validação CNPJ alfanumérico

```python
# src/agente10/utils/cnpj.py
def validar_cnpj_dv(cnpj: str) -> bool:
    """Valida DV de CNPJ alfanumérico (jul/2026)."""
    if len(cnpj) != 14:
        return False
    base = cnpj[:12]
    dv_informado = cnpj[12:]
    dv_calculado = calcular_dv_modulo11_alfanum(base)
    return dv_informado == dv_calculado
```

Implementar conforme especificação Receita Federal: caracteres alfanuméricos convertidos para valor numérico subtraindo 48 do código ASCII (A=17, B=18, ..., Z=42), depois módulo 11 padrão.

---

## 10. Geocodificação

### 10.1 Estratégia

- Geocodificar empresas por **CEP** primeiro (gratuito, ~95% de cobertura via [BrasilAPI](https://brasilapi.com.br/) ou [ViaCEP](https://viacep.com.br/))
- Para CEPs ausentes ou imprecisos, fallback Google Geocoding API (pago — orçar)
- Resultado salvo em `empresas.geom` (PostGIS POINT)
- Geocodificação em background, fila Redis, throttle 50 req/s

### 10.2 Helper

```python
# src/agente10/ingestion/geocoding.py
async def geocode_cnpj(cnpj: str, db: AsyncSession):
    empresa = await db.get(Empresa, cnpj)
    if empresa.geom:
        return  # já geocodificado

    # tenta CEP via BrasilAPI
    coords = await brasil_api_cep(empresa.cep)
    if not coords:
        coords = await google_geocoding(empresa.endereco)

    if coords:
        empresa.geom = f"POINT({coords['lng']} {coords['lat']})"
        await db.commit()
```

---

## 11. Integrações externas

### 11.1 Arquivei (NF-e SEFAZ)

- Documentação: https://arquivei.com.br/api/
- Caso de uso: confirmar emissão de NF-e por CNAE nos últimos 12 meses
- Implementar com retry exponencial e rate limiting
- Cache TTL: 30 dias

### 11.2 Econodata ou Speedio (B2B)

- Decisão pendente — escolher 1 no início do projeto
- Caso de uso: contatos comerciais, faturamento estimado, certificações
- Cache TTL: 90 dias

### 11.3 Serasa/Boa Vista

- Caso de uso: score de crédito apenas para top-15 finalistas
- Custo por consulta alto — usar com parcimônia
- Cache TTL: 60 dias

### 11.4 CEIS/CNEP (Portal da Transparência)

- Download mensal do CSV oficial: https://portaldatransparencia.gov.br/download-de-dados/ceis
- Carregar em tabela própria, fazer JOIN local (não consultar API por CNPJ)
- Atualização semanal

---

## 12. API REST (FastAPI)

### 12.1 Endpoints principais

```
POST   /uploads                       # upload de XLSX/CSV
GET    /uploads/{id}                  # status do processamento
GET    /uploads/{id}/linhas           # spend tagueado (paginado)

POST   /analyses                      # dispara estágios 2-4
GET    /analyses/{id}                 # resultado da análise
GET    /analyses/{id}/concentracao    # ranking de categorias
GET    /analyses/{id}/shortlist/{cnae} # shortlist de categoria

GET    /shortlists/{id}/dossie/{cnpj} # PDF do dossiê
GET    /shortlists/{id}/export        # XLSX da shortlist completa

GET    /tenants/me                    # config do tenant
PATCH  /tenants/me                    # atualiza pesos/filtros
```

### 12.2 Autenticação

JWT Bearer token. Claim `tenant_id` é obrigatório e usado para RLS.

### 12.3 Schemas (Pydantic)

Definir em `src/agente10/schemas/` com versionamento implícito por endpoint.

---

## 13. Frontend (Next.js 14)

### 13.1 Páginas

| Rota | Função |
|---|---|
| `/login` | autenticação |
| `/upload` | drag-and-drop de XLSX/CSV |
| `/uploads` | histórico de uploads + status |
| `/analyses/{id}` | dashboard da análise |
| `/analyses/{id}/categoria/{cnae}` | shortlist da categoria |
| `/settings` | config de pesos e filtros |

### 13.2 Componentes-chave

- Upload drag-and-drop com progresso real-time
- Tabela de categorias ordenada por prioridade (com filtros HHI, spend, tipo)
- Visualização de score por dimensão (gráfico radar via Recharts)
- Cards de fornecedor com link para dossiê PDF
- Botão "Exportar shortlist" → XLSX

### 13.3 Branding IAgentics

- Cor primária: `#1D9E75` (teal)
- Cor secundária: `#6B46C1` (roxo, headings)
- Tipografia: Inter
- Logo: assets/logo-iagentics.svg

---

## 14. Testes

### 14.1 Cobertura mínima

- **Unit tests:** 100% das funções de `utils/` e `stages/`
- **Integration tests:** fluxo completo upload → tagger → analyzer → discovery → curator com mocks de APIs externas
- **E2E tests:** Playwright para fluxos críticos do frontend

### 14.2 Base de avaliação

`tests/fixtures/spend_rotulado.csv` — mínimo 1.000 linhas com CNAE rotulado manualmente. Será fornecido pelo cliente piloto ou sintetizado via NF-e da Arquivei.

### 14.3 Métricas a reportar

```python
# tests/integration/test_stage1_acuracia.py
def test_acuracia_top1_minima():
    resultado = avaliar_estagio1(spend_rotulado)
    assert resultado['top1_accuracy'] >= 0.75
    assert resultado['cobertura'] >= 0.95
```

---

## 15. Deploy e infraestrutura

### 15.1 Ambientes

| Ambiente | Uso |
|---|---|
| `local` | docker-compose com Postgres + Redis + app |
| `staging` | OCI Compute, dados de teste, integrações em sandbox |
| `production` | OCI Compute, RLS habilitado, monitoring completo |

### 15.2 Docker Compose (desenvolvimento)

Serviços: `api`, `worker`, `postgres` (com extensões pgvector + postgis), `redis`, `frontend`.

### 15.3 OCI

- Compute: VM Standard.E4.Flex (4 OCPU, 32GB RAM) inicialmente
- Storage: Object Storage para uploads + dossiês PDF
- Database: Autonomous Database (Postgres-compatible) ou Compute com Postgres self-managed
- Redis: OCI Cache (ou Compute com Redis self-managed)

---

## 16. Roadmap de execução (16 semanas)

### Sprint 0 — Setup (semana 1)
- [ ] Repositório git + estrutura de diretórios
- [ ] Docker compose funcional (postgres + pgvector + postgis + redis)
- [ ] Alembic configurado, primeira migration
- [ ] CI básico (lint + tests)
- [ ] Pré-commit hooks
- [ ] README com setup local

### Sprint 1 — Fundação de dados (semanas 2-4)
- [ ] Schema completo + migrations
- [ ] Pipeline de ingestão Receita Federal
- [ ] Carga inicial completa (60M empresas)
- [ ] Geocodificação em background
- [ ] Carga da tabela `cnae_taxonomy` com embeddings Voyage-3
- [ ] Carga inicial CEIS/CNEP
- [ ] Validador CNPJ alfanumérico testado

### Sprint 2 — Estágio 1 (semanas 5-7)
- [ ] Endpoint de upload XLSX/CSV
- [ ] Worker de processamento async
- [ ] Pipeline normalização → embedding → retrieval → Haiku rerank
- [ ] Cache Redis + Postgres
- [ ] Endpoint de status de upload
- [ ] Testes com base rotulada (alvo: top-1 ≥ 75%)
- [ ] Frontend: upload + tabela de spend tagueado

### Sprint 3 — Estágio 2 (semanas 8-9)
- [ ] Cálculo HHI, single-source, score de prioridade
- [ ] Diagnóstico textual via Claude Sonnet
- [ ] Detecção de qualidade de dados ruim
- [ ] Endpoint `/analyses/{id}/concentracao`
- [ ] Frontend: dashboard de categorias prioritárias

### Sprint 4 — Estágio 3 (semanas 10-11)
- [ ] Query geoespacial para discovery
- [ ] Score híbrido configurável
- [ ] Filtros automáticos (CEIS, situação, idade)
- [ ] Endpoint `/analyses/{id}/shortlist/{cnae}` (top-100)
- [ ] Frontend: lista expandida de candidatos por categoria

### Sprint 5 — Estágio 4 (semanas 12-14)
- [ ] Integração Arquivei
- [ ] Integração Econodata ou Speedio
- [ ] Integração Serasa
- [ ] Funil de enriquecimento top-100 → top-10
- [ ] Filtros customizáveis por tenant
- [ ] Geração de dossiê PDF
- [ ] Endpoint de export XLSX
- [ ] Frontend: shortlist final + dossiês

### Sprint 6 — Polish e piloto (semanas 15-16)
- [ ] Testes E2E
- [ ] Observabilidade (Langfuse + métricas custom)
- [ ] Documentação para usuário final
- [ ] Deploy em staging
- [ ] Onboarding cliente piloto
- [ ] Calibração de pesos com feedback do piloto

---

## 17. Decisões registradas (ADRs)

### ADR-001: Ingestão via XLSX/CSV no MVP
**Decisão:** aceitar uploads manuais; não integrar Oracle Fusion via API.
**Razão:** elimina ~3 semanas de trabalho; reduz fricção de venda em PoC.
**Reversibilidade:** alta — adicionar conector em v2 sem refactor.

### ADR-002: CNAE como taxonomia primária
**Decisão:** usar CNAE 2.3 (1.331 subclasses) como classificação principal.
**Razão:** alinhamento com base RF (60M empresas), reconhecimento legal no Brasil, base oficial gratuita.
**Trade-off:** granularidade limitada em algumas categorias; v2 complementa com NCM.

### ADR-003: Cascade de modelos LLM
**Decisão:** Haiku para classificação (Estágio 1), Sonnet para análise (Estágios 2 e 4).
**Razão:** redução de custo ~70% mantendo qualidade onde importa.
**Padrão IAgentics.**

### ADR-004: Embedding-first no Estágio 1, Haiku como fallback
**Decisão:** se top-1 do retrieval tem similaridade ≥ 0.85, usa direto (sem LLM); senão chama Haiku.
**Razão:** reduz custo ~60% em descrições óbvias mantendo qualidade em ambíguas.

### ADR-005: Score híbrido com pesos fixos no MVP
**Decisão:** V1 com pesos fixos configuráveis por tenant; V2 com aprendizado via feedback.
**Razão:** simplicidade no MVP; calibração manual com 1-2 clientes antes de automatizar.

### ADR-006: Schema cnpj VARCHAR(14) desde dia zero
**Decisão:** aceitar CNPJ alfanumérico desde o início (vigência julho/2026).
**Razão:** evitar refactor em produção.
**Custo:** zero.

### ADR-007: Voyage-3 para embeddings
**Decisão:** usar Voyage-3 (1024 dim) em vez de OpenAI ada-002 (1536 dim).
**Razão:** melhor performance em português técnico; custo similar; menor pegada de storage.

### ADR-008: PostGIS para queries geoespaciais
**Decisão:** usar PostGIS em vez de calcular haversine em Python.
**Razão:** ordens de magnitude mais rápido para queries por raio em base de 60M empresas.

---

## 18. Variáveis de ambiente

```bash
# .env.example

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agente10
REDIS_URL=redis://localhost:6379/0

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_HAIKU=claude-haiku-4-5
ANTHROPIC_MODEL_SONNET=claude-sonnet-4-6

# Voyage
VOYAGE_API_KEY=pa-...
VOYAGE_MODEL=voyage-3

# Receita Federal
RF_DUMP_URL=https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/
RF_MIRROR_URL=https://dados-abertos-rf-cnpj.casadosdados.com.br/

# Integrações
ARQUIVEI_API_KEY=
ARQUIVEI_BASE_URL=https://api.arquivei.com.br/v1/
ECONODATA_API_KEY=
SERASA_API_KEY=

# Geocoding
BRASILAPI_BASE_URL=https://brasilapi.com.br/api/cep/v2/
GOOGLE_GEOCODING_API_KEY=

# OCI
OCI_BUCKET_UPLOADS=agente10-uploads
OCI_BUCKET_REPORTS=agente10-reports
OCI_REGION=sa-saopaulo-1

# Observabilidade
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Auth
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

---

## 19. Critérios de aceite final (MVP pronto para piloto)

- [ ] Pipeline de ingestão RF rodando mensalmente sem intervenção
- [ ] Schema com `cnpj VARCHAR(14)` e validador alfanumérico
- [ ] Embeddings Voyage-3 da tabela CNAE 2.3 carregados
- [ ] Geocodificação ≥95% das empresas ativas
- [ ] Estágio 1: top-1 ≥75% em base rotulada de 1.000+ linhas
- [ ] Estágio 2: diagnóstico coerente em 10+ categorias avaliadas
- [ ] Estágio 3: ≥50 candidatos retornados em 95% das categorias testadas
- [ ] Estágio 4: dossiê PDF + XLSX exportável funcionais
- [ ] Integrações Arquivei + Econodata/Speedio + Serasa + CEIS/CNEP funcionais
- [ ] Multi-tenancy com RLS testado com 2+ tenants
- [ ] Frontend completo (upload, dashboard, shortlist, settings)
- [ ] Cobertura de testes ≥80% no backend
- [ ] Deploy em staging funcional
- [ ] Documentação de usuário pronta

---

## 20. Riscos conhecidos e mitigações

| Risco | Mitigação |
|---|---|
| Layout RF muda durante desenvolvimento | Testes de schema na ingestão; mirror Casa dos Dados como backup |
| Acurácia <75% no Estágio 1 | Iterar normalização de abreviações; ampliar prompt do Haiku com few-shot examples; revisar tabela `cnae_taxonomy` |
| Custo Serasa explode | Funil estrito top-100→30→15→10; tarifador interno; alertas em consumo anômalo |
| LGPD — dados de sócios PF | Não importar tabela `Socios` no MVP; usar apenas `Empresas` + `Estabelecimentos` |
| CNPJ alfanumérico em produção (jul/2026) | Schema VARCHAR + validador implementados desde sprint 1; testes específicos |
| Cliente piloto fornece spend "sujo" | Estágio 2 detecta e reporta; oferecer spend cleansing como serviço pago |

---

## 21. Próximos passos para o desenvolvedor

1. Ler este documento integralmente
2. Clonar template-base IAgentics (se existir) ou inicializar do zero conforme estrutura da seção 3
3. Subir docker-compose local
4. Criar branch `feat/setup-inicial` e abrir PR com Sprint 0 completo
5. Sincronizar com Rodrigo (CEO) e Ronaldo (CTO) antes de iniciar Sprint 1

**Contatos:**
- Rodrigo Costa (CEO/Product) — rodrigo@iagentics.com.br
- Ronaldo Bueno (CTO/AI Engineer) — ronaldo@iagentics.com.br
- Jesse Guimarães (Commercial) — jesse@iagentics.com.br

---

**Documento confidencial — IAgentics — Maio 2026**
**Versão:** 1.0
