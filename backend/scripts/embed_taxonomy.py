"""Embed taxonomy.json with Voyage-3 (input_type='document') -> taxonomy_with_embeddings.json.

Usage:
    cd backend && uv run python scripts/embed_taxonomy.py

Reads:  data/cnae_2.3/taxonomy.json
Writes: data/cnae_2.3/taxonomy_with_embeddings.json (incremental, resumable on failure)

Requires: VOYAGE_API_KEY env var.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agente10.integrations.voyage import VoyageClient

IN_PATH = Path(__file__).parent.parent / "data" / "cnae_2.3" / "taxonomy.json"
OUT_PATH = Path(__file__).parent.parent / "data" / "cnae_2.3" / "taxonomy_with_embeddings.json"
EXPECTED_COUNT = 1331
EXPECTED_DIM = 1024
BATCH_SIZE = 128


def render_doc(row: dict) -> str:
    parts = [row["denominacao"]]
    if row.get("notas_explicativas"):
        parts.append(row["notas_explicativas"])
    if row.get("exemplos_atividades"):
        parts.append(f"Atividades: {row['exemplos_atividades']}")
    text = ". ".join(parts)
    assert len(text) < 30000, f"texto excede limite Voyage para {row['codigo']}"
    return text


def _load_progress() -> dict[str, list[float]]:
    """Load embeddings already computed in a previous (interrupted) run."""
    if not OUT_PATH.exists():
        return {}
    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    return {r["codigo"]: r["embedding"] for r in data if r.get("embedding")}


def _save_progress(rows: list[dict]) -> None:
    """Write rows to OUT_PATH with .6f float precision (keeps file ~7MB)."""

    def _round(o):
        if isinstance(o, float):
            return round(o, 6)
        if isinstance(o, list):
            return [_round(x) for x in o]
        if isinstance(o, dict):
            return {k: _round(v) for k, v in o.items()}
        return o

    OUT_PATH.write_text(
        json.dumps(_round(rows), ensure_ascii=False, indent=None, separators=(",", ":")),
        encoding="utf-8",
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)
async def _embed_batch(client: VoyageClient, texts: list[str]) -> list[list[float]]:
    return await client.embed_documents(texts)


async def main() -> int:
    if not IN_PATH.exists():
        print(f"ERROR: {IN_PATH} not found. Run parse_ibge_xls.py first.", file=sys.stderr)
        return 2

    rows = json.loads(IN_PATH.read_text(encoding="utf-8"))
    if len(rows) != EXPECTED_COUNT:
        print(f"ERROR: input has {len(rows)} rows, expected {EXPECTED_COUNT}.", file=sys.stderr)
        return 1

    already = _load_progress()
    print(f"Resuming with {len(already)} already-embedded subclasses.")

    client = VoyageClient()

    pending_idx = [i for i, r in enumerate(rows) if r["codigo"] not in already]
    print(f"Embedding {len(pending_idx)} pending subclasses in batches of {BATCH_SIZE}...")

    out_rows: list[dict] = []
    for r in rows:
        emb = already.get(r["codigo"])
        out_rows.append({**r, "embedding": emb})

    processed = 0
    for batch_start in range(0, len(pending_idx), BATCH_SIZE):
        batch_indices = pending_idx[batch_start : batch_start + BATCH_SIZE]
        batch_texts = [render_doc(rows[i]) for i in batch_indices]
        embeddings = await _embed_batch(client, batch_texts)
        assert len(embeddings) == len(batch_indices)
        for i, emb in zip(batch_indices, embeddings, strict=True):
            assert len(emb) == EXPECTED_DIM, (
                f"dim {len(emb)} != {EXPECTED_DIM} for {rows[i]['codigo']}"
            )
            out_rows[i]["embedding"] = emb
        processed += len(batch_indices)
        _save_progress(out_rows)
        total_in_file = sum(1 for r in out_rows if r["embedding"])
        print(f"  saved {processed}/{len(pending_idx)} (total in file: {total_in_file})")

    missing = [r["codigo"] for r in out_rows if not r["embedding"]]
    if missing:
        print(
            f"ERROR: {len(missing)} rows still missing embedding: {missing[:5]}...",
            file=sys.stderr,
        )
        return 1
    print(f"Done -- {len(out_rows)} subclasses embedded with {EXPECTED_DIM}-dim vectors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
