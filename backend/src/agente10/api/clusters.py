"""REST endpoints for cluster review and shortlist viewing."""

from __future__ import annotations

from datetime import date as date_t
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from agente10.api.uploads import get_tenant_id
from agente10.cache import classification_cache as cache
from agente10.core.db import get_session_factory
from agente10.core.tenancy import tenant_context
from agente10.curator.client import CuratorClient
from agente10.estagio3.shortlist_generator import regenerate_shortlist_for_cluster

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


class ClusterPatch(BaseModel):
    cnae: str | None = None
    notas_revisor: str | None = None
    revisado_humano: bool | None = None
    handoff_rfx: bool | None = None


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
            # DISTINCT ON dedupes (cnae, cnpj) collisions when multiple clusters
            # share the same CNAE (each cluster's _shortlist_stage inserts its
            # own top-10 without UPSERT). Sprint 4: add UNIQUE constraint on
            # supplier_shortlists(tenant_id, cnae, cnpj_fornecedor).
            rows = (
                await session.execute(
                    text("""
                        WITH deduped AS (
                            SELECT DISTINCT ON (s.cnpj_fornecedor)
                                s.cnpj_fornecedor AS cnpj,
                                s.rank_estagio3
                            FROM supplier_shortlists s
                            WHERE s.cnae = :c AND s.tenant_id = :t
                            ORDER BY s.cnpj_fornecedor, s.rank_estagio3
                        )
                        SELECT d.cnpj, d.rank_estagio3,
                               e.razao_social, e.nome_fantasia, e.capital_social,
                               e.uf, e.municipio, e.data_abertura
                        FROM deduped d
                        JOIN empresas e ON e.cnpj = d.cnpj
                        ORDER BY d.rank_estagio3
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


@router.patch("/clusters/{cluster_id}", response_model=ClusterDetail)
async def patch_cluster(
    cluster_id: UUID,
    body: ClusterPatch,
    background: BackgroundTasks,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> ClusterDetail:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            current = (
                await session.execute(
                    text(
                        "SELECT nome_cluster, cnae, cnae_metodo FROM spend_clusters "
                        "WHERE id = :i"
                    ),
                    {"i": str(cluster_id)},
                )
            ).first()
            if not current:
                raise HTTPException(404, "cluster not found")
            cnae_changed = body.cnae is not None and body.cnae != current.cnae

            if cnae_changed:
                # Audit trail BEFORE the UPDATE — preserves the human-correction signal
                # as future training data even if the cluster gets reclassified later.
                await session.execute(
                    text("""
                        INSERT INTO cnae_correction_audit (
                            tenant_id, cluster_id, descricao_cluster,
                            cnae_antes, metodo_antes, cnae_depois, notas_revisor
                        ) VALUES (:t, :i, :d, :ca, :ma, :cd, :n)
                    """),
                    {
                        "t": str(tenant_id),
                        "i": str(cluster_id),
                        "d": current.nome_cluster,
                        "ca": current.cnae,
                        "ma": current.cnae_metodo,
                        "cd": body.cnae,
                        "n": body.notas_revisor,
                    },
                )

            updates: list[str] = []
            params: dict[str, object] = {"i": str(cluster_id)}
            if body.cnae is not None:
                updates.append("cnae = :cnae")
                params["cnae"] = body.cnae
                updates.append("cnae_metodo = 'revisado_humano'")
            if body.notas_revisor is not None:
                updates.append("notas_revisor = :n")
                params["n"] = body.notas_revisor
            if body.revisado_humano is not None:
                updates.append("revisado_humano = :r")
                params["r"] = body.revisado_humano
            if cnae_changed:
                updates.append("shortlist_gerada = false")
            if updates:
                await session.execute(
                    text(f"UPDATE spend_clusters SET {', '.join(updates)} WHERE id = :i"),
                    params,
                )

            if cnae_changed:
                # Cache reflects the human-validated CNAE for this description.
                # Priority 'revisado_humano' won't be downgraded by future curator runs.
                await cache.upsert(
                    session,
                    current.nome_cluster,
                    body.cnae,  # type: ignore[arg-type]
                    confianca=1.0,
                    metodo="revisado_humano",
                )

    if cnae_changed:
        background.add_task(
            regenerate_shortlist_for_cluster,
            cluster_id,
            tenant_id,
            factory,
            CuratorClient(),
        )

    return await get_cluster(cluster_id, tenant_id=tenant_id)
