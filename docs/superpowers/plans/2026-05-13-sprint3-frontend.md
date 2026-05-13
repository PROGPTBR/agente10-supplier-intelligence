# Sprint 3 — Frontend UI + cluster review/shortlist endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the polished MVP UI on top of Sprint 2's pipeline. 5 frontend routes (dashboard, uploads list, upload new, upload detail, cluster detail) + 6 new backend endpoints (uploads list, clusters list/detail/shortlist, PATCH cluster with regen, dashboard stats).

**Architecture:** Next.js 16 App Router consumes FastAPI REST endpoints via fetch wrapper. TanStack Query handles polling for upload progress and optimistic UI for cluster PATCH. CNAE picker uses 1331-row bundled JSON for client-side fuzzy filter. Tenant scoped by `X-Tenant-ID` header from `NEXT_PUBLIC_TENANT_ID` env.

**Tech Stack:** Backend: FastAPI + asyncpg + SQLAlchemy. Frontend: Next.js 16 + React 19 + Tailwind v4 + @base-ui/react + shadcn (button/card/table/badge/input/label/combobox/progress/dialog) + TanStack Query v5 + zod. Vitest + @testing-library/react for frontend tests.

**Spec:** [`docs/superpowers/specs/2026-05-13-sprint3-frontend-design.md`](../specs/2026-05-13-sprint3-frontend-design.md)

**Next.js 16 warning** (from `frontend/AGENTS.md`): This is NOT the Next.js most engineers learned. Before using any Next.js API (router, server components, file conventions, fetch caching), read the relevant guide in `node_modules/next/dist/docs/`.

---

## Task 1: Backend — `progresso_pct` field + GET /api/v1/uploads list

**Files:**
- Modify: `backend/src/agente10/api/uploads.py`
- Test: `backend/tests/integration/test_api_uploads_list.py`

- [ ] **Step 1: Add UploadSummary + UploadStatus.progresso_pct**

Edit `backend/src/agente10/api/uploads.py` — extend `UploadStatus` model and add a list endpoint:

```python
# Add after the existing UploadStatus class
class UploadSummary(BaseModel):
    upload_id: UUID
    nome_arquivo: str
    status: str
    linhas_total: int
    linhas_classificadas: int
    data_upload: str
    progresso_pct: float


# Modify UploadStatus to add progresso_pct
class UploadStatus(BaseModel):
    upload_id: UUID
    status: str
    linhas_total: int
    linhas_classificadas: int
    erro: str | None
    progresso_pct: float
```

In `get_upload`, change the SELECT + response to include `progresso_pct`:

```python
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
    pct = (r.linhas_classificadas / r.linhas_total * 100.0) if r.linhas_total else 0.0
    return UploadStatus(
        upload_id=r.id,
        status=r.status,
        linhas_total=r.linhas_total,
        linhas_classificadas=r.linhas_classificadas,
        erro=r.erro,
        progresso_pct=round(pct, 2),
    )
```

Add a list endpoint above `create_upload`:

```python
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
                    "linhas_classificadas, data_upload "
                    "FROM spend_uploads "
                    "ORDER BY data_upload DESC"
                )
            )
            rows = result.all()
    out: list[UploadSummary] = []
    for r in rows:
        pct = (r.linhas_classificadas / r.linhas_total * 100.0) if r.linhas_total else 0.0
        out.append(
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
    return out
```

- [ ] **Step 2: Write integration test**

```python
# backend/tests/integration/test_api_uploads_list.py
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_list_uploads_returns_ordered_by_data_upload_desc(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    older_id = uuid.uuid4()
    newer_id = uuid.uuid4()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status, data_upload) "
                "VALUES (:i, :t, :n, '/tmp/x', 'done', NOW() - INTERVAL '1 hour')"
            ),
            {"i": str(older_id), "t": str(tenant_id), "n": "older.csv"},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status, linhas_total, linhas_classificadas) "
                "VALUES (:i, :t, :n, '/tmp/y', 'processing', 100, 50)"
            ),
            {"i": str(newer_id), "t": str(tenant_id), "n": "newer.csv"},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/uploads", headers={"X-Tenant-ID": str(tenant_id)})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["upload_id"] == str(newer_id)
    assert body[0]["progresso_pct"] == 50.0
    assert body[1]["upload_id"] == str(older_id)

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id IN (:a, :b)"),
            {"a": str(older_id), "b": str(newer_id)},
        )


@pytest.mark.asyncio
async def test_get_upload_includes_progresso_pct(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status, linhas_total, linhas_classificadas) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'processing', 200, 60)"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}", headers={"X-Tenant-ID": str(tenant_id)}
        )
    assert resp.status_code == 200
    assert resp.json()["progresso_pct"] == 30.0

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"), {"u": str(upload_id)}
        )
```

- [ ] **Step 3: Run tests**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest tests/integration/test_api_uploads_list.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/src/agente10/api/uploads.py backend/tests/integration/test_api_uploads_list.py
git commit -m "feat(backend): api uploads list + progresso_pct field"
```

---

## Task 2: Backend — clusters router (list + detail + shortlist GETs)

**Files:**
- Create: `backend/src/agente10/api/clusters.py`
- Modify: `backend/src/agente10/main.py`
- Test: `backend/tests/integration/test_api_clusters.py`

- [ ] **Step 1: Create clusters router**

```python
# backend/src/agente10/api/clusters.py
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
            id=r.id, nome_cluster=r.nome_cluster, cnae=r.cnae,
            cnae_descricao=r.cnae_descricao, cnae_confianca=r.cnae_confianca,
            cnae_metodo=r.cnae_metodo, num_linhas=r.num_linhas,
            revisado_humano=r.revisado_humano, shortlist_size=int(r.shortlist_size),
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
                    text(
                        """
                        SELECT c.id, c.upload_id, c.nome_cluster, c.cnae,
                               ct.denominacao AS cnae_descricao,
                               c.cnae_confianca, c.cnae_metodo, c.num_linhas,
                               c.revisado_humano, c.notas_revisor,
                               c.shortlist_gerada
                        FROM spend_clusters c
                        LEFT JOIN cnae_taxonomy ct ON ct.codigo = c.cnae
                        WHERE c.id = :i
                        """
                    ),
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
        id=row.id, upload_id=row.upload_id, nome_cluster=row.nome_cluster,
        cnae=row.cnae, cnae_descricao=row.cnae_descricao,
        cnae_confianca=row.cnae_confianca, cnae_metodo=row.cnae_metodo,
        num_linhas=row.num_linhas, revisado_humano=row.revisado_humano,
        notas_revisor=row.notas_revisor, shortlist_gerada=row.shortlist_gerada,
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
                    text(
                        """
                        SELECT s.cnpj_fornecedor AS cnpj, s.rank_estagio3,
                               e.razao_social, e.nome_fantasia, e.capital_social,
                               e.uf, e.municipio, e.data_abertura
                        FROM supplier_shortlists s
                        JOIN empresas e ON e.cnpj = s.cnpj_fornecedor
                        WHERE s.cnae = :c AND s.tenant_id = :t
                        ORDER BY s.rank_estagio3
                        LIMIT 10
                        """
                    ),
                    {"c": cnae_row.cnae, "t": str(tenant_id)},
                )
            ).all()
    return [
        ShortlistEntryView(
            cnpj=r.cnpj, razao_social=r.razao_social, nome_fantasia=r.nome_fantasia,
            capital_social=float(r.capital_social) if r.capital_social is not None else None,
            uf=r.uf, municipio=r.municipio, data_abertura=r.data_abertura,
            rank_estagio3=r.rank_estagio3,
        )
        for r in rows
    ]
```

- [ ] **Step 2: Register router in main.py**

In `backend/src/agente10/main.py`, after the existing `app.include_router(uploads_router)` line, add:

```python
from agente10.api.clusters import router as clusters_router
app.include_router(clusters_router)
```

- [ ] **Step 3: Write integration tests**

```python
# backend/tests/integration/test_api_clusters.py
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_cluster(factory, tenant_id, *, cnae: str | None = "4744001",
                        metodo: str | None = "retrieval", revisado: bool = False):
    upload_id = uuid.uuid4()
    cluster_id = uuid.uuid4()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_clusters "
                "(id, tenant_id, upload_id, nome_cluster, cnae, cnae_confianca, "
                "cnae_metodo, num_linhas, revisado_humano) "
                "VALUES (:i, :t, :u, 'Parafusos', :cnae, 0.92, :m, 6, :r)"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id),
             "cnae": cnae, "m": metodo, "r": revisado},
        )
        for n in range(3):
            await session.execute(
                text(
                    "INSERT INTO spend_linhas (tenant_id, upload_id, "
                    "descricao_original, cluster_id) "
                    "VALUES (:t, :u, :d, :c)"
                ),
                {"t": str(tenant_id), "u": str(upload_id),
                 "d": f"Parafuso M{n}", "c": str(cluster_id)},
            )
    return upload_id, cluster_id


