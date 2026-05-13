"""REST endpoints for spend upload lifecycle."""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.integrations.voyage import VoyageClient

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


class UploadStatus(BaseModel):
    upload_id: UUID
    status: str
    linhas_total: int
    linhas_classificadas: int
    erro: str | None


@router.post("/uploads", response_model=UploadCreated, status_code=202)
async def create_upload(
    background: BackgroundTasks,
    tenant_id: UUID = Depends(get_tenant_id),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    nome_arquivo: str = Form(...),
    modo: str = Form("catalogo"),
) -> UploadCreated:
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file too large (>50MB)")

    upload_id = uuid.uuid4()
    storage_dir = Path("/app/data/uploads") / str(tenant_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{upload_id}{Path(nome_arquivo).suffix}"
    storage_path.write_bytes(raw)

    factory = get_session_factory()
    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await session.execute(
                text(
                    "INSERT INTO spend_uploads "
                    "(id, tenant_id, nome_arquivo, object_storage_path, modo, status) "
                    "VALUES (:i, :t, :n, :p, :m, 'pending')"
                ),
                {
                    "i": str(upload_id),
                    "t": str(tenant_id),
                    "n": nome_arquivo,
                    "p": str(storage_path),
                    "m": modo,
                },
            )

    voyage = VoyageClient()
    curator = CuratorClient()
    background.add_task(
        processar_upload,
        upload_id,
        tenant_id,
        storage_path,
        factory,
        voyage,
        curator,
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
                    "SELECT id, status, linhas_total, linhas_classificadas, erro "
                    "FROM spend_uploads WHERE id = :u"
                ),
                {"u": str(upload_id)},
            )
            r = row.first()
    if not r:
        raise HTTPException(404, "upload not found")
    return UploadStatus(
        upload_id=r.id,
        status=r.status,
        linhas_total=r.linhas_total,
        linhas_classificadas=r.linhas_classificadas,
        erro=r.erro,
    )
