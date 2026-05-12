"""Load CNAE 2.3 taxonomy + embeddings into cnae_taxonomy table (idempotent UPSERT).

Usage:
    cd backend && uv run python scripts/load_cnae_taxonomy.py

Reads:  data/cnae_2.3/taxonomy_with_embeddings.json
Writes: 1331 rows in cnae_taxonomy via INSERT ... ON CONFLICT (codigo) DO UPDATE.

Connects via DATABASE_URL (asyncpg-form is auto-converted to libpq form).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import asyncpg

DATA_PATH = Path(__file__).parent.parent / "data" / "cnae_2.3" / "taxonomy_with_embeddings.json"
EXPECTED_COUNT = 1331
EXPECTED_DIM = 1024

UPSERT_SQL = """
INSERT INTO cnae_taxonomy
    (codigo, secao, divisao, grupo, classe, denominacao,
     notas_explicativas, exemplos_atividades, embedding)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)
ON CONFLICT (codigo) DO UPDATE SET
    secao = EXCLUDED.secao,
    divisao = EXCLUDED.divisao,
    grupo = EXCLUDED.grupo,
    classe = EXCLUDED.classe,
    denominacao = EXCLUDED.denominacao,
    notas_explicativas = EXCLUDED.notas_explicativas,
    exemplos_atividades = EXCLUDED.exemplos_atividades,
    embedding = EXCLUDED.embedding;
"""


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL not set")
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run embed_taxonomy.py first.", file=sys.stderr)
        return 2

    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if len(rows) != EXPECTED_COUNT:
        print(f"ERROR: file has {len(rows)} rows, expected {EXPECTED_COUNT}.", file=sys.stderr)
        return 1
    for r in rows:
        if len(r["embedding"]) != EXPECTED_DIM:
            print(
                f"ERROR: {r['codigo']} has dim {len(r['embedding'])}, expected {EXPECTED_DIM}.",
                file=sys.stderr,
            )
            return 1

    conn = await asyncpg.connect(_dsn())
    try:
        t0 = time.perf_counter()
        async with conn.transaction():
            for r in rows:
                emb_str = "[" + ",".join(f"{x:.6f}" for x in r["embedding"]) + "]"
                await conn.execute(
                    UPSERT_SQL,
                    r["codigo"],
                    r["secao"],
                    r["divisao"],
                    r["grupo"],
                    r["classe"],
                    r["denominacao"],
                    r["notas_explicativas"],
                    r["exemplos_atividades"],
                    emb_str,
                )
        await conn.execute("ANALYZE cnae_taxonomy;")
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM cnae_taxonomy WHERE embedding IS NOT NULL;"
        )
        if count != EXPECTED_COUNT:
            print(
                f"ERROR: after load, count = {count}, expected {EXPECTED_COUNT}.",
                file=sys.stderr,
            )
            return 1
        print(f"Loaded {count} CNAE subclasses in {time.perf_counter() - t0:.2f}s")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