async def _cleanup(factory, tenant_id, upload_id):
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        for table in ("spend_linhas", "spend_clusters", "spend_uploads"):
            await session.execute(
                text(f"DELETE FROM {table} WHERE upload_id = :u OR id = :u"),
                {"u": str(upload_id)},
            )


@pytest.mark.asyncio
async def test_list_clusters_for_upload(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, cluster_id = await _seed_cluster(factory, tenant_id)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}/clusters",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["nome_cluster"] == "Parafusos"
    assert body[0]["cnae"] == "4744001"
    assert body[0]["num_linhas"] == 6
    await _cleanup(factory, tenant_id, upload_id)


@pytest.mark.asyncio
async def test_list_clusters_filters_by_metodo(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, _ = await _seed_cluster(factory, tenant_id, metodo="retrieval")

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/uploads/{upload_id}/clusters?metodo=curator",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json() == []
    await _cleanup(factory, tenant_id, upload_id)


@pytest.mark.asyncio
async def test_get_cluster_detail_includes_sample_linhas(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, cluster_id = await _seed_cluster(factory, tenant_id)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/clusters/{cluster_id}",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome_cluster"] == "Parafusos"
    assert len(body["sample_linhas"]) == 3
    assert body["sample_linhas"][0].startswith("Parafuso")
    await _cleanup(factory, tenant_id, upload_id)


@pytest.mark.asyncio
async def test_get_shortlist_returns_empty_when_no_entries(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    tenant_id, _ = two_tenants
    upload_id, cluster_id = await _seed_cluster(factory, tenant_id)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/v1/clusters/{cluster_id}/shortlist",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json() == []
    await _cleanup(factory, tenant_id, upload_id)
```

- [ ] **Step 4: Run tests**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest tests/integration/test_api_clusters.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/api/clusters.py backend/src/agente10/main.py backend/tests/integration/test_api_clusters.py
git commit -m "feat(backend): clusters router (list/detail/shortlist GETs)"
```

---

## Task 3: Backend — PATCH /clusters/{id} + shortlist regen background task

**Files:**
- Modify: `backend/src/agente10/api/clusters.py`
- Modify: `backend/src/agente10/estagio3/shortlist_generator.py` (add helper)
- Test: `backend/tests/integration/test_api_cluster_patch.py`

- [ ] **Step 1: Add single-cluster shortlist regen helper**

In `backend/src/agente10/estagio3/shortlist_generator.py`, after `generate_shortlist`, add:

```python
async def regenerate_shortlist_for_cluster(
    cluster_id: UUID,
    tenant_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    curator: CuratorClient,
) -> None:
    """Re-run Estágio 3 for a single cluster: delete old shortlist, re-insert new."""
    from agente10.core.tenancy import tenant_context
    from agente10.curator.shortlist_reranker import rerank_top10
    from agente10.empresas.discovery import find_empresas_by_cnae
    from functools import partial
    from sqlalchemy import text

    async with session_factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            cluster = (
                await session.execute(
                    text("SELECT id, cnae, nome_cluster FROM spend_clusters WHERE id = :i"),
                    {"i": str(cluster_id)},
                )
            ).first()
            if not cluster or not cluster.cnae:
                return
            await session.execute(
                text(
                    "DELETE FROM supplier_shortlists "
                    "WHERE cnae = :c AND tenant_id = :t"
                ),
                {"c": cluster.cnae, "t": str(tenant_id)},
            )
            entries = await generate_shortlist(
                cluster.nome_cluster, cluster.cnae,
                discovery=lambda cnae: find_empresas_by_cnae(session, cnae, limit=25),
                rerank=partial(rerank_top10, curator),
            )
            for entry in entries:
                await session.execute(
                    text(
                        "INSERT INTO supplier_shortlists "
                        "(tenant_id, cnae, cnpj_fornecedor, rank_estagio3) "
                        "VALUES (:t, :c, :cnpj, :r)"
                    ),
                    {"t": str(tenant_id), "c": cluster.cnae,
                     "cnpj": entry.cnpj, "r": entry.rank_estagio3},
                )
            await session.execute(
                text(
                    "UPDATE spend_clusters SET shortlist_gerada = true WHERE id = :i"
                ),
                {"i": str(cluster_id)},
            )
```

Also add the missing imports at the top of the file:

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from agente10.curator.client import CuratorClient
```

- [ ] **Step 2: Add PATCH endpoint to clusters.py**

In `backend/src/agente10/api/clusters.py`, add `BackgroundTasks` import + PATCH endpoint:

```python
# Update imports at top
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from agente10.curator.client import CuratorClient
from agente10.estagio3.shortlist_generator import regenerate_shortlist_for_cluster


class ClusterPatch(BaseModel):
    cnae: str | None = None
    notas_revisor: str | None = None
    revisado_humano: bool | None = None
    handoff_rfx: bool | None = None


# Add this endpoint after get_cluster_shortlist
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
                    text("SELECT cnae FROM spend_clusters WHERE id = :i"),
                    {"i": str(cluster_id)},
                )
            ).first()
            if not current:
                raise HTTPException(404, "cluster not found")
            cnae_changed = body.cnae is not None and body.cnae != current.cnae

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
                    text(
                        f"UPDATE spend_clusters SET {', '.join(updates)} WHERE id = :i"
                    ),
                    params,
                )

    if cnae_changed:
        background.add_task(
            regenerate_shortlist_for_cluster,
            cluster_id, tenant_id, factory, CuratorClient(),
        )

    return await get_cluster(cluster_id, tenant_id=tenant_id)
```

- [ ] **Step 3: Write integration test**

```python
# backend/tests/integration/test_api_cluster_patch.py
import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_patch_cluster_notas_does_not_trigger_regen(db_engine, two_tenants, monkeypatch):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker

    regen_called = False
    async def fake_regen(*args, **kwargs):
        nonlocal regen_called
        regen_called = True
    monkeypatch.setattr(
        "agente10.api.clusters.regenerate_shortlist_for_cluster", fake_regen
    )

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()
    cluster_id = uuid.uuid4()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_clusters (id, tenant_id, upload_id, "
                "nome_cluster, cnae, cnae_confianca, cnae_metodo) "
                "VALUES (:i, :t, :u, 'X', '4744001', 0.9, 'retrieval')"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/clusters/{cluster_id}",
            json={"notas_revisor": "ok", "revisado_humano": True},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["notas_revisor"] == "ok"
    assert resp.json()["revisado_humano"] is True
    assert not regen_called

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )


