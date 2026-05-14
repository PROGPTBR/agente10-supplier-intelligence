"""REST endpoints for spend upload lifecycle."""

from __future__ import annotations

import json
import uuid
from datetime import UTC
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import text

from agente10.core.db import get_session_factory
from agente10.core.tenancy import tenant_context
from agente10.estagio1.csv_parser import CsvParseError, preview_catalog_bytes
from agente10.worker.client import get_pool

router = APIRouter(prefix="/api/v1", tags=["uploads"])

MAX_BYTES = 50 * 1024 * 1024


async def get_tenant_id(x_tenant_id: str = Header(...)) -> UUID:
    try:
        return UUID(x_tenant_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "invalid X-Tenant-ID") from exc


class UploadCreated(BaseModel):
    upload_id: UUID
    status: str


class UploadPreview(BaseModel):
    columns: list[str]
    auto_mapping: dict[str, str]
    sample_rows: list[list[str]]
    needs_mapping: bool


class UploadSummary(BaseModel):
    upload_id: UUID
    nome_arquivo: str
    status: str
    linhas_total: int
    linhas_classificadas: int
    data_upload: str
    progresso_pct: float
    # None while pending; elapsed while processing; final on done/failed
    duracao_segundos: float | None


class UploadStatus(BaseModel):
    upload_id: UUID
    status: str
    linhas_total: int
    linhas_classificadas: int
    erro: str | None
    progresso_pct: float
    clusters_total: int
    clusters_classificados: int  # com cnae assignment
    clusters_com_shortlist: int  # shortlist_gerada=true
    duracao_segundos: float | None


