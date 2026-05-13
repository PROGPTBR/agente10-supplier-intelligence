"""Transform: rictom/cnpj-sqlite (SQLite) → Postgres empresas (denormalized, filtered ATIVA).

Usage:
    cd backend && uv run python scripts/load_empresas.py

Reads:  data/cnpj.db (produced by `make ingest-rf`)
Writes: ~30M rows into the Postgres empresas table via INSERT ... ON CONFLICT (cnpj) DO UPDATE.

Filters: situacao_cadastral = '02' (ATIVA per RF code table).

Transactions: each 100k-row chunk runs in its own transaction. A crash mid-load
leaves the table partially populated; re-run is idempotent (UPSERT) and heals it.

Connects via DATABASE_URL (asyncpg-form is auto-converted to libpq form).
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import asyncpg
from empresas_helpers import parse_porte, parse_yyyymmdd

DATA_PATH = Path(__file__).parent.parent / "data" / "cnpj.db"
CHUNK_SIZE = 100_000
MIN_EXPECTED_ROWS = 25_000_000  # margin below 35M for monthly RF variation

# Sentinel row used to detect schema drift before processing 30M rows.
_SCHEMA_CHECK_SQL = """
SELECT name FROM sqlite_master WHERE type='table'
  AND name IN ('empresas','estabelecimento','municipio');
"""

# Main transform query — JOIN empresas + estabelecimento + municipio (lookup).
# Real rictom-produced schema (verified 2026-05-12):
#   - table is `empresas` (plural), not `empresa`
#   - column is `cnae_fiscal` (not cnae_fiscal_principal)
#   - columns are `ddd1`/`telefone1` (no underscore between letters and digit)
#   - estabelecimento has a denormalized `cnpj` column (basico+ordem+dv pre-joined)
_SELECT_SQL = """
SELECT
    est.cnpj                                          AS cnpj,
    e.razao_social,
    NULLIF(est.nome_fantasia, '')                     AS nome_fantasia,
    est.cnae_fiscal                                   AS cnae_primario,
    est.cnae_fiscal_secundaria                        AS cnaes_sec_csv,
    est.data_inicio_atividades                        AS data_abertura_str,
    e.porte_empresa                                   AS porte_code,
    e.capital_social,
    e.natureza_juridica,
    est.uf,
    m.descricao                                       AS municipio,
    est.cep,
    trim(coalesce(est.tipo_logradouro,'') || ' ' ||
         coalesce(est.logradouro,'')      || ', ' ||
         coalesce(est.numero,'')          || ' ' ||
         coalesce(est.complemento,'')     || ' - ' ||
         coalesce(est.bairro,''))                     AS endereco,
    coalesce(est.ddd1,'') || coalesce(est.telefone1,'') AS telefone,
    NULLIF(est.correio_eletronico, '')                AS email
FROM estabelecimento est
JOIN empresas e USING (cnpj_basico)
LEFT JOIN municipio m ON m.codigo = est.municipio
WHERE est.situacao_cadastral = '02'
ORDER BY est.cnpj_basico, est.cnpj_ordem
"""

UPSERT_SQL = """
INSERT INTO empresas (
    cnpj, razao_social, nome_fantasia,
    cnae_primario, cnaes_secundarios,
    situacao_cadastral, data_abertura,
    porte, capital_social, natureza_juridica,
    uf, municipio, cep, endereco,
    geom, telefone, email, ultima_atualizacao_rf
)
VALUES (
    $1, $2, $3,
    $4, $5,
    'ATIVA', $6,
    $7, $8, $9,
    $10, $11, $12, $13,
    NULL, $14, $15, CURRENT_DATE
)
ON CONFLICT (cnpj) DO UPDATE SET
    razao_social         = EXCLUDED.razao_social,
    nome_fantasia        = EXCLUDED.nome_fantasia,
    cnae_primario        = EXCLUDED.cnae_primario,
    cnaes_secundarios    = EXCLUDED.cnaes_secundarios,
    situacao_cadastral   = EXCLUDED.situacao_cadastral,
    data_abertura        = EXCLUDED.data_abertura,
    porte                = EXCLUDED.porte,
    capital_social       = EXCLUDED.capital_social,
    natureza_juridica    = EXCLUDED.natureza_juridica,
    uf                   = EXCLUDED.uf,
    municipio            = EXCLUDED.municipio,
    cep                  = EXCLUDED.cep,
    endereco             = EXCLUDED.endereco,
    telefone             = EXCLUDED.telefone,
    email                = EXCLUDED.email,
    ultima_atualizacao_rf = EXCLUDED.ultima_atualizacao_rf