@pytest.mark.asyncio
async def test_patch_cluster_cnae_triggers_regen(db_engine, two_tenants, monkeypatch):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker

    regen_called = False
    async def fake_regen(*args, **kwargs):
        nonlocal regen_called
        regen_called = True
    monkeypatch.setattr(
        "agente10.api.clusters.regenerate_shortlist_for_cluster", fake_regen
    )

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()
    cluster_id = uuid.uuid4()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_clusters (id, tenant_id, upload_id, "
                "nome_cluster, cnae, cnae_confianca, cnae_metodo, shortlist_gerada) "
                "VALUES (:i, :t, :u, 'X', '4744001', 0.9, 'retrieval', true)"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/v1/clusters/{cluster_id}",
            json={"cnae": "4673700"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["cnae"] == "4673700"
    # BackgroundTask runs after the response is dispatched
    await asyncio.sleep(0.1)
    assert regen_called

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        flag = await session.scalar(
            text("SELECT shortlist_gerada FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
    assert flag is False
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
```

- [ ] **Step 4: Run tests**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest tests/integration/test_api_cluster_patch.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/api/clusters.py backend/src/agente10/estagio3/shortlist_generator.py backend/tests/integration/test_api_cluster_patch.py
git commit -m "feat(backend): PATCH /clusters/{id} + shortlist regen background task"
```

---

## Task 4: Backend — dashboard stats endpoint

**Files:**
- Create: `backend/src/agente10/api/dashboard.py`
- Modify: `backend/src/agente10/main.py`
- Test: `backend/tests/integration/test_api_dashboard.py`

- [ ] **Step 1: Create dashboard router**

```python
# backend/src/agente10/api/dashboard.py
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
            uploads_total = await session.scalar(
                text("SELECT COUNT(*) FROM spend_uploads")
            )
            uploads_done = await session.scalar(
                text("SELECT COUNT(*) FROM spend_uploads WHERE status = 'done'")
            )
            clusters_total = await session.scalar(
                text("SELECT COUNT(*) FROM spend_clusters")
            )
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
                upload_id=r.id, nome_arquivo=r.nome_arquivo, status=r.status,
                linhas_total=r.linhas_total, linhas_classificadas=r.linhas_classificadas,
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
```

- [ ] **Step 2: Register in main.py**

In `backend/src/agente10/main.py`, add:

```python
from agente10.api.dashboard import router as dashboard_router
app.include_router(dashboard_router)
```

- [ ] **Step 3: Write integration test**

```python
# backend/tests/integration/test_api_dashboard.py
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_dashboard_stats_counts(db_engine, two_tenants):
    from agente10 import main as main_module
    from sqlalchemy.ext.asyncio import async_sessionmaker

    tenant_id, _ = two_tenants
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    upload_id = uuid.uuid4()
    cluster_id = uuid.uuid4()

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_uploads (id, tenant_id, nome_arquivo, "
                "object_storage_path, status) "
                "VALUES (:i, :t, 'x.csv', '/tmp/x', 'done')"
            ),
            {"i": str(upload_id), "t": str(tenant_id)},
        )
        await session.execute(
            text(
                "INSERT INTO spend_clusters (id, tenant_id, upload_id, "
                "nome_cluster, cnae, cnae_metodo, revisado_humano) "
                "VALUES (:i, :t, :u, 'X', '4744001', 'retrieval', true)"
            ),
            {"i": str(cluster_id), "t": str(tenant_id), "u": str(upload_id)},
        )

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/dashboard/stats",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["uploads_total"] >= 1
    assert body["uploads_done"] >= 1
    assert body["clusters_total"] >= 1
    assert body["clusters_revised"] >= 1
    assert body["clusters_by_metodo"].get("retrieval", 0) >= 1
    assert any(u["upload_id"] == str(upload_id) for u in body["recent_uploads"])

    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        await session.execute(
            text("DELETE FROM spend_clusters WHERE id = :i"),
            {"i": str(cluster_id)},
        )
        await session.execute(
            text("DELETE FROM spend_uploads WHERE id = :u"),
            {"u": str(upload_id)},
        )
```

- [ ] **Step 4: Run tests**

```bash
docker compose run --rm \
  -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
  backend uv run pytest tests/integration/test_api_dashboard.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/agente10/api/dashboard.py backend/src/agente10/main.py backend/tests/integration/test_api_dashboard.py
git commit -m "feat(backend): dashboard stats endpoint"
```

---

## Task 5: Frontend — deps + CNAE taxonomy bundle script

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/scripts/build-cnae-bundle.mjs`
- Create: `frontend/lib/cnae-taxonomy.json` (generated)

- [ ] **Step 1: Add deps**

```bash
cd frontend && pnpm add @tanstack/react-query zod && pnpm add -D @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

Verify `package.json` has the new entries under `dependencies` and `devDependencies`.

- [ ] **Step 2: Create CNAE bundle script**

```javascript
// frontend/scripts/build-cnae-bundle.mjs
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = join(__dirname, "..", "..", "backend", "data", "cnae_2.3", "taxonomy_with_embeddings.json");
const dst = join(__dirname, "..", "lib", "cnae-taxonomy.json");

const raw = JSON.parse(await readFile(src, "utf-8"));
// Strip embeddings; keep only codigo + denominacao for client picker
const stripped = raw.map((entry) => ({
  codigo: entry.codigo,
  denominacao: entry.denominacao,
}));
await writeFile(dst, JSON.stringify(stripped));
console.log(`Wrote ${stripped.length} CNAEs to ${dst}`);
```

- [ ] **Step 3: Add build:cnae script to package.json**

In `frontend/package.json` `scripts`:

```json
{
  "scripts": {
    "build:cnae": "node scripts/build-cnae-bundle.mjs"
  }
}
```

- [ ] **Step 4: Run bundle script**

```bash
cd frontend && pnpm build:cnae
```

Expected output: `Wrote 1331 CNAEs to .../lib/cnae-taxonomy.json` and a new ~80KB JSON file.

- [ ] **Step 5: Verify size**

```bash
ls -lh frontend/lib/cnae-taxonomy.json
```

Expected: < 200KB.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/scripts/build-cnae-bundle.mjs frontend/lib/cnae-taxonomy.json
git commit -m "feat(frontend): add TanStack Query + zod + CNAE taxonomy bundle"
```

---

## Task 6: Frontend — API client, tenant config, types

**Files:**
- Create: `frontend/lib/tenant.ts`
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api/client.ts`
- Create: `frontend/lib/api/uploads.ts`
- Create: `frontend/lib/api/clusters.ts`
- Create: `frontend/lib/api/dashboard.ts`
- Create: `frontend/tests/api/client.test.ts`
- Create: `frontend/vitest.config.ts` (if not present)
- Create: `frontend/tests/setup.ts`

- [ ] **Step 1: Vitest setup**

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
});
```

Add `@vitejs/plugin-react`:

```bash
cd frontend && pnpm add -D @vitejs/plugin-react
```

Create `frontend/tests/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

Add to `frontend/package.json` scripts:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 2: tenant.ts**

```typescript
// frontend/lib/tenant.ts
export function readTenantId(): string {
  const tenant = process.env.NEXT_PUBLIC_TENANT_ID;
  if (!tenant) {
    throw new Error("NEXT_PUBLIC_TENANT_ID env var is required");
  }
  return tenant;
}

export function readApiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}
```

- [ ] **Step 3: types.ts (zod schemas)**

```typescript
// frontend/lib/types.ts
import { z } from "zod";

export const UploadSummary = z.object({
  upload_id: z.string().uuid(),
  nome_arquivo: z.string(),
  status: z.string(),
  linhas_total: z.number(),
  linhas_classificadas: z.number(),
  data_upload: z.string(),
  progresso_pct: z.number(),
});
export type UploadSummary = z.infer<typeof UploadSummary>;

export const UploadStatus = UploadSummary.extend({
  erro: z.string().nullable(),
}).omit({ nome_arquivo: true, data_upload: true });
export type UploadStatus = z.infer<typeof UploadStatus>;

export const ClusterSummary = z.object({
  id: z.string().uuid(),
  nome_cluster: z.string(),
  cnae: z.string().nullable(),
  cnae_descricao: z.string().nullable(),
  cnae_confianca: z.number().nullable(),
  cnae_metodo: z.string().nullable(),
  num_linhas: z.number(),
  revisado_humano: z.boolean(),
  shortlist_size: z.number(),
});
export type ClusterSummary = z.infer<typeof ClusterSummary>;

export const ClusterDetail = z.object({
  id: z.string().uuid(),
  upload_id: z.string().uuid(),
  nome_cluster: z.string(),
  cnae: z.string().nullable(),
  cnae_descricao: z.string().nullable(),
  cnae_confianca: z.number().nullable(),
  cnae_metodo: z.string().nullable(),
  num_linhas: z.number(),
  revisado_humano: z.boolean(),
  notas_revisor: z.string().nullable(),
  shortlist_gerada: z.boolean(),
  sample_linhas: z.array(z.string()),
});
export type ClusterDetail = z.infer<typeof ClusterDetail>;

export const ShortlistEntry = z.object({
  cnpj: z.string(),
  razao_social: z.string(),
  nome_fantasia: z.string().nullable(),
  capital_social: z.number().nullable(),
  uf: z.string().nullable(),
  municipio: z.string().nullable(),
  data_abertura: z.string().nullable(),
  rank_estagio3: z.number(),
});
export type ShortlistEntry = z.infer<typeof ShortlistEntry>;

export const DashboardStats = z.object({
  uploads_total: z.number(),
  uploads_done: z.number(),
  clusters_total: z.number(),
  clusters_revised: z.number(),
  clusters_by_metodo: z.record(z.string(), z.number()),
  shortlists_total: z.number(),
  recent_uploads: z.array(UploadSummary),
});
export type DashboardStats = z.infer<typeof DashboardStats>;
```

- [ ] **Step 4: Write client.test.ts**

```typescript
// frontend/tests/api/client.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiFetch } from "../../lib/api/client";

describe("apiFetch", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_TENANT_ID = "00000000-0000-0000-0000-000000000001";
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    global.fetch = vi.fn();
  });

  it("injects X-Tenant-ID header", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    } as Response);

    await apiFetch("/x");

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const init = call[1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-Tenant-ID"]).toBe(
      "00000000-0000-0000-0000-000000000001",
    );
    expect(call[0]).toBe("http://api.test/x");
  });

  it("throws on non-ok response with detail", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "bad request" }),
    } as Response);

    await expect(apiFetch("/x")).rejects.toThrow(/bad request/);
  });
});
```

- [ ] **Step 5: Implement client.ts**

```typescript
// frontend/lib/api/client.ts
import { readApiBase, readTenantId } from "../tenant";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-ID": readTenantId(),
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (init.body && !(init.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }
  const resp = await fetch(`${readApiBase()}${path}`, { ...init, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
```

- [ ] **Step 6: Implement uploads.ts (TanStack hooks)**

```typescript
// frontend/lib/api/uploads.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./client";
import { UploadStatus, UploadSummary } from "../types";

export function useUploadsQuery() {
  return useQuery({
    queryKey: ["uploads"],
    queryFn: async () => z.array(UploadSummary).parse(await apiFetch("/api/v1/uploads")),
  });
}

export function useUploadStatusQuery(uploadId: string) {
  return useQuery({
    queryKey: ["uploads", uploadId],
    queryFn: async () =>
      UploadStatus.parse(await apiFetch(`/api/v1/uploads/${uploadId}`)),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 2000;
    },
    enabled: !!uploadId,
  });
}

export function useCreateUploadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("nome_arquivo", file.name);
      return await apiFetch<{ upload_id: string; status: string }>(
        "/api/v1/uploads",
        { method: "POST", body: fd },
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["uploads"] }),
  });
}
```

- [ ] **Step 7: Implement clusters.ts**

```typescript
// frontend/lib/api/clusters.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./client";
import { ClusterDetail, ClusterSummary, ShortlistEntry } from "../types";

export function useClustersQuery(
  uploadId: string,
  filters: { metodo?: string; revisado?: boolean } = {},
) {
  const params = new URLSearchParams();
  if (filters.metodo) params.set("metodo", filters.metodo);
  if (filters.revisado !== undefined) params.set("revisado", String(filters.revisado));
  const query = params.toString();
  return useQuery({
    queryKey: ["clusters", uploadId, filters],
    queryFn: async () =>
      z.array(ClusterSummary).parse(
        await apiFetch(
          `/api/v1/uploads/${uploadId}/clusters${query ? `?${query}` : ""}`,
        ),
      ),
    enabled: !!uploadId,
  });
}

export function useClusterDetailQuery(clusterId: string) {
  return useQuery({
    queryKey: ["clusters", clusterId, "detail"],
    queryFn: async () =>
      ClusterDetail.parse(await apiFetch(`/api/v1/clusters/${clusterId}`)),
    enabled: !!clusterId,
  });
}

export function useShortlistQuery(clusterId: string, shortlistGerada: boolean | undefined) {
  return useQuery({
    queryKey: ["clusters", clusterId, "shortlist"],
    queryFn: async () =>
      z.array(ShortlistEntry).parse(
        await apiFetch(`/api/v1/clusters/${clusterId}/shortlist`),
      ),
    enabled: !!clusterId,
    refetchInterval: shortlistGerada === false ? 2000 : false,
  });
}

export interface ClusterPatchBody {
  cnae?: string;
  notas_revisor?: string;
  revisado_humano?: boolean;
}

export function usePatchClusterMutation(clusterId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClusterPatchBody) =>
      ClusterDetail.parse(
        await apiFetch(`/api/v1/clusters/${clusterId}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["clusters", clusterId, "detail"], data);
      qc.invalidateQueries({ queryKey: ["clusters", clusterId, "shortlist"] });
      qc.invalidateQueries({ queryKey: ["clusters", data.upload_id] });
    },
  });
}
```

- [ ] **Step 8: Implement dashboard.ts**

```typescript
// frontend/lib/api/dashboard.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { DashboardStats } from "../types";

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => DashboardStats.parse(await apiFetch("/api/v1/dashboard/stats")),
    refetchOnWindowFocus: true,
  });
}
```

- [ ] **Step 9: Run client tests**

```bash
cd frontend && pnpm test client.test
```

Expected: 2 passed.

- [ ] **Step 10: Commit**

```bash
git add frontend/lib/ frontend/tests/ frontend/vitest.config.ts frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat(frontend): api client + tenant config + types + tanstack hooks"
```

---

## Task 7: Frontend — AppShell + global layout + base shadcn components

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/page.tsx`
- Create: `frontend/app/providers.tsx`
- Create: `frontend/components/shell/AppShell.tsx`
- Create: `frontend/components/shell/SidebarNav.tsx`
- Create: `frontend/components/ui/button.tsx`, `card.tsx`, `badge.tsx` (via shadcn CLI)