@router.get("/uploads", response_model=list[UploadSummary])
async def list_uploads(
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> list[UploadSummary]:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            result = await session.execute(
                text(
                    "SELECT id, nome_arquivo, status, linhas_total, "
                    "linhas_classificadas, data_upload, data_conclusao "
                    "FROM spend_uploads "
                    "ORDER BY data_upload DESC"
                )
            )
            rows = result.all()
    from datetime import datetime

    out: list[UploadSummary] = []
    for r in rows:
        pct = (r.linhas_classificadas / r.linhas_total * 100.0) if r.linhas_total else 0.0
        if r.status == "pending":
            duracao = None
        elif r.data_conclusao is not None:
            duracao = (r.data_conclusao - r.data_upload).total_seconds()
        else:
            # Still processing — show elapsed so far
            duracao = (datetime.now(UTC) - r.data_upload).total_seconds()
        out.append(
            UploadSummary(
                upload_id=r.id,
                nome_arquivo=r.nome_arquivo,
                status=r.status,
                linhas_total=r.linhas_total,
                linhas_classificadas=r.linhas_classificadas,
                data_upload=r.data_upload.isoformat(),
                progresso_pct=round(pct, 2),
                duracao_segundos=round(duracao, 1) if duracao is not None else None,
            )
        )
    return out


@router.post("/uploads/preview", response_model=UploadPreview)
async def preview_upload(
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> UploadPreview:
    """Inspect a catalog file's headers + sample rows without saving anything.

    Frontend calls this before POST /uploads so the user can map columns
    when our alias table doesn't recognize them.
    """
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file too large (>50MB)")
    try:
        info = preview_catalog_bytes(raw, file.filename or "upload.csv")
    except CsvParseError as exc:
        raise HTTPException(400, str(exc)) from exc
    return UploadPreview(**info)


@router.post("/uploads", response_model=UploadCreated, status_code=202)
async def create_upload(
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    nome_arquivo: str = Form(...),
    modo: str = Form("catalogo"),
    column_mapping: str | None = Form(None),
) -> UploadCreated:
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file too large (>50MB)")

    mapping: dict[str, str] | None = None
    if column_mapping:
        try:
            parsed = json.loads(column_mapping)
            if not isinstance(parsed, dict):
                raise ValueError("column_mapping must be a JSON object")
            mapping = {str(k): str(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(400, f"invalid column_mapping: {exc}") from exc

    upload_id = uuid.uuid4()
    # Best-effort write to the API container's local FS (useful for backups
    # and direct inspection). The worker container can't read this path, so
    # we ALSO persist the bytes in Postgres for cross-container access.
    storage_dir = Path("/app/data/uploads") / str(tenant_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{upload_id}{Path(nome_arquivo).suffix}"
    try:
        storage_path.write_bytes(raw)
    except OSError:
        pass  # FS write is non-critical when bytes are in Postgres

    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await session.execute(
                text(
                    "INSERT INTO spend_uploads "
                    "(id, tenant_id, nome_arquivo, object_storage_path, modo, "
                    " status, file_bytes) "
                    "VALUES (:i, :t, :n, :p, :m, 'pending', :b)"
                ),
                {
                    "i": str(upload_id),
                    "t": str(tenant_id),
                    "n": nome_arquivo,
                    "p": str(storage_path),
                    "m": modo,
                    "b": raw,
                },
            )

    # Enqueue to the persistent arq worker (survives API restarts).
    pool = get_pool()
    await pool.enqueue_job(
        "run_pipeline",
        str(upload_id),
        str(tenant_id),
        str(storage_path),
        mapping,
    )
    return UploadCreated(upload_id=upload_id, status="pending")


@router.get("/uploads/{upload_id}", response_model=UploadStatus)
async def get_upload(
    upload_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> UploadStatus:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            row = await session.execute(
                text(
                    "SELECT id, status, linhas_total, linhas_classificadas, "
                    "erro, data_upload, data_conclusao "
                    "FROM spend_uploads WHERE id = :u"
                ),
                {"u": str(upload_id)},
            )
            r = row.first()
            if not r:
                raise HTTPException(404, "upload not found")
            stats = await session.execute(
                text(
                    "SELECT "
                    "  COUNT(*) AS total, "
                    "  COUNT(*) FILTER (WHERE cnae IS NOT NULL) AS com_cnae, "
                    "  COUNT(*) FILTER (WHERE shortlist_gerada = true) AS com_sl "
                    "FROM spend_clusters WHERE upload_id = :u"
                ),
                {"u": str(upload_id)},
            )
            s = stats.first()
    pct = (r.linhas_classificadas / r.linhas_total * 100.0) if r.linhas_total else 0.0
    from datetime import datetime

    if r.status == "pending":
        duracao = None
    elif r.data_conclusao is not None:
        duracao = (r.data_conclusao - r.data_upload).total_seconds()
    else:
        duracao = (datetime.now(UTC) - r.data_upload).total_seconds()
    return UploadStatus(
        upload_id=r.id,
        status=r.status,
        linhas_total=r.linhas_total,
        linhas_classificadas=r.linhas_classificadas,
        erro=r.erro,
        progresso_pct=round(pct, 2),
        clusters_total=int(s.total) if s else 0,
        clusters_classificados=int(s.com_cnae) if s else 0,
        clusters_com_shortlist=int(s.com_sl) if s else 0,
        duracao_segundos=round(duracao, 1) if duracao is not None else None,
    )


@router.post("/uploads/{upload_id}/retry", response_model=UploadCreated, status_code=202)
async def retry_upload(
    upload_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> UploadCreated:
    """Re-enqueue a stuck or failed upload. Pipeline stages are idempotent
    (parse skips if linhas exist, cnae filters WHERE cnae IS NULL, shortlist
    filters WHERE shortlist_gerada=false), so retry resumes from wherever it
    died rather than redoing finished work.
    """
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            row = (
                await session.execute(
                    text("SELECT object_storage_path FROM spend_uploads WHERE id = :u"),
                    {"u": str(upload_id)},
                )
            ).first()
            if not row:
                raise HTTPException(404, "upload not found")
            # Reset error + status so the UI shows progress again
            await session.execute(
                text("UPDATE spend_uploads SET status='pending', erro=NULL " "WHERE id = :u"),
                {"u": str(upload_id)},
            )

    pool = get_pool()
    await pool.enqueue_job(
        "run_pipeline",
        str(upload_id),
        str(tenant_id),
        row.object_storage_path,
        None,  # column_mapping was already applied on the first try (rows persist)
    )
    return UploadCreated(upload_id=upload_id, status="pending")


@router.delete("/uploads/{upload_id}", status_code=204)
async def delete_upload(
    upload_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
) -> None:
    """Remove an upload and ALL its child data: linhas, clusters, shortlists.

    Shortlists are keyed by (tenant_id, cnae, cnpj) — not per-upload — so we
    only delete supplier_shortlists rows that were INSERTed exclusively because
    of this upload's clusters. Easier safe path: leave supplier_shortlists alone
    (they're cross-upload by design) and only remove this upload's own rows.
    """
    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            existing = (
                await session.execute(
                    text("SELECT 1 FROM spend_uploads WHERE id = :u"),
                    {"u": str(upload_id)},
                )
            ).first()
            if not existing:
                raise HTTPException(404, "upload not found")
            await session.execute(
                text("DELETE FROM spend_linhas WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            await session.execute(
                text("DELETE FROM spend_clusters WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            await session.execute(
                text("DELETE FROM concentracao_categorias WHERE upload_id = :u"),
                {"u": str(upload_id)},
            )
            await session.execute(
                text("DELETE FROM spend_uploads WHERE id = :u"),
                {"u": str(upload_id)},
            )