"""


def _check_schema(conn: sqlite3.Connection) -> None:
    rows = {r[0] for r in conn.execute(_SCHEMA_CHECK_SQL)}
    expected = {"empresas", "estabelecimento", "municipio"}
    missing = expected - rows
    if missing:
        raise RuntimeError(
            f"SQLite is missing expected tables: {missing}. "
            f"Has rictom/cnpj-sqlite layout changed? Check the upstream README."
        )


def _parse_secondary(csv: str | None) -> list[str]:
    if not csv:
        return []
    return [c.strip() for c in csv.split(",") if c.strip()]


def build_empresa_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    """Stream rows from the SQLite SELECT and yield Postgres-ready dicts."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(_SELECT_SQL)
    for r in cursor:
        yield {
            "cnpj": r["cnpj"],
            "razao_social": r["razao_social"],
            "nome_fantasia": r["nome_fantasia"],
            "cnae_primario": r["cnae_primario"],
            "cnaes_secundarios": _parse_secondary(r["cnaes_sec_csv"]),
            "situacao_cadastral": "ATIVA",
            "data_abertura": parse_yyyymmdd(r["data_abertura_str"]),
            "porte": parse_porte(r["porte_code"]),
            "capital_social": r["capital_social"],
            "natureza_juridica": r["natureza_juridica"],
            "uf": r["uf"],
            "municipio": r["municipio"],
            "cep": r["cep"],
            "endereco": r["endereco"] or None,
            "telefone": r["telefone"] or None,
            "email": r["email"],
            "geom": None,
        }


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL not set")
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    if not DATA_PATH.exists():
        print(
            f"ERROR: {DATA_PATH} not found. Run `make ingest-rf` first.",
            file=sys.stderr,
        )
        return 2

    sqlite_conn = sqlite3.connect(str(DATA_PATH))
    try:
        _check_schema(sqlite_conn)
        pg_conn = await asyncpg.connect(_dsn())
        try:
            t0 = time.perf_counter()
            chunk: list[tuple] = []
            total = 0

            for row in build_empresa_rows(sqlite_conn):
                chunk.append(
                    (
                        row["cnpj"],
                        row["razao_social"],
                        row["nome_fantasia"],
                        row["cnae_primario"],
                        row["cnaes_secundarios"],
                        row["data_abertura"],
                        row["porte"],
                        row["capital_social"],
                        row["natureza_juridica"],
                        row["uf"],
                        row["municipio"],
                        row["cep"],
                        row["endereco"],
                        row["telefone"],
                        row["email"],
                    )
                )
                if len(chunk) >= CHUNK_SIZE:
                    async with pg_conn.transaction():
                        await pg_conn.executemany(UPSERT_SQL, chunk)
                    total += len(chunk)
                    chunk.clear()
                    print(f"  upserted {total:,} rows ({time.perf_counter() - t0:.1f}s)")

            if chunk:
                async with pg_conn.transaction():
                    await pg_conn.executemany(UPSERT_SQL, chunk)
                total += len(chunk)

            await pg_conn.execute("ANALYZE empresas;")
            count = await pg_conn.fetchval("SELECT COUNT(*) FROM empresas")
            elapsed = time.perf_counter() - t0
            print(
                f"\nDone — {total:,} rows upserted, table now has {count:,} rows in {elapsed:.1f}s"
            )

            if count < MIN_EXPECTED_ROWS:
                print(
                    f"WARNING: empresas count = {count:,} < expected >= {MIN_EXPECTED_ROWS:,}. "
                    f"Check upstream RF dump completeness.",
                    file=sys.stderr,
                )
                return 1
        finally:
            await pg_conn.close()
    finally:
        sqlite_conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
