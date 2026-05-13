"""Helper for Task 10 — verify candidate CNPJs are loaded and discover their CNAE.

Usage (after `make load-empresas` completes):
    docker exec agente-supplierdiscovery-backend-1 sh -c \
        "cd /app && uv run python scripts/verify_golden_candidates.py"

Reads CANDIDATES (well-known Brazilian companies' headquarters CNPJs), looks each
up in the loaded `empresas` table, and prints rows ready to paste into
`tests/fixtures/empresas_golden.csv`. Misses are reported on stderr so we can
swap them out before committing the golden CSV.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import NamedTuple

import asyncpg


class Candidate(NamedTuple):
    descricao: str
    cnpj_esperado: str


# Matriz CNPJs (14 digits, ending in 0001-DV) of well-known Brazilian companies.
# Picked to span sectors: oil/gas, mining, banking, retail, beverage, aerospace,
# logistics. CNAE is *not* pre-set — we read it from Postgres so the golden CSV
# matches the dump we actually loaded.
CANDIDATES: list[Candidate] = [
    Candidate("Petrobras",          "33000167000101"),
    Candidate("Vale",               "33592510000154"),
    Candidate("Banco do Brasil",    "00000000000191"),
    Candidate("Itau Unibanco",      "60701190000104"),
    Candidate("Bradesco",           "60746948000112"),
    Candidate("Ambev",              "07526557000100"),
    Candidate("Magazine Luiza",     "47960950000121"),
    Candidate("Lojas Renner",       "92754738000162"),
    Candidate("Embraer",            "07689002000189"),
    Candidate("B3 (Bolsa)",         "09346601000125"),
    # Spares (in case any of the above is BAIXADA/missing in this RF dump):
    Candidate("JBS",                "02916265000160"),
    Candidate("Natura",             "71673990000177"),
]


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL not set")
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    conn = await asyncpg.connect(_dsn())
    try:
        print("descricao,cnpj_esperado,cnae,uf")
        misses: list[Candidate] = []
        for c in CANDIDATES:
            row = await conn.fetchrow(
                "SELECT cnae_primario, uf, razao_social FROM empresas WHERE cnpj = $1",
                c.cnpj_esperado,
            )
            if row is None:
                misses.append(c)
                continue
            print(f"{c.descricao},{c.cnpj_esperado},{row['cnae_primario']},{row['uf']}")

        if misses:
            print(
                f"\nMISSING ({len(misses)}/{len(CANDIDATES)}):", file=sys.stderr
            )
            for c in misses:
                print(f"  - {c.descricao} ({c.cnpj_esperado})", file=sys.stderr)
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
