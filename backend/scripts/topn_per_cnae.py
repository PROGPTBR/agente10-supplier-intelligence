"""Trim load: top-N empresas per CNAE for every code in `cnae_taxonomy`.

Goal: enlarge the supplier base so the trade-tier auto-suggestion (which can
pick CNAEs in divisões 46/47 outside the original pilot list) returns
non-empty shortlists.

Reads:  backend/data/cnpj.db (40GB SQLite from rictom/cnpj-sqlite)
Writes: Postgres `empresas` — UPSERTs top-N ATIVA empresas per CNAE,
        ranked by capital_social DESC NULLS LAST, data_abertura ASC NULLS LAST.

Idempotent (ON CONFLICT cnpj DO UPDATE). Skips CNAEs whose current population
is already ≥ TOP_N to avoid hammering already-saturated codes.

Usage:
    railway run --service backend uv run python scripts/topn_per_cnae.py
    railway run --service backend uv run python scripts/topn_per_cnae.py --dry-run
    railway run --service backend uv run python scripts/topn_per_cnae.py --top 200
    railway run --service backend uv run python scripts/topn_per_cnae.py --resume 4673700
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
import time
from pathlib import Path

import asyncpg
from empresas_helpers import parse_porte, parse_yyyymmdd

DATA_PATH = Path(__file__).parent.parent / "data" / "cnpj.db"
DEFAULT_TOP_N = 100
PG_BATCH = 200  # rows per UPSERT executemany (keeps each tx small for Railway proxy)

# Per-CNAE pull (uses idx_est_cnae_fiscal — see project memory)
_TOP_N_SQL = """
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
WHERE est.cnae_fiscal = ?
  AND est.situacao_cadastral = '02'
ORDER BY CAST(e.capital_social AS REAL) DESC,
         est.data_inicio_atividades ASC
LIMIT ?
"""

UPSERT_SQL = """
INSERT INTO empresas (
    cnpj, razao_social, nome_fantasia,
    cnae_primario, cnaes_secundarios,
    situacao_cadastral, data_abertura,
    porte, capital_social, natureza_juridica,
    uf, municipio, cep, endereco,
    telefone, email, ultima_atualizacao_rf
)
VALUES (
    $1, $2, $3,
    $4, $5,
    'ATIVA', $6,
    $7, $8, $9,
    $10, $11, $12, $13,
    $14, $15, CURRENT_DATE
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


def _parse_secondary(csv: str | None) -> list[str]:
    if not csv:
        return []
    return [c.strip() for c in csv.split(",") if c.strip()]


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL not set (run under `railway run`)")
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def _row_to_tuple(r: sqlite3.Row) -> tuple:
    return (
        r["cnpj"],
        r["razao_social"],
        r["nome_fantasia"],
        r["cnae_primario"],
        _parse_secondary(r["cnaes_sec_csv"]),
        parse_yyyymmdd(r["data_abertura_str"]),
        parse_porte(r["porte_code"]),
        r["capital_social"],
        r["natureza_juridica"],
        r["uf"],
        r["municipio"],
        r["cep"],
        r["endereco"] or None,
        r["telefone"] or None,
        r["email"],
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_N,
        help="rows per CNAE (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="just print what would happen, no writes",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default="",
        help="resume from this CNAE code (skip earlier codes)",
    )
    parser.add_argument(
        "--codes-file",
        type=str,
        default="",
        help="override: read CNAE list from this file instead of cnae_taxonomy",
    )
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found.", file=sys.stderr)
        return 2

    sqlite_conn = sqlite3.connect(str(DATA_PATH))
    sqlite_conn.row_factory = sqlite3.Row

    pg = await asyncpg.connect(_dsn())
    try:
        # 1. Pull all CNAE codes
        if args.codes_file:
            codes = [
                line.strip()
                for line in Path(args.codes_file).read_text().splitlines()
                if line.strip()
            ]
        else:
            rows = await pg.fetch(
                "SELECT codigo FROM cnae_taxonomy ORDER BY codigo"
            )
            codes = [r["codigo"] for r in rows]
        print(f"Loaded {len(codes)} CNAE codes from "
              f"{'file ' + args.codes_file if args.codes_file else 'cnae_taxonomy'}",
              file=sys.stderr)

        if args.resume:
            codes = [c for c in codes if c >= args.resume]
            print(f"Resuming from {args.resume}: {len(codes)} codes remain",
                  file=sys.stderr)

        t0 = time.perf_counter()
        skipped = 0
        loaded_codes = 0
        inserted = 0

        for i, code in enumerate(codes, 1):
            # Skip if already saturated
            existing = await pg.fetchval(
                "SELECT COUNT(*) FROM empresas WHERE cnae_primario = $1",
                code,
            )
            if existing >= args.top:
                skipped += 1
                if i % 100 == 0:
                    elapsed = time.perf_counter() - t0
                    print(
                        f"  [{i}/{len(codes)}] {code}: SKIP (have {existing}) "
                        f"· loaded={loaded_codes} inserted={inserted} skipped={skipped} "
                        f"({elapsed:.1f}s)",
                        file=sys.stderr,
                    )
                continue

            need = args.top - existing
            rows = sqlite_conn.execute(_TOP_N_SQL, (code, args.top)).fetchall()
            if not rows:
                loaded_codes += 1
                if i % 50 == 0 or len(rows) > 0:
                    print(
                        f"  [{i}/{len(codes)}] {code}: 0 rows in SQLite",
                        file=sys.stderr,
                    )
                continue

            tuples = [_row_to_tuple(r) for r in rows]

            if args.dry_run:
                print(
                    f"  [{i}/{len(codes)}] {code}: would UPSERT {len(tuples)} "
                    f"(have {existing}, need {need})",
                    file=sys.stderr,
                )
            else:
                # Chunked UPSERT (each chunk = its own tx, robust to proxy drops)
                for j in range(0, len(tuples), PG_BATCH):
                    batch = tuples[j : j + PG_BATCH]
                    async with pg.transaction():
                        await pg.executemany(UPSERT_SQL, batch)
                inserted += len(tuples)

            loaded_codes += 1
            elapsed = time.perf_counter() - t0
            if i % 20 == 0 or i == len(codes):
                print(
                    f"  [{i}/{len(codes)}] {code}: "
                    f"{len(tuples)} rows · loaded_codes={loaded_codes} "
                    f"inserted={inserted} skipped={skipped} ({elapsed:.1f}s)",
                    file=sys.stderr,
                )

        if not args.dry_run:
            await pg.execute("ANALYZE empresas;")
            total = await pg.fetchval("SELECT COUNT(*) FROM empresas")
            elapsed = time.perf_counter() - t0
            print(
                f"\nDone — {inserted:,} rows upserted across {loaded_codes} CNAEs "
                f"({skipped} skipped). Table now has {total:,} rows in {elapsed:.1f}s",
                file=sys.stderr,
            )
        else:
            print(f"\nDRY RUN — would touch {loaded_codes} CNAEs", file=sys.stderr)

    finally:
        await pg.close()
        sqlite_conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
