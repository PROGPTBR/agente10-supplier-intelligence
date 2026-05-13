"""CLI to run the full Estágio 1+3 pipeline against a local CSV file.

Usage:
    docker exec agente-supplierdiscovery-backend-1 sh -c \
        "cd /app && uv run python scripts/run_pipeline.py \
        --csv tests/fixtures/catalogo_sintetico.csv \
        --tenant <uuid> --nome 'Catálogo teste'"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agente10.core.tenancy import tenant_context
from agente10.curator.client import CuratorClient
from agente10.estagio1.pipeline import processar_upload
from agente10.integrations.voyage import VoyageClient


async def main(args: argparse.Namespace) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    engine = create_async_engine(db_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    tenant_id = uuid.UUID(args.tenant)
    upload_id = uuid.uuid4()
    src = Path(args.csv).resolve()
    if not src.exists():
        print(f"CSV not found: {src}", file=sys.stderr)
        return 2

    storage_dir = Path("/app/data/uploads") / str(tenant_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dst = storage_dir / f"{upload_id}{src.suffix}"
    shutil.copy(src, dst)

    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            await session.execute(
                text(
                    "INSERT INTO spend_uploads "
                    "(id, tenant_id, nome_arquivo, object_storage_path, status) "
                    "VALUES (:i, :t, :n, :p, 'pending')"
                ),
                {
                    "i": str(upload_id), "t": str(tenant_id),
                    "n": args.nome, "p": str(dst),
                },
            )
    print(f"upload_id = {upload_id}")
    await processar_upload(
        upload_id=upload_id, tenant_id=tenant_id, csv_path=dst,
        session_factory=factory,
        voyage=VoyageClient(), curator=CuratorClient(),
    )

    async with factory() as session, session.begin():
        async with tenant_context(session, tenant_id):
            row = await session.execute(
                text(
                    "SELECT status, linhas_total, linhas_classificadas, "
                    "(SELECT COUNT(*) FROM spend_clusters WHERE upload_id = :u) AS clusters, "
                    "(SELECT COUNT(*) FROM supplier_shortlists s "
                    "  WHERE s.cnae IN (SELECT cnae FROM spend_clusters c "
                    "                    WHERE c.upload_id = :u)) AS shortlists "
                    "FROM spend_uploads WHERE id = :u"
                ),
                {"u": str(upload_id)},
            )
            summary = row.one()
    print(
        f"Done: status={summary.status} "
        f"linhas={summary.linhas_total} classificadas={summary.linhas_classificadas} "
        f"clusters={summary.clusters} shortlists={summary.shortlists}"
    )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--nome", default="CLI upload")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
