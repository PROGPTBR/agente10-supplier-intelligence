"""arq persistent task queue.

Replaces FastAPI's BackgroundTasks for long-running pipeline + shortlist regen.
BackgroundTasks die when the API container restarts (Railway deploy); arq jobs
survive in Redis and are picked up by the dedicated worker service.

The worker is run via:
    uv run arq agente10.worker.tasks.WorkerSettings

The Railway "worker" service uses the same Docker image as backend but
overrides the start command to launch arq.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings

from agente10.core.config import get_settings
from agente10.core.db import dispose_engine, get_session_factory, init_engine
from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.estagio3.shortlist_generator import regenerate_shortlist_for_cluster
from agente10.integrations.voyage import VoyageClient

log = logging.getLogger(__name__)


async def run_pipeline(
    ctx: dict[str, Any],
    upload_id: str,
    tenant_id: str,
    csv_path: str,
    column_mapping: dict[str, str] | None = None,
) -> None:
    """Worker job: run the full ingestion pipeline for one upload."""
    factory = get_session_factory()
    voyage = VoyageClient()
    curator = CuratorClient()
    log.info("worker: starting pipeline for upload=%s", upload_id)
    await processar_upload(
        UUID(upload_id),
        UUID(tenant_id),
        Path(csv_path),
        factory,
        voyage,
        curator,
        column_mapping,
    )
    log.info("worker: finished pipeline for upload=%s", upload_id)


async def run_regenerate_shortlist(
    ctx: dict[str, Any],
    cluster_id: str,
    tenant_id: str,
) -> None:
    """Worker job: regenerate one cluster's shortlist after human CNAE edit."""
    factory = get_session_factory()
    curator = CuratorClient()
    log.info("worker: regenerating shortlist for cluster=%s", cluster_id)
    await regenerate_shortlist_for_cluster(UUID(cluster_id), UUID(tenant_id), factory, curator)


async def _startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    init_engine(settings)
    log.info("worker: engine initialized")


async def _shutdown(ctx: dict[str, Any]) -> None:
    await dispose_engine()


def _redis_settings() -> RedisSettings:
    """Resolved at module import time when worker starts; REDIS_URL must be set."""
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    """arq worker entrypoint — `uv run arq agente10.worker.tasks.WorkerSettings`."""

    functions = [run_pipeline, run_regenerate_shortlist]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = _redis_settings()
    # Long pipelines: a single job can take 10+ minutes (cnae + shortlist
    # stages combined). 30min ceiling allows for hot summer days.
    job_timeout = 1800
    max_jobs = 2  # concurrent pipelines per worker — keeps memory bounded
    keep_result = 3600  # 1h retention for inspection
    health_check_interval = 60
