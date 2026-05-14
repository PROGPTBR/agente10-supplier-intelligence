"""Load IBGE explanatory notes into cnae_taxonomy (UPDATE only — table already populated).

Reads `backend/data/cnae_2.3/notas_ibge.json` and updates:
- cnae_taxonomy.notas_explicativas  ← "Esta subclasse não compreende:" block
- cnae_taxonomy.exemplos_atividades ← "Esta subclasse compreende:" block

Uses batched updates + per-batch reconnect to survive Railway proxy disconnects.

Usage:
    DATABASE_URL=... uv run python scripts/load_ibge_notes.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import asyncpg

DATA_PATH = Path(__file__).parent.parent / "data" / "cnae_2.3" / "notas_ibge.json"

UPDATE_SQL = """
UPDATE cnae_taxonomy SET
    notas_explicativas = $2,
    exemplos_atividades = $3,
    divisao_descricao = $4,
    grupo_descricao = $5
WHERE codigo = $1
"""


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL not set")
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run parse_ibge_notes.py first.", file=sys.stderr)
        return 2

    entries = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    print(f"Loading {len(entries)} IBGE notes...", flush=True)

    t0 = time.perf_counter()
    BATCH = 100
    total = 0
    dsn = _dsn()
    for i in range(0, len(entries), BATCH):
        chunk = entries[i : i + BATCH]
        for attempt in range(3):
            try:
                conn = await asyncpg.connect(dsn, command_timeout=60)
                async with conn.transaction():
                    for e in chunk:
                        await conn.execute(
                            UPDATE_SQL,
                            e["codigo"],
                            e.get("notas_explicativas") or None,
                            e.get("exemplos_atividades") or None,
                            e.get("divisao_descricao") or None,
                            e.get("grupo_descricao") or None,
                        )
                await conn.close()
                total += len(chunk)
                break
            except Exception as exc:
                print(f"  retry {attempt+1} batch {i}: {type(exc).__name__}", flush=True)
                await asyncio.sleep(2)
        else:
            print(f"FAILED at batch {i}", file=sys.stderr)
            return 1
        if (i // BATCH) % 5 == 0:
            print(f"  {total}/{len(entries)} ({time.perf_counter()-t0:.1f}s)", flush=True)

    # Verify
    conn = await asyncpg.connect(dsn, command_timeout=60)
    with_notes = await conn.fetchval(
        "SELECT COUNT(*) FROM cnae_taxonomy WHERE notas_explicativas IS NOT NULL OR exemplos_atividades IS NOT NULL"
    )
    await conn.close()
    print(f"DONE: {total} entries processed in {time.perf_counter()-t0:.1f}s")
    print(f"      {with_notes}/1331 cnae_taxonomy rows now have notas/exemplos")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
