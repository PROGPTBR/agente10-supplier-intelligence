"""Top-k retrieval of CNAE subclasses by embedding cosine similarity (pgvector <=>)."""

from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CnaeCandidate(BaseModel):
    """One candidate CNAE subclass with its similarity to the query.

    `notas_explicativas` (NÃO compreende) and `exemplos_atividades` (compreende)
    come from the IBGE 600-page book; the original `embedding` is built from
    `denominacao` only, but `embedding_rich` includes the exemplos for hybrid
    retrieval. Notes + hierarchy (divisão/grupo) descriptions are passed to the
    curator for disambiguation.
    """

    codigo: str
    denominacao: str
    similarity: float
    notas_explicativas: str | None = None
    exemplos_atividades: str | None = None
    divisao_descricao: str | None = None
    grupo_descricao: str | None = None


_TOP_K_BASE_SQL = """
    SELECT codigo,
           denominacao,
           notas_explicativas,
           exemplos_atividades,
           divisao_descricao,
           grupo_descricao,
           1 - ({col} <=> CAST(:emb AS vector)) AS similarity
    FROM cnae_taxonomy
    WHERE {col} IS NOT NULL
    ORDER BY {col} <=> CAST(:emb AS vector)
    LIMIT :k
"""


def _row_to_candidate(row: Any) -> CnaeCandidate:
    return CnaeCandidate(
        codigo=row.codigo,
        denominacao=row.denominacao,
        similarity=float(row.similarity),
        notas_explicativas=row.notas_explicativas,
        exemplos_atividades=row.exemplos_atividades,
        divisao_descricao=row.divisao_descricao,
        grupo_descricao=row.grupo_descricao,
    )


async def top_k_cnaes(
    db: AsyncSession,
    query_embedding: list[float],
    k: int = 10,
) -> list[CnaeCandidate]:
    """Top-k against the original `embedding` column (denominacao-only)."""
    emb_str = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
    await db.execute(text("SET ivfflat.probes = 20"))
    sql = text(_TOP_K_BASE_SQL.format(col="embedding"))
    result = await db.execute(sql, {"emb": emb_str, "k": k})
    return [_row_to_candidate(row) for row in result.all()]


async def top_k_cnaes_hybrid(
    db: AsyncSession,
    query_embedding: list[float],
    k: int = 5,
    pool_size: int = 12,
) -> list[CnaeCandidate]:
    """Hybrid retrieval: union top-pool from both `embedding` and `embedding_rich`,
    return up to k unique candidates ranked by best similarity across either signal.

    The denominacao-only embedding has good recall for short/canonical inputs;
    the rich (denom+exemplos) embedding has better recall when the query uses
    jargon or describes activities not literal in the denominação. Union widens
    candidate pool before reranking.
    """
    emb_str = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
    await db.execute(text("SET ivfflat.probes = 20"))

    sql_a = text(_TOP_K_BASE_SQL.format(col="embedding"))
    sql_b = text(_TOP_K_BASE_SQL.format(col="embedding_rich"))
    rows_a = (await db.execute(sql_a, {"emb": emb_str, "k": pool_size})).all()
    rows_b = (await db.execute(sql_b, {"emb": emb_str, "k": pool_size})).all()

    best: dict[str, Any] = {}
    for row in rows_a + rows_b:
        prev = best.get(row.codigo)
        if prev is None or row.similarity > prev.similarity:
            best[row.codigo] = row

    sorted_rows = sorted(best.values(), key=lambda r: r.similarity, reverse=True)[:k]
    return [_row_to_candidate(row) for row in sorted_rows]
