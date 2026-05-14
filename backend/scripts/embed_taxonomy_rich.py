"""Generate cnae_taxonomy.embedding_rich = Voyage(denominacao + exemplos_atividades).

The original `embedding` column is built from `denominacao` only — short,
generic, prone to missing the right CNAE when the cluster name is colorful or
uses domain jargon. `embedding_rich` adds the IBGE "Esta subclasse compreende:"
text (concrete activity examples) so retrieval can match against the actual
activities a subclass covers.

Keeping both columns side-by-side lets the classifier do hybrid retrieval
(union of top-K from each) without losing the recall characteristics of the
original embedding.

Usage:
    DATABASE_URL=... VOYAGE_API_KEY=... uv run python scripts/embed_taxonomy_rich.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import asyncpg
import voyageai

BATCH = 50  # Voyage embed accepts up to 128 texts per call


def _build_text(denom: str, exemplos: str | None) -> str:
    """Concatenate denominacao + truncated exemplos for embedding."""
    if not exemplos:
        return denom
    # Cap exemplos at ~800 chars to stay well under Voyage's token limits and
    # avoid one long subclass dominating the embedding space.
    exemplos_short = exemplos[:800].replace("\n", " ")
    return f"{denom}. Inclui: {exemplos_short}"


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    voyage_key = os.environ.get("VOYAGE_API_KEY")
    if not dsn or not voyage_key:
        print("ERROR: DATABASE_URL and VOYAGE_API_KEY are required", file=sys.stderr)
        return 2
    dsn_pg = dsn.replace("postgresql+asyncpg://", "postgresql://")
    voyage = voyageai.AsyncClient(api_key=voyage_key)
    model = os.environ.get("VOYAGE_MODEL", "voyage-3")

    conn = await asyncpg.connect(dsn_pg, command_timeout=60)
    rows = await conn.fetch(
        "SELECT codigo, denominacao, exemplos_atividades FROM cnae_taxonomy "
        "WHERE embedding_rich IS NULL ORDER BY codigo"
    )
    print(f"Embedding {len(rows)} subclasses (model={model})...", flush=True)
    t0 = time.perf_counter()

    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        texts = [_build_text(r["denominacao"], r["exemplos_atividades"]) for r in chunk]
        for attempt in range(3):
            try:
                resp = await voyage.embed(texts, model=model, input_type="document")
                embeddings = resp.embeddings
                break
            except Exception as exc:
                print(f"  voyage retry {attempt + 1}: {type(exc).__name__}", flush=True)
                await asyncio.sleep(2)
        else:
            print(f"FAILED voyage at batch {i}", file=sys.stderr)
            return 1

        # Push to DB — fresh connection per batch keeps Railway proxy happy
        for attempt in range(3):
            try:
                dbconn = await asyncpg.connect(dsn_pg, command_timeout=60)
                async with dbconn.transaction():
                    for r, emb in zip(chunk, embeddings, strict=True):
                        emb_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
                        await dbconn.execute(
                            "UPDATE cnae_taxonomy SET embedding_rich = $1::vector WHERE codigo = $2",
                            emb_str,
                            r["codigo"],
                        )
                await dbconn.close()
                break
            except Exception as exc:
                print(f"  db retry {attempt + 1} batch {i}: {type(exc).__name__}", flush=True)
                await asyncio.sleep(2)
        else:
            print(f"FAILED db at batch {i}", file=sys.stderr)
            return 1

        if (i // BATCH) % 5 == 0:
            print(
                f"  {min(i + BATCH, len(rows))}/{len(rows)} ({time.perf_counter() - t0:.1f}s)",
                flush=True,
            )

    # Verify + refresh ivfflat stats
    conn2 = await asyncpg.connect(dsn_pg, command_timeout=60)
    cnt = await conn2.fetchval(
        "SELECT COUNT(*) FROM cnae_taxonomy WHERE embedding_rich IS NOT NULL"
    )
    await conn2.execute("ANALYZE cnae_taxonomy")
    await conn2.close()
    await conn.close()
    print(f"DONE: {cnt} rows have embedding_rich in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