- [ ] **Step 1: Generate shadcn base components**

```bash
cd frontend && pnpm dlx shadcn@latest add button card badge input label table progress dialog combobox
```

If `shadcn` is not installed, run `pnpm dlx shadcn-ui@latest init` first and accept defaults (Tailwind v4, @base-ui). This populates `components/ui/`.

- [ ] **Step 2: Create QueryClient provider**

```typescript
// frontend/app/providers.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 3: Sidebar nav**

```typescript
// frontend/components/shell/SidebarNav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/uploads", label: "Uploads" },
];

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 p-4" aria-label="Navegação principal">
      {NAV.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-2 text-sm font-medium ${
              active
                ? "bg-zinc-900 text-white"
                : "text-zinc-700 hover:bg-zinc-100"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 4: AppShell**

```typescript
// frontend/components/shell/AppShell.tsx
import { SidebarNav } from "./SidebarNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="border-r border-zinc-200 bg-zinc-50">
        <div className="px-4 py-6">
          <h1 className="text-lg font-semibold">Agente 10</h1>
          <p className="text-xs text-zinc-500">Supplier Intelligence</p>
        </div>
        <SidebarNav />
      </aside>
      <main className="overflow-y-auto p-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 5: Update root layout**

```typescript
// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "../components/shell/AppShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Agente 10 — Supplier Intelligence",
  description: "Pipeline de descoberta de fornecedores",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Replace placeholder page with redirect**

```typescript
// frontend/app/page.tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
```

- [ ] **Step 7: Manual sanity check**

Start dev server, verify routes load without errors:

```bash
cd frontend && pnpm dev
```

Open `http://localhost:3000` — should redirect to `/dashboard` (which will 404 since not built yet — that's fine for this task). Sidebar should appear with Dashboard + Uploads links.

- [ ] **Step 8: Commit**

```bash
git add frontend/app/ frontend/components/
git commit -m "feat(frontend): root layout + QueryProvider + AppShell sidebar"
```

---

## Task 8: Frontend — Dashboard page

**Files:**
- Create: `frontend/app/dashboard/page.tsx`
- Create: `frontend/components/dashboard/StatCard.tsx`
- Create: `frontend/components/dashboard/ClustersByMetodoChart.tsx`
- Create: `frontend/components/dashboard/RecentUploadsList.tsx`

- [ ] **Step 1: StatCard component**

```typescript
// frontend/components/dashboard/StatCard.tsx
import { Card } from "../ui/card";

export function StatCard({ label, value, sublabel }: {
  label: string;
  value: string | number;
  sublabel?: string;
}) {
  return (
    <Card className="p-6">
      <p className="text-sm font-medium text-zinc-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      {sublabel && <p className="mt-1 text-xs text-zinc-500">{sublabel}</p>}
    </Card>
  );
}
```

- [ ] **Step 2: ClustersByMetodoChart (CSS only)**

```typescript
// frontend/components/dashboard/ClustersByMetodoChart.tsx
const COLORS: Record<string, string> = {
  retrieval: "bg-emerald-500",
  curator: "bg-sky-500",
  manual_pending: "bg-amber-500",
  retrieval_fallback: "bg-zinc-500",
  revisado_humano: "bg-purple-500",
};

const LABELS: Record<string, string> = {
  retrieval: "Auto",
  curator: "Curator LLM",
  manual_pending: "Manual",
  retrieval_fallback: "Fallback",
  revisado_humano: "Revisado",
};

export function ClustersByMetodoChart({ data }: { data: Record<string, number> }) {
  const total = Object.values(data).reduce((s, n) => s + n, 0) || 1;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-zinc-700">Clusters por método</p>
      <div className="flex h-3 overflow-hidden rounded-full bg-zinc-100">
        {Object.entries(data).map(([k, n]) => (
          <div
            key={k}
            className={COLORS[k] ?? "bg-zinc-400"}
            style={{ width: `${(n / total) * 100}%` }}
            aria-label={`${LABELS[k] ?? k}: ${n}`}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-3 text-xs">
        {Object.entries(data).map(([k, n]) => (
          <li key={k} className="flex items-center gap-1.5">
            <span className={`inline-block size-2 rounded-sm ${COLORS[k] ?? "bg-zinc-400"}`} />
            <span className="text-zinc-700">{LABELS[k] ?? k}: {n}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: RecentUploadsList**

```typescript
// frontend/components/dashboard/RecentUploadsList.tsx
import Link from "next/link";
import { Badge } from "../ui/badge";
import type { UploadSummary } from "../../lib/types";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  done: "default",
  processing: "secondary",
  pending: "secondary",
  failed: "destructive",
};

export function RecentUploadsList({ uploads }: { uploads: UploadSummary[] }) {
  if (uploads.length === 0) {
    return <p className="text-sm text-zinc-500">Nenhum upload ainda.</p>;
  }
  return (
    <ul className="divide-y divide-zinc-200">
      {uploads.map((u) => (
        <li key={u.upload_id} className="flex items-center justify-between py-3">
          <Link
            href={`/uploads/${u.upload_id}`}
            className="text-sm font-medium text-zinc-900 hover:underline"
          >
            {u.nome_arquivo}
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-500">
              {u.linhas_classificadas}/{u.linhas_total} linhas
            </span>
            <Badge variant={STATUS_VARIANT[u.status] ?? "secondary"}>{u.status}</Badge>
          </div>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Dashboard page**

```typescript
// frontend/app/dashboard/page.tsx
"use client";

import { useDashboardStats } from "../../lib/api/dashboard";
import { StatCard } from "../../components/dashboard/StatCard";
import { ClustersByMetodoChart } from "../../components/dashboard/ClustersByMetodoChart";
import { RecentUploadsList } from "../../components/dashboard/RecentUploadsList";

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardStats();

  if (isLoading) return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (error || !data) {
    return <p className="text-sm text-red-600">Erro ao carregar dashboard.</p>;
  }

  const revisado_pct =
    data.clusters_total > 0 ? (data.clusters_revised / data.clusters_total) * 100 : 0;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Uploads totais" value={data.uploads_total} />
        <StatCard
          label="Uploads concluídos"
          value={data.uploads_done}
          sublabel={`${data.uploads_total - data.uploads_done} em andamento`}
        />
        <StatCard label="Clusters" value={data.clusters_total} />
        <StatCard
          label="Revisados"
          value={`${revisado_pct.toFixed(0)}%`}
          sublabel={`${data.clusters_revised} de ${data.clusters_total}`}
        />
      </div>
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <ClustersByMetodoChart data={data.clusters_by_metodo} />
      </div>
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-medium">Uploads recentes</h2>
        <RecentUploadsList uploads={data.recent_uploads} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify in browser**

```bash
cd frontend && pnpm dev
```

Open `http://localhost:3000/dashboard`. With backend running and at least one upload in the DB, all cards + chart + recent list render.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/dashboard/ frontend/components/dashboard/
git commit -m "feat(frontend): dashboard page (stats + chart + recent uploads)"
```

---

## Task 9: Frontend — Uploads list page

**Files:**
- Create: `frontend/app/uploads/page.tsx`

- [ ] **Step 1: Implement page**

```typescript
// frontend/app/uploads/page.tsx
"use client";

import Link from "next/link";
import { useUploadsQuery } from "../../lib/api/uploads";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

const STATUS_VARIANT = {
  done: "default",
  processing: "secondary",
  pending: "secondary",
  failed: "destructive",
} as const;

export default function UploadsListPage() {
  const { data, isLoading, error } = useUploadsQuery();
  if (isLoading) return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (error || !data) {
    return <p className="text-sm text-red-600">Erro ao carregar uploads.</p>;
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Uploads</h1>
        <Button asChild>
          <Link href="/uploads/new">Novo upload</Link>
        </Button>
      </div>
      {data.length === 0 ? (
        <p className="text-sm text-zinc-500">
          Nenhum upload ainda — comece <Link href="/uploads/new" className="underline">enviando um CSV</Link>.
        </p>
      ) : (
        <table className="w-full border-separate border-spacing-0 text-sm">
          <thead className="text-left text-xs text-zinc-500">
            <tr>
              <th className="border-b border-zinc-200 pb-2">Arquivo</th>
              <th className="border-b border-zinc-200 pb-2">Status</th>
              <th className="border-b border-zinc-200 pb-2">Linhas</th>
              <th className="border-b border-zinc-200 pb-2">Progresso</th>
              <th className="border-b border-zinc-200 pb-2">Data</th>
            </tr>
          </thead>
          <tbody>
            {data.map((u) => (
              <tr key={u.upload_id} className="hover:bg-zinc-50">
                <td className="border-b border-zinc-100 py-3">
                  <Link
                    href={`/uploads/${u.upload_id}`}
                    className="font-medium text-zinc-900 hover:underline"
                  >
                    {u.nome_arquivo}
                  </Link>
                </td>
                <td className="border-b border-zinc-100 py-3">
                  <Badge variant={(STATUS_VARIANT as Record<string, "default" | "secondary" | "destructive">)[u.status] ?? "secondary"}>
                    {u.status}
                  </Badge>
                </td>
                <td className="border-b border-zinc-100 py-3 text-zinc-700">
                  {u.linhas_classificadas}/{u.linhas_total}
                </td>
                <td className="border-b border-zinc-100 py-3 text-zinc-700">
                  {u.progresso_pct.toFixed(0)}%
                </td>
                <td className="border-b border-zinc-100 py-3 text-zinc-500">
                  {new Date(u.data_upload).toLocaleString("pt-BR")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

`/uploads` renders empty state OR rows depending on DB content.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/uploads/page.tsx
git commit -m "feat(frontend): uploads list page"
```

---

## Task 10: Frontend — Upload new (UploadDropzone)

**Files:**
- Create: `frontend/app/uploads/new/page.tsx`
- Create: `frontend/components/upload/UploadDropzone.tsx`
- Create: `frontend/tests/components/UploadDropzone.test.tsx`

- [ ] **Step 1: UploadDropzone component**

```typescript
// frontend/components/upload/UploadDropzone.tsx
"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

const MAX_BYTES = 50 * 1024 * 1024;
const ACCEPTED = [".csv", ".xlsx", ".xlsm"];

export interface UploadDropzoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

function validate(file: File): string | null {
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  if (!ACCEPTED.includes(ext)) return "Formato inválido — use CSV ou XLSX";
  if (file.size > MAX_BYTES) return "Arquivo muito grande (>50MB)";
  return null;
}

export function UploadDropzone({ onFile, disabled }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFile(file: File) {
    const err = validate(file);
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    onFile(file);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setHover(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setHover(true);
        }}
        onDragLeave={() => setHover(false)}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        className={`flex h-48 cursor-pointer items-center justify-center rounded-lg border-2 border-dashed text-center transition ${
          hover ? "border-emerald-500 bg-emerald-50" : "border-zinc-300 bg-zinc-50"
        } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <div>
          <p className="text-sm font-medium text-zinc-700">
            Arraste seu CSV ou XLSX aqui
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            ou clique para selecionar — máx 50MB · coluna <code>descricao_original</code> obrigatória
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={onChange}
          aria-label="Arquivo de catálogo"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Test UploadDropzone**

```typescript
// frontend/tests/components/UploadDropzone.test.tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { UploadDropzone } from "../../components/upload/UploadDropzone";

function makeFile(name: string, size = 100): File {
  const file = new File([new Uint8Array(size)], name, { type: "text/csv" });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("UploadDropzone", () => {
  it("accepts CSV and fires onFile", () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);
    const input = screen.getByLabelText("Arquivo de catálogo") as HTMLInputElement;
    const file = makeFile("a.csv");
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("rejects non-CSV files", () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);
    const input = screen.getByLabelText("Arquivo de catálogo") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("a.pdf")] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText(/Formato inválido/)).toBeInTheDocument();
  });

  it("rejects files larger than 50MB", () => {
    const onFile = vi.fn();
    render(<UploadDropzone onFile={onFile} />);
    const input = screen.getByLabelText("Arquivo de catálogo") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("a.csv", 51 * 1024 * 1024)] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText(/muito grande/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Upload new page**

```typescript
// frontend/app/uploads/new/page.tsx
"use client";

import { useRouter } from "next/navigation";
import { useCreateUploadMutation } from "../../../lib/api/uploads";
import { UploadDropzone } from "../../../components/upload/UploadDropzone";

export default function UploadNewPage() {
  const router = useRouter();
  const { mutate, isPending, error } = useCreateUploadMutation();

  function onFile(file: File) {
    mutate(file, {
      onSuccess: (data) => router.push(`/uploads/${data.upload_id}`),
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Novo upload</h1>
      <UploadDropzone onFile={onFile} disabled={isPending} />
      {isPending && <p className="text-sm text-zinc-500">Enviando…</p>}
      {error && <p className="text-sm text-red-600">{error.message}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && pnpm test UploadDropzone
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/uploads/new/ frontend/components/upload/ frontend/tests/components/UploadDropzone.test.tsx
git commit -m "feat(frontend): upload new page + UploadDropzone with size/format validation"
```

---

## Task 11: Frontend — Upload detail (progress + cluster table)

**Files:**
- Create: `frontend/app/uploads/[id]/page.tsx`
- Create: `frontend/components/upload/UploadProgressBar.tsx`
- Create: `frontend/components/cluster/ClusterTable.tsx`
- Create: `frontend/components/cluster/ClusterFilters.tsx`
- Create: `frontend/components/cluster/ConfidenceBadge.tsx`
- Create: `frontend/tests/components/ConfidenceBadge.test.tsx`
- Create: `frontend/tests/components/ClusterTable.test.tsx`

- [ ] **Step 1: ConfidenceBadge**

```typescript
// frontend/components/cluster/ConfidenceBadge.tsx
import { Badge } from "../ui/badge";

const STYLES: Record<string, { className: string; label: string }> = {
  retrieval: { className: "bg-emerald-100 text-emerald-800", label: "Auto" },
  curator: { className: "bg-sky-100 text-sky-800", label: "Curator" },
  manual_pending: { className: "bg-amber-100 text-amber-800", label: "Manual" },
  retrieval_fallback: { className: "bg-zinc-100 text-zinc-700", label: "Fallback" },
  revisado_humano: { className: "bg-purple-100 text-purple-800", label: "Revisado" },
};

export function ConfidenceBadge({
  metodo,
  confianca,
}: {
  metodo: string | null;
  confianca: number | null;
}) {
  if (!metodo) return <Badge variant="secondary">—</Badge>;
  const style = STYLES[metodo] ?? { className: "bg-zinc-100 text-zinc-700", label: metodo };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${style.className}`}
      aria-label={`Método ${style.label}, confiança ${confianca?.toFixed(2) ?? "n/d"}`}
    >
      <span>{style.label}</span>
      {confianca !== null && <span className="opacity-70">{(confianca * 100).toFixed(0)}%</span>}
    </span>
  );
}
```

- [ ] **Step 2: ConfidenceBadge test**

```typescript
// frontend/tests/components/ConfidenceBadge.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceBadge } from "../../components/cluster/ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("renders 'Auto' for retrieval", () => {
    render(<ConfidenceBadge metodo="retrieval" confianca={0.92} />);
    expect(screen.getByText("Auto")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("renders 'Manual' for manual_pending", () => {
    render(<ConfidenceBadge metodo="manual_pending" confianca={0.5} />);
    expect(screen.getByText("Manual")).toBeInTheDocument();
  });

  it("renders dash when metodo is null", () => {
    render(<ConfidenceBadge metodo={null} confianca={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: ClusterFilters**

```typescript
// frontend/components/cluster/ClusterFilters.tsx
"use client";

import { Input } from "../ui/input";

export interface ClusterFilterState {
  metodo?: string;
  revisado?: boolean;
  search: string;
}

export function ClusterFilters({
  value,
  onChange,
}: {
  value: ClusterFilterState;
  onChange: (next: ClusterFilterState) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Input
        type="search"
        placeholder="Buscar cluster…"
        value={value.search}
        onChange={(e) => onChange({ ...value, search: e.target.value })}
        className="w-64"
        aria-label="Buscar cluster"
      />
      <select
        value={value.metodo ?? ""}
        onChange={(e) => onChange({ ...value, metodo: e.target.value || undefined })}
        className="rounded-md border border-zinc-300 px-3 py-2 text-sm"
        aria-label="Filtrar por método"
      >
        <option value="">Todos os métodos</option>
        <option value="retrieval">Auto (retrieval)</option>
        <option value="curator">Curator</option>
        <option value="manual_pending">Manual pending</option>
        <option value="retrieval_fallback">Fallback</option>
        <option value="revisado_humano">Revisado</option>
      </select>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value.revisado === true}
          onChange={(e) => onChange({ ...value, revisado: e.target.checked || undefined })}
        />
        Apenas revisados
      </label>
    </div>
  );
}
```

- [ ] **Step 4: ClusterTable**

```typescript
// frontend/components/cluster/ClusterTable.tsx
import Link from "next/link";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { ClusterSummary } from "../../lib/types";

export function ClusterTable({
  clusters,
  searchTerm,
}: {
  clusters: ClusterSummary[];
  searchTerm: string;
}) {
  const filtered = searchTerm.trim()
    ? clusters.filter((c) =>
        c.nome_cluster.toLowerCase().includes(searchTerm.toLowerCase()),
      )
    : clusters;

  if (filtered.length === 0) {
    return <p className="text-sm text-zinc-500">Nenhum cluster encontrado.</p>;
  }
  return (
    <table className="w-full border-separate border-spacing-0 text-sm" aria-label="Clusters">
      <thead className="text-left text-xs text-zinc-500">
        <tr>
          <th className="border-b border-zinc-200 pb-2">Cluster</th>
          <th className="border-b border-zinc-200 pb-2">Linhas</th>
          <th className="border-b border-zinc-200 pb-2">CNAE</th>
          <th className="border-b border-zinc-200 pb-2">Método</th>
          <th className="border-b border-zinc-200 pb-2">Revisado</th>
          <th className="border-b border-zinc-200 pb-2">Shortlist</th>
          <th className="border-b border-zinc-200 pb-2" />
        </tr>
      </thead>
      <tbody>
        {filtered.map((c) => (
          <tr key={c.id} className="hover:bg-zinc-50">
            <td className="border-b border-zinc-100 py-3 font-medium text-zinc-900">
              {c.nome_cluster}
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">{c.num_linhas}</td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">
              {c.cnae ?? "—"}
              {c.cnae_descricao && (
                <span className="block text-xs text-zinc-500">{c.cnae_descricao}</span>
              )}
            </td>
            <td className="border-b border-zinc-100 py-3">
              <ConfidenceBadge metodo={c.cnae_metodo} confianca={c.cnae_confianca} />
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">
              {c.revisado_humano ? "✓" : "—"}
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">{c.shortlist_size}</td>
            <td className="border-b border-zinc-100 py-3 text-right">
              <Link href={`/clusters/${c.id}`} className="text-sm font-medium text-zinc-900 hover:underline">
                Abrir →
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 5: ClusterTable test**

```typescript
// frontend/tests/components/ClusterTable.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClusterTable } from "../../components/cluster/ClusterTable";
import type { ClusterSummary } from "../../lib/types";

const sample: ClusterSummary[] = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    nome_cluster: "Parafusos",
    cnae: "4744001",
    cnae_descricao: "Ferragens",
    cnae_confianca: 0.92,
    cnae_metodo: "retrieval",
    num_linhas: 6,
    revisado_humano: false,
    shortlist_size: 10,
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    nome_cluster: "Geradores",
    cnae: null,
    cnae_descricao: null,
    cnae_confianca: null,
    cnae_metodo: null,
    num_linhas: 4,
    revisado_humano: true,
    shortlist_size: 0,
  },
];

describe("ClusterTable", () => {
  it("renders all rows when search is empty", () => {
    render(<ClusterTable clusters={sample} searchTerm="" />);
    expect(screen.getByText("Parafusos")).toBeInTheDocument();
    expect(screen.getByText("Geradores")).toBeInTheDocument();
  });

  it("filters by searchTerm", () => {
    render(<ClusterTable clusters={sample} searchTerm="paraf" />);
    expect(screen.getByText("Parafusos")).toBeInTheDocument();
    expect(screen.queryByText("Geradores")).not.toBeInTheDocument();
  });

  it("shows empty state when no match", () => {
    render(<ClusterTable clusters={sample} searchTerm="xyz" />);
    expect(screen.getByText(/Nenhum cluster/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: UploadProgressBar**

```typescript
// frontend/components/upload/UploadProgressBar.tsx
import { Progress } from "../ui/progress";

export function UploadProgressBar({
  status,
  pct,
  erro,
}: {
  status: string;
  pct: number;
  erro?: string | null;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">Status: {status}</span>
        <span className="text-zinc-500">{pct.toFixed(0)}%</span>
      </div>
      <Progress value={pct} aria-label="Progresso do upload" />
      {erro && <p className="text-sm text-red-600">Erro: {erro}</p>}
    </div>
  );
}
```

- [ ] **Step 7: Upload detail page**

```typescript
// frontend/app/uploads/[id]/page.tsx
"use client";

import { use, useState } from "react";
import { useClustersQuery } from "../../../lib/api/clusters";
import { useUploadStatusQuery } from "../../../lib/api/uploads";
import { ClusterFilters, type ClusterFilterState } from "../../../components/cluster/ClusterFilters";
import { ClusterTable } from "../../../components/cluster/ClusterTable";
import { UploadProgressBar } from "../../../components/upload/UploadProgressBar";

export default function UploadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const upload = useUploadStatusQuery(id);
  const [filters, setFilters] = useState<ClusterFilterState>({ search: "" });
  const clusters = useClustersQuery(id, {
    metodo: filters.metodo,
    revisado: filters.revisado,
  });

  if (upload.isLoading) return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (upload.error || !upload.data) {
    return <p className="text-sm text-red-600">Upload não encontrado.</p>;
  }

  const done = upload.data.status === "done";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Upload</h1>
      <UploadProgressBar
        status={upload.data.status}
        pct={upload.data.progresso_pct}
        erro={upload.data.erro}
      />
      {done && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Clusters</h2>
          <ClusterFilters value={filters} onChange={setFilters} />
          {clusters.isLoading && <p className="text-sm text-zinc-500">Carregando clusters…</p>}
          {clusters.data && (
            <ClusterTable clusters={clusters.data} searchTerm={filters.search} />
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run tests**

```bash
cd frontend && pnpm test
```

Expected: all frontend tests passing (≥10 cumulative).

- [ ] **Step 9: Commit**

```bash
git add frontend/app/uploads/[id]/ frontend/components/upload/UploadProgressBar.tsx frontend/components/cluster/ frontend/tests/components/
git commit -m "feat(frontend): upload detail (progress bar + cluster table + filters)"
```

---

## Task 12: Frontend — Cluster detail (CNAE editor + shortlist)

**Files:**
- Create: `frontend/app/clusters/[id]/page.tsx`
- Create: `frontend/components/cluster/ClusterCnaeEditor.tsx`
- Create: `frontend/components/cluster/ClusterReviewForm.tsx`
- Create: `frontend/components/shortlist/ShortlistTable.tsx`
- Create: `frontend/tests/components/ClusterCnaeEditor.test.tsx`

- [ ] **Step 1: ClusterCnaeEditor (client-side fuzzy search over bundled JSON)**

```typescript
// frontend/components/cluster/ClusterCnaeEditor.tsx
"use client";

import { useMemo, useState } from "react";
import cnaeData from "../../lib/cnae-taxonomy.json";

interface Cnae {
  codigo: string;
  denominacao: string;
}

const ALL_CNAES = cnaeData as Cnae[];

export function ClusterCnaeEditor({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (next: string) => void;
}) {
  const [query, setQuery] = useState("");
  const matches = useMemo(() => {
    if (!query.trim()) return ALL_CNAES.slice(0, 20);
    const q = query.toLowerCase();
    return ALL_CNAES.filter(
      (c) => c.codigo.includes(q) || c.denominacao.toLowerCase().includes(q),
    ).slice(0, 20);
  }, [query]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-zinc-700">CNAE</label>
      <input
        type="search"
        placeholder="Pesquisar por código ou descrição…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
        aria-label="Pesquisar CNAE"
      />
      <ul className="max-h-64 overflow-y-auto rounded-md border border-zinc-200" role="listbox">
        {matches.map((c) => (
          <li
            key={c.codigo}
            onClick={() => onChange(c.codigo)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onChange(c.codigo);
            }}
            role="option"
            aria-selected={value === c.codigo}
            tabIndex={0}
            className={`cursor-pointer px-3 py-2 text-sm hover:bg-zinc-50 ${
              value === c.codigo ? "bg-emerald-50" : ""
            }`}
          >
            <span className="font-mono text-zinc-600">{c.codigo}</span>{" "}
            <span className="text-zinc-900">{c.denominacao}</span>
          </li>
        ))}
        {matches.length === 0 && (
          <li className="px-3 py-2 text-sm text-zinc-500">Nenhum CNAE encontrado.</li>
        )}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Test ClusterCnaeEditor**

```typescript
// frontend/tests/components/ClusterCnaeEditor.test.tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ClusterCnaeEditor } from "../../components/cluster/ClusterCnaeEditor";

describe("ClusterCnaeEditor", () => {
  it("filters by user input", () => {
    const onChange = vi.fn();
    render(<ClusterCnaeEditor value={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Pesquisar CNAE"), {
      target: { value: "0600001" },
    });
    expect(screen.getByText("0600001")).toBeInTheDocument();
  });

  it("fires onChange when clicking an option", () => {
    const onChange = vi.fn();
    render(<ClusterCnaeEditor value={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Pesquisar CNAE"), {
      target: { value: "0600001" },
    });
    fireEvent.click(screen.getByText("0600001"));
    expect(onChange).toHaveBeenCalledWith("0600001");
  });
});
```

- [ ] **Step 3: ShortlistTable**

```typescript
// frontend/components/shortlist/ShortlistTable.tsx
import type { ShortlistEntry } from "../../lib/types";

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}

export function ShortlistTable({ entries }: { entries: ShortlistEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        Shortlist ainda não gerada — aguardando classificação CNAE do cluster.
      </p>
    );
  }
  return (
    <table className="w-full border-separate border-spacing-0 text-sm" aria-label="Shortlist de fornecedores">
      <thead className="text-left text-xs text-zinc-500">
        <tr>
          <th className="border-b border-zinc-200 pb-2">#</th>
          <th className="border-b border-zinc-200 pb-2">Razão social</th>
          <th className="border-b border-zinc-200 pb-2">CNPJ</th>
          <th className="border-b border-zinc-200 pb-2">Capital</th>
          <th className="border-b border-zinc-200 pb-2">UF / Município</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={e.cnpj}>
            <td className="border-b border-zinc-100 py-2 text-zinc-500">{e.rank_estagio3}</td>
            <td className="border-b border-zinc-100 py-2">
              <span className="font-medium text-zinc-900">{e.razao_social}</span>
              {e.nome_fantasia && (
                <span className="block text-xs text-zinc-500">{e.nome_fantasia}</span>
              )}
            </td>
            <td className="border-b border-zinc-100 py-2 font-mono text-xs text-zinc-700">{e.cnpj}</td>
            <td className="border-b border-zinc-100 py-2 text-zinc-700">{formatBRL(e.capital_social)}</td>
            <td className="border-b border-zinc-100 py-2 text-zinc-700">
              {e.uf ?? "—"}
              {e.municipio && <span className="block text-xs text-zinc-500">{e.municipio}</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: ClusterReviewForm**

```typescript
// frontend/components/cluster/ClusterReviewForm.tsx
"use client";

import { useState } from "react";
import type { ClusterDetail } from "../../lib/types";
import { usePatchClusterMutation, type ClusterPatchBody } from "../../lib/api/clusters";
import { ClusterCnaeEditor } from "./ClusterCnaeEditor";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Button } from "../ui/button";

export function ClusterReviewForm({ cluster }: { cluster: ClusterDetail }) {
  const [cnae, setCnae] = useState<string | null>(cluster.cnae);
  const [notas, setNotas] = useState(cluster.notas_revisor ?? "");
  const [revisado, setRevisado] = useState(cluster.revisado_humano);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

  const patch = usePatchClusterMutation(cluster.id);

  function save() {
    const body: ClusterPatchBody = {};
    if (cnae !== cluster.cnae && cnae !== null) body.cnae = cnae;
    if (notas !== (cluster.notas_revisor ?? "")) body.notas_revisor = notas;
    if (revisado !== cluster.revisado_humano) body.revisado_humano = revisado;
    if (Object.keys(body).length === 0) {
      setFeedback({ kind: "ok", msg: "Nada para salvar." });
      return;
    }
    patch.mutate(body, {
      onSuccess: () => setFeedback({ kind: "ok", msg: "Salvo." }),
      onError: (e: Error) => setFeedback({ kind: "err", msg: e.message }),
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-zinc-700">Cluster</p>
        <p className="text-lg font-semibold">{cluster.nome_cluster}</p>
        <p className="mt-1 text-xs text-zinc-500">{cluster.num_linhas} linhas</p>
      </div>

      {cluster.sample_linhas.length > 0 && (
        <div>
          <p className="text-sm font-medium text-zinc-700">Amostra de linhas</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-zinc-700">
            {cluster.sample_linhas.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-zinc-700">CNAE atual:</span>
        <span className="font-mono text-sm">{cluster.cnae ?? "—"}</span>
        <ConfidenceBadge metodo={cluster.cnae_metodo} confianca={cluster.cnae_confianca} />
      </div>

      <ClusterCnaeEditor value={cnae} onChange={setCnae} />

      <div>
        <label htmlFor="notas" className="block text-sm font-medium text-zinc-700">
          Notas do revisor
        </label>
        <textarea
          id="notas"
          value={notas}
          onChange={(e) => setNotas(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
        />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={revisado}
          onChange={(e) => setRevisado(e.target.checked)}
        />
        Marcar como revisado
      </label>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={patch.isPending}>
          {patch.isPending ? "Salvando…" : "Salvar"}
        </Button>
        {feedback && (
          <span
            className={`text-sm ${
              feedback.kind === "ok" ? "text-emerald-700" : "text-red-600"
            }`}
          >
            {feedback.msg}
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Cluster detail page**

```typescript
// frontend/app/clusters/[id]/page.tsx
"use client";

import Link from "next/link";
import { use } from "react";
import { useClusterDetailQuery, useShortlistQuery } from "../../../lib/api/clusters";
import { ClusterReviewForm } from "../../../components/cluster/ClusterReviewForm";
import { ShortlistTable } from "../../../components/shortlist/ShortlistTable";

export default function ClusterDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const cluster = useClusterDetailQuery(id);
  const shortlist = useShortlistQuery(id, cluster.data?.shortlist_gerada);

  if (cluster.isLoading) return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (cluster.error || !cluster.data) {
    return <p className="text-sm text-red-600">Cluster não encontrado.</p>;
  }
  return (
    <div className="space-y-8">
      <div>
        <Link
          href={`/uploads/${cluster.data.upload_id}`}
          className="text-sm text-zinc-500 hover:underline"
        >
          ← Voltar ao upload
        </Link>
      </div>
      <ClusterReviewForm cluster={cluster.data} />
      <section className="space-y-3">
        <h2 className="text-lg font-medium">Shortlist de fornecedores (top 10)</h2>
        {cluster.data.shortlist_gerada === false && (
          <p className="text-xs text-amber-700">Regenerando shortlist…</p>
        )}
        {shortlist.data ? <ShortlistTable entries={shortlist.data} /> : null}
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Run tests**

```bash
cd frontend && pnpm test
```

Expected: ≥11 tests passing (3 client + 3 UploadDropzone + 3 ClusterTable + 3 ConfidenceBadge + 2 ClusterCnaeEditor — ~14 total).

- [ ] **Step 7: Commit**

```bash
git add frontend/app/clusters/ frontend/components/cluster/ClusterCnaeEditor.tsx frontend/components/cluster/ClusterReviewForm.tsx frontend/components/shortlist/ frontend/tests/components/ClusterCnaeEditor.test.tsx
git commit -m "feat(frontend): cluster detail (CNAE editor + review form + shortlist viewer)"
```

---

## Task 13: Smoke test + DoD verification + memory update

**Files:**
- Modify: `Makefile` (add `test-sprint3` target)
- Modify: `C:\Users\rgoal\.claude\projects\c--Users-rgoal-Desktop-IAgentics-Agente---SUpplier-Discovery\memory\project_agente10.md`

- [ ] **Step 1: Add test-sprint3 Makefile target**

In `Makefile`, after `test-sprint2`:

```makefile
test-sprint3:
	docker compose up -d postgres
	docker compose run --rm \
		-e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
		backend uv run pytest -q \
			tests/integration/test_api_uploads_list.py \
			tests/integration/test_api_clusters.py \
			tests/integration/test_api_cluster_patch.py \
			tests/integration/test_api_dashboard.py \
			-m "integration"
```

Update the help section accordingly.

- [ ] **Step 2: Run full test suites**

```bash
make test-sprint3
make test-sprint2
cd frontend && pnpm test
```

Expected: all green, no regressions in Sprint 1 / Sprint 2 backend.

- [ ] **Step 3: Frontend build smoke test**

```bash
cd frontend && pnpm build
```

Expected: build succeeds with no type or lint errors.

- [ ] **Step 4: Manual smoke test in dev**

```bash
# Terminal 1: backend
make up
# Terminal 2: frontend
cd frontend && NEXT_PUBLIC_TENANT_ID=<tenant-uuid> NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 pnpm dev
```

Run these checks in browser at `http://localhost:3000`:

1. `/` → redirects to `/dashboard`
2. `/dashboard` renders stats cards (may all be 0)
3. Sidebar `Uploads → Novo upload` works
4. Upload `backend/tests/fixtures/catalogo_sintetico.csv`
5. Auto-redirect to `/uploads/{id}`, progress bar fills as backend processes
6. Once status=done, cluster table renders
7. Click any cluster `Abrir →`
8. Cluster detail shows current CNAE + sample linhas + CNAE editor + shortlist
9. Change CNAE via combobox → Save → see `Regenerando shortlist…` then updated shortlist
10. Hit refresh → state persists

If any step fails, fix before committing memory update.

- [ ] **Step 5: Update memory**

In `C:\Users\rgoal\.claude\projects\c--Users-rgoal-Desktop-IAgentics-Agente---SUpplier-Discovery\memory\project_agente10.md`, update the "Latest sprint complete" entry:

```markdown
- **Latest sprint complete:** Sprint 3 (Frontend UI + cluster review endpoints) — completo 2026-05-13. 5 frontend routes (dashboard, uploads list/new/detail, cluster detail) + 6 new backend endpoints. Stack: Next.js 16 + React 19 + Tailwind v4 + @base-ui/react + shadcn + TanStack Query v5. Polled progress, optimistic CNAE PATCH, client-side CNAE picker over 1331-row bundle. Tests: ≥10 frontend Vitest + 4 backend integration. **Sprint 3 follow-ups:** (1) PATCH cluster lacks handoff_rfx field plumbing; (2) no CSV/Excel export of shortlist; (3) no bulk actions on clusters; (4) auth still header-based (no JWT); (5) `_cnae_stage` long transaction still unfixed from Sprint 2.
```

And in `MEMORY.md`, update the project line accordingly.

- [ ] **Step 6: Commit and push**

```bash
git add Makefile
git commit -m "test(backend): make test-sprint3 target + sprint 3 memory update"
git push origin main
```

---

## Definition of Done verification

- [ ] Backend: 4 new test files + corresponding endpoints, all passing
- [ ] Frontend: 5 routes (`/`, `/dashboard`, `/uploads`, `/uploads/new`, `/uploads/[id]`, `/clusters/[id]`) all functional
- [ ] Frontend: ≥10 Vitest tests passing
- [ ] `pnpm build` succeeds
- [ ] `pnpm test` succeeds
- [ ] `make test-sprint3` passes
- [ ] `make test-sprint2` still passes (regression)
- [ ] `make test-backend` passes (regression)
- [ ] `make lint` clean
- [ ] Manual smoke test passes (upload → progress → review → CNAE override → shortlist regen)
- [ ] Memory updated with Sprint 3 status + follow-ups
- [ ] Pushed to origin/main
