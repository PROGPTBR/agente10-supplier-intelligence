"""Top-N supplier discovery — `empresas` filtered by CNAE (primary OR secondary)."""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class EmpresaCandidate(BaseModel):
    """One candidate supplier returned by find_empresas_by_cnae."""

    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    cnae_primario: str
    primary_match: bool
    uf: str | None
    municipio: str | None
    data_abertura: date | None


_QUERY = text("""
    SELECT
        cnpj,
        razao_social,
        nome_fantasia,
        cnae_primario,
        (cnae_primario = :cnae) AS primary_match,
        uf,
        municipio,
        data_abertura
    FROM empresas
    WHERE (cnae_primario = :cnae OR :cnae = ANY(cnaes_secundarios))
      AND situacao_cadastral = 'ATIVA'
      AND (CAST(:uf AS text) IS NULL OR uf = :uf)
      AND (CAST(:municipio AS text) IS NULL OR municipio = :municipio)
    ORDER BY primary_match DESC,
             capital_social DESC NULLS LAST,
             data_abertura ASC NULLS LAST
    LIMIT :limit
    """)


async def find_empresas_by_cnae(
    db: AsyncSession,
    cnae: str,
    uf: str | None = None,
    municipio: str | None = None,
    limit: int = 25,
) -> list[EmpresaCandidate]:
    """Return up to ``limit`` ATIVA empresas matching ``cnae`` in primary or secondary.

    Ordering: primary matches first, then ``capital_social DESC`` (larger first =
    higher-capacity suppliers), then ``data_abertura ASC`` as a tiebreaker
    (older = more stable). Filters: optional UF and município (exact match).
    """
    result = await db.execute(
        _QUERY,
        {"cnae": cnae, "uf": uf, "municipio": municipio, "limit": limit},
    )
    return [
        EmpresaCandidate(
            cnpj=row.cnpj,
            razao_social=row.razao_social,
            nome_fantasia=row.nome_fantasia,
            cnae_primario=row.cnae_primario,
            primary_match=bool(row.primary_match),
            uf=row.uf,
            municipio=row.municipio,
            data_abertura=row.data_abertura,
        )
        for row in result.all()
    ]
