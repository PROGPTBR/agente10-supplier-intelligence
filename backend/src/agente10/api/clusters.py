"""REST endpoints for cluster review and shortlist viewing."""

from __future__ import annotations

from datetime import date as date_t
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from agente10.api.uploads import get_tenant_id
from agente10.core.db import get_session_factory
from agente10.core.tenancy import tenant_context

router = APIRouter(prefix="/api/v1", tags=["clusters"])


class ClusterSummary(BaseModel):
    id: UUID
    nome_cluster: str
    cnae: str | None
    cnae_descricao: str | None
    cnae_confianca: float | None
    cnae_metodo: str | None
    num_linhas: int
    revisado_humano: bool
    shortlist_size: int


class ClusterDetail(BaseModel):
    id: UUID
    upload_id: UUID
    nome_cluster: str
    cnae: str | None
    cnae_descricao: str | None
    cnae_confianca: float | None
    cnae_metodo: str | None
    num_linhas: int
    revisado_humano: bool
    notas_revisor: str | None
    shortlist_gerada: bool
    sample_linhas: list[str]


class ShortlistEntryView(BaseModel):
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    capital_social: float | None
    uf: str | None
    municipio: str | None
    data_abertura: date_t | None
    rank_estagio3: int


@router.get("/uploads/{upload_id}/clusters", response_model=list[ClusterSummary])
async def list_clusters_for_upload(
    upload_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
    metodo: str | None = Query(default=None),
    revisado: bool | None = Query(default=None),
) -> list[ClusterSummary]:
    factory = get_session_factory()
    sql = """
        SELECT
            c.id, c.nome_cluster, c.cnae, ct.denominacao AS cnae_descricao,
            c.cnae_confianca, c.cnae_metodo, c.num_linhas, c.revisado_humano,
            (SELECT COUNT(*) FROM supplier_shortlists s WHERE s.cnae = c.cnae
                AND s.tenant_id = c.tenant_id) AS shortlist_size
        FROM spend_clusters c
        LEFT JOIN cnae_taxonomy ct ON ct.codigo = c.cnae
        WHERE c.upload_id = :u
    """
    params: dict[str, object] = {"u": str(upload_id)}
    if metodo:
        sql += " AND c.cnae_metodo = :m"
        params["m"] = metodo
    if revisado is not None:
        sql += " AND c.revisado_humano = :r"
        params["r"] = revisado
    sql += " ORDER BY c.nome_cluster"

    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            rows = (await session.execute(text(sql), params)).all()
    return [
        ClusterSummary(
            id=r.id,
            nome_cluster=r.nome_cluster,
            cnae=r.cnae,
            cnae_descricao=r.cnae_descricao,
            cnae_confianca=r.cnae_confianca,
            cnae_metodo=r.cnae_metodo,
            num_linhas=r.num_linhas,
            revisado_humano=r.revisado_humano,
            shortlist_size=int(r.shortlist_size),
        )
        for r in rows
    ]


@router.get("/clusters/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(
    cluster_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> ClusterDetail:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            row = (
                await session.execute(
                    text("""
                        SELECT c.id, c.upload_id, c.nome_cluster, c.cnae,
                               ct.denominacao AS cnae_descricao,
                               c.cnae_confianca, c.cnae_metodo, c.num_linhas,
                               c.revisado_humano, c.notas_revisor,
                               c.shortlist_gerada
                        FROM spend_clusters c
                        LEFT JOIN cnae_taxonomy ct ON ct.codigo = c.cnae
                        WHERE c.id = :i
                        """),
                    {"i": str(cluster_id)},
                )
            ).first()
            if not row:
                raise HTTPException(404, "cluster not found")
            sample_rows = (
                await session.execute(
                    text(
                        "SELECT descricao_original FROM spend_linhas "
                        "WHERE cluster_id = :i ORDER BY id LIMIT 5"
                    ),
                    {"i": str(cluster_id)},
                )
            ).all()
    return ClusterDetail(
        id=row.id,
        upload_id=row.upload_id,
        nome_cluster=row.nome_cluster,
        cnae=row.cnae,
        cnae_descricao=row.cnae_descricao,
        cnae_confianca=row.cnae_confianca,
        cnae_metodo=row.cnae_metodo,
        num_linhas=row.num_linhas,
        revisado_humano=row.revisado_humano,
        notas_revisor=row.notas_revisor,
        shortlist_gerada=row.shortlist_gerada,
        sample_linhas=[s.descricao_original for s in sample_rows],
    )


@router.get("/clusters/{cluster_id}/shortlist", response_model=list[ShortlistEntryView])
async def get_cluster_shortlist(
    cluster_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> list[ShortlistEntryView]:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            cnae_row = (
                await session.execute(
                    text("SELECT cnae FROM spend_clusters WHERE id = :i"),
                    {"i": str(cluster_id)},
                )
            ).first()
            if not cnae_row:
                raise HTTPException(404, "cluster not found")
            if not cnae_row.cnae:
                return []
            rows = (
                await session.execute(
                    text("""
                        SELECT s.cnpj_fornecedor AS cnpj, s.rank_estagio3,
                               e.razao_social, e.nome_fantasia, e.capital_social,
                               e.uf, e.municipio, e.data_abertura
                        FROM supplier_shortlists s
                        JOIN empresas e ON e.cnpj = s.cnpj_fornecedor
                        WHERE s.cnae = :c AND s.tenant_id = :t
                        ORDER BY s.rank_estagio3
                        LIMIT 10
                        """),
                    {"c": cnae_row.cnae, "t": str(tenant_id)},
                )
            ).all()
    return [
        ShortlistEntryView(
            cnpj=r.cnpj,
            razao_social=r.razao_social,
            nome_fantasia=r.nome_fantasia,
            capital_social=float(r.capital_social) if r.capital_social is not None else None,
            uf=r.uf,
            municipio=r.municipio,
            data_abertura=r.data_abertura,
            rank_estagio3=r.rank_estagio3,
        )
        for r in rows
    ]
