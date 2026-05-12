# CNAE 2.3 — Taxonomia + embeddings Voyage-3

## Conteúdo

- `raw/CNAE_2.3_Estrutura_Detalhada.xlsx` — **NÃO commitado** (gitignored). Baixar manualmente
  do IBGE/CONCLA antes de regenerar.
- `taxonomy.json` — saída do parser (`scripts/parse_ibge_xls.py`). 1331 subclasses CNAE 2.3
  com hierarquia (seção/divisão/grupo/classe), denominação, notas explicativas e exemplos
  de atividades.
- `taxonomy_with_embeddings.json` — saída do embedder (`scripts/embed_taxonomy.py`). Mesmo
  conteúdo + `embedding` (Voyage-3, 1024 dim, `input_type="document"`) por subclasse.

## Proveniência

- **Fonte:** CONCLA / IBGE — "CNAE 2.3 Subclasses — Estrutura Detalhada"
- **URL típica:** `https://concla.ibge.gov.br/` → CNAE 2.3 → "Subclasses — Estrutura Detalhada (.xls)"
- **Data do snapshot:** [preencher na hora do download]
- **Versão:** CNAE 2.3 (vigente desde 2024-12)

## Regeneração

Trocar de modelo (ex: voyage-3 → voyage-3.5) ou atualizar a taxonomia:

```bash
# 1) Baixar XLSX atualizado para backend/data/cnae_2.3/raw/CNAE_2.3_Estrutura_Detalhada.xlsx
# 2) Parsear:
cd backend && uv run python scripts/parse_ibge_xls.py
# 3) Embedar (custo Voyage ~$0.02 lifetime):
cd backend && uv run python scripts/embed_taxonomy.py
# 4) Aplicar em cada env:
make load-cnae
```

## Por que JSON commitado?

Embeddings determinísticos + 7MB de tamanho não justifica LFS. Mantém o repo auto-contido,
CI verde sem `VOYAGE_API_KEY`, e diff legível no review.
