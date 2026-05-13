"""Dashboard stats endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from agente10.api.uploads import UploadSummary, get_tenant_id
from agente10.core.db import get_session_factory
from agente10.core.tenancy import tenant_context

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


class DashboardStats(BaseModel):
    uploads_total: int
    uploads_done: int
    clusters_total: int
    clusters_revised: int
    clusters_by_metodo: dict[str, int]
    shortlists_total: int
    recent_uploads: list[UploadSummary]


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> DashboardStats:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            uploads_total = await session.scalar(text("SELECT COUNT(*) FROM spend_uploads"))
            uploads_done = await session.scalar(
                text("SELECT COUNT(*) FROM spend_uploads WHERE status = 'done'")
            )
            clusters_total = await session.scalar(text("SELECT COUNT(*) FROM spend_clusters"))
            clusters_revised = await session.scalar(
                text("SELECT COUNT(*) FROM spend_clusters WHERE revisado_humano = true")
            )
            by_metodo_rows = (
                await session.execute(
                    text(
                        "SELECT cnae_metodo, COUNT(*) AS n FROM spend_clusters "
                        "WHERE cnae_metodo IS NOT NULL GROUP BY cnae_metodo"
                    )
                )
            ).all()
            shortlists_total = await session.scalar(
                text("SELECT COUNT(*) FROM supplier_shortlists")
            )
            recent = (
                await session.execute(
                    text(
                        "SELECT id, nome_arquivo, status, linhas_total, "
                        "linhas_classificadas, data_upload "
                        "FROM spend_uploads ORDER BY data_upload DESC LIMIT 5"
                    )
                )
            ).all()

    recent_uploads: list[UploadSummary] = []
    for r in recent:
        pct = (r.linhas_classificadas / r.linhas_total * 100.0) if r.linhas_total else 0.0
        recent_uploads.append(
            UploadSummary(
                upload_id=r.id,
                nome_arquivo=r.nome_arquivo,
                status=r.status,
                linhas_total=r.linhas_total,
                linhas_classificadas=r.linhas_classificadas,
                data_upload=r.data_upload.isoformat(),
                progresso_pct=round(pct, 2),
            )
        )

    return DashboardStats(
        uploads_total=int(uploads_total or 0),
        uploads_done=int(uploads_done or 0),
        clusters_total=int(clusters_total or 0),
        clusters_revised=int(clusters_revised or 0),
        clusters_by_metodo={r.cnae_metodo: int(r.n) for r in by_metodo_rows},
        shortlists_total=int(shortlists_total or 0),
        recent_uploads=recent_uploads,
    )
