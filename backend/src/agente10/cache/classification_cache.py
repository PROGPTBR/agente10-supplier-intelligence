"""Cross-tenant CNAE classification cache.

Lookups against `spend_classification_cache` allow us to skip Voyage embedding,
pgvector retrieval and Anthropic curator for cluster descriptions already
classified in any previous upload (any tenant).

Cache key is MD5 of the normalized description (NFKD-stripped, lowercase,
single-spaced). TTL defaults to 180 days but a fresh hit always wins.

The embedding column (added in migration 0009) is used for few-shot example
search: given a cluster's embedding, find the top-K cache entries with cosine
similarity ≥ threshold for use as in-context examples to the curator.

Methods stored in `metodo` column have priority order (high → low):
    revisado_humano > golden > curator > retrieval > retrieval_fallback > cache
Higher-priority entries should not be overwritten by lower-priority ones.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Higher number = stronger signal, should not be overwritten by lower.
_METHOD_PRIORITY: dict[str, int] = {
    "revisado_humano": 100,
    "golden": 90,
    "curator": 50,
    "retrieval": 40,
    "retrieval_fallback": 30,
    "cache": 10,
}


def _method_priority(metodo: str | None) -> int:
    return _METHOD_PRIORITY.get(metodo or "", 0)


@dataclass(frozen=True, slots=True)
class CacheEntry:
    cnae: str
    confianca: float
    metodo: str


def normalize_description(s: str) -> str:
    """Normalize for cache lookup: NFKD strip accents, lowercase, single-space."""
    decomposed = unicodedata.normalize("NFKD", s)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only.lower().strip())


def hash_description(s: str) -> str:
    """MD5 of the normalized description — the cache primary key."""
    return hashlib.md5(normalize_description(s).encode("utf-8")).hexdigest()


async def lookup(session: AsyncSession, descricao: str) -> CacheEntry | None:
    """Return the cache entry for this description, or None on miss / expired TTL."""
    h = hash_description(descricao)
    row = (
        await session.execute(
            text(
                "SELECT cnae, confianca, metodo FROM spend_classification_cache "
                "WHERE descricao_hash = :h AND (ttl IS NULL OR ttl > NOW())"
            ),
            {"h": h},
        )
    ).first()
    if not row:
        return None
    return CacheEntry(cnae=row.cnae, confianca=float(row.confianca), metodo=row.metodo)


async def upsert(
    session: AsyncSession,
    descricao: str,
    cnae: str,
    confianca: float,
    metodo: str,
    ttl_days: int = 180,
    embedding: list[float] | None = None,
) -> None:
    """Insert or update cache. Won't downgrade an existing higher-priority entry.

    If `embedding` is provided, persists it for later few-shot NN search.
    """
    h = hash_description(descricao)
    normalized = normalize_description(descricao)
    new_priority = _method_priority(metodo)
    existing = (
        await session.execute(
            text("SELECT metodo FROM spend_classification_cache WHERE descricao_hash = :h"),
            {"h": h},
        )
    ).first()
    if existing and _method_priority(existing.metodo) > new_priority:
        return  # Don't downgrade revisado_humano → curator
    emb_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]" if embedding else None
    await session.execute(
        text(
            "INSERT INTO spend_classification_cache "
            "(descricao_hash, descricao_normalizada, cnae, confianca, metodo, ttl, embedding) "
            "VALUES (:h, :n, :c, :conf, :m, NOW() + (:ttl || ' days')::INTERVAL, "
            "        CAST(:emb AS vector)) "
            "ON CONFLICT (descricao_hash) DO UPDATE SET "
            "  descricao_normalizada = EXCLUDED.descricao_normalizada, "
            "  cnae = EXCLUDED.cnae, "
            "  confianca = EXCLUDED.confianca, "
            "  metodo = EXCLUDED.metodo, "
            "  ttl = EXCLUDED.ttl, "
            "  embedding = COALESCE(EXCLUDED.embedding, spend_classification_cache.embedding)"
        ),
        {
            "h": h,
            "n": normalized,
            "c": cnae,
            "conf": confianca,
            "m": metodo,
            "ttl": str(ttl_days),
            "emb": emb_str,
        },
    )


@dataclass(frozen=True, slots=True)
class FewShotExample:
    descricao: str
    cnae: str
    metodo: str
    similarity: float


async def find_similar_examples(
    session: AsyncSession,
    embedding: list[float],
    k: int = 3,
    min_similarity: float = 0.85,
    prefer_methods: tuple[str, ...] = ("revisado_humano", "golden"),
) -> list[FewShotExample]:
    """Return up to k cache entries similar to `embedding`, preferring high-priority methods.

    Two-pass: first try only `prefer_methods`; if < k found, top up from any method.
    Filters by `similarity >= min_similarity` (cosine).
    """
    emb_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    await session.execute(text("SET ivfflat.probes = 10"))
    found: list[FewShotExample] = []
    seen: set[str] = set()

    # Pass 1: high-priority only
    if prefer_methods:
        rows = (
            await session.execute(
                text(
                    "SELECT descricao_normalizada, cnae, metodo, "
                    "       1 - (embedding <=> CAST(:emb AS vector)) AS similarity "
                    "FROM spend_classification_cache "
                    "WHERE embedding IS NOT NULL AND metodo = ANY(:methods) "
                    "ORDER BY embedding <=> CAST(:emb AS vector) LIMIT :k"
                ),
                {"emb": emb_str, "methods": list(prefer_methods), "k": k},
            )
        ).all()
        for r in rows:
            if r.similarity < min_similarity:
                continue
            if r.descricao_normalizada in seen:
                continue
            seen.add(r.descricao_normalizada)
            found.append(
                FewShotExample(
                    descricao=r.descricao_normalizada,
                    cnae=r.cnae,
                    metodo=r.metodo,
                    similarity=float(r.similarity),
                )
            )

    # Pass 2: top up from any method if needed
    if len(found) < k:
        rows = (
            await session.execute(
                text(
                    "SELECT descricao_normalizada, cnae, metodo, "
                    "       1 - (embedding <=> CAST(:emb AS vector)) AS similarity "
                    "FROM spend_classification_cache "
                    "WHERE embedding IS NOT NULL "
                    "ORDER BY embedding <=> CAST(:emb AS vector) LIMIT :k"
                ),
                {"emb": emb_str, "k": k * 2},
            )
        ).all()
        for r in rows:
            if len(found) >= k:
                break
            if r.similarity < min_similarity:
                continue
            if r.descricao_normalizada in seen:
                continue
            seen.add(r.descricao_normalizada)
            found.append(
                FewShotExample(
                    descricao=r.descricao_normalizada,
                    cnae=r.cnae,
                    metodo=r.metodo,
                    similarity=float(r.similarity),
                )
            )

    return found


async def invalidate(session: AsyncSession, descricao: str) -> None:
    """Remove the cache entry for this description (used when humano corrects CNAE)."""
    await session.execute(
        text("DELETE FROM spend_classification_cache WHERE descricao_hash = :h"),
        {"h": hash_description(descricao)},
    )
