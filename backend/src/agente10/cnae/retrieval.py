"""Top-k retrieval of CNAE subclasses by embedding cosine similarity (pgvector <=>)."""

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CnaeCandidate(BaseModel):
    """One candidate CNAE subclass with its similarity to the query."""

    codigo: str
    denominacao: str
    similarity: float


_TOP_K_SQL = text("""
    SELECT codigo,
           denominacao,
           1 - (embedding <=> CAST(:emb AS vector)) AS similarity
    FROM cnae_taxonomy
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:emb AS vector)
    LIMIT :k
    """)


async def top_k_cnaes(
    db: AsyncSession,
    query_embedding: list[float],
    k: int = 10,
) -> list[CnaeCandidate]:
    """Return the k CNAE subclasses most similar to ``query_embedding`` (cosine)."""
    emb_str = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
    result = await db.execute(_TOP_K_SQL, {"emb": emb_str, "k": k})
    return [
        CnaeCandidate(
            codigo=row.codigo,
            denominacao=row.denominacao,
            similarity=float(row.similarity),
        )
        for row in result.all()
    ]
