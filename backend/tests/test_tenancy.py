"""RLS isolation tests against a real Postgres.

Marker: integration — run via ``make test-backend-integration`` or
``pytest -m integration``. Requires ``docker compose up -d postgres`` and
the latest migrations applied (``make migrate``).
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agente10.core.tenancy import tenant_context

pytestmark = pytest.mark.integration


async def _seed_upload(session: AsyncSession, tenant_id: uuid.UUID, nome: str) -> uuid.UUID:
    """Insert a spend_upload row under the current tenant context, return its id."""
    row = await session.execute(
        text("""
            INSERT INTO spend_uploads (tenant_id, nome_arquivo, object_storage_path)
            VALUES (:tid, :nome, :path)
            RETURNING id
            """),
        {"tid": str(tenant_id), "nome": nome, "path": f"s3://bucket/{nome}"},
    )
    return row.scalar_one()


async def test_select_without_context_returns_zero_rows(
    db_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """Without SET LOCAL, RLS hides all rows even if they exist."""
    tenant_a, _ = two_tenants

    # Seed a row as A
    async with db_session.begin():
        async with tenant_context(db_session, tenant_a):
            await _seed_upload(db_session, tenant_a, "seed_a.csv")

    # Now query WITHOUT tenant context: should see 0 rows
    async with db_session.begin():
        result = await db_session.execute(text("SELECT COUNT(*) FROM spend_uploads"))
        assert result.scalar_one() == 0


async def test_tenant_sees_only_own_rows(
    db_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    tenant_a, tenant_b = two_tenants

    async with db_session.begin():
        async with tenant_context(db_session, tenant_a):
            await _seed_upload(db_session, tenant_a, "a1.csv")
            await _seed_upload(db_session, tenant_a, "a2.csv")
        async with tenant_context(db_session, tenant_b):
            await _seed_upload(db_session, tenant_b, "b1.csv")

    async with db_session.begin():
        async with tenant_context(db_session, tenant_a):
            result = await db_session.execute(
                text("SELECT nome_arquivo FROM spend_uploads ORDER BY nome_arquivo")
            )
            names_a = [r[0] for r in result.all()]

        async with tenant_context(db_session, tenant_b):
            result = await db_session.execute(
                text("SELECT nome_arquivo FROM spend_uploads ORDER BY nome_arquivo")
            )
            names_b = [r[0] for r in result.all()]

    assert names_a == ["a1.csv", "a2.csv"]
    assert names_b == ["b1.csv"]


async def test_with_check_blocks_cross_tenant_insert(
    db_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """While in tenant_context(A), inserting tenant_id=B is blocked by WITH CHECK."""
    tenant_a, tenant_b = two_tenants

    with pytest.raises((IntegrityError, DBAPIError)):
        async with db_session.begin():
            async with tenant_context(db_session, tenant_a):
                await db_session.execute(
                    text("""
                        INSERT INTO spend_uploads (tenant_id, nome_arquivo, object_storage_path)
                        VALUES (:tid, :nome, :path)
                        """),
                    {
                        "tid": str(tenant_b),
                        "nome": "evil.csv",
                        "path": "s3://bucket/evil",
                    },
                )


async def test_update_other_tenant_is_no_op(
    db_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """Update issued under tenant_context(A) cannot touch tenant B's rows."""
    tenant_a, tenant_b = two_tenants

    async with db_session.begin():
        async with tenant_context(db_session, tenant_b):
            upload_id = await _seed_upload(db_session, tenant_b, "b_only.csv")

    async with db_session.begin():
        async with tenant_context(db_session, tenant_a):
            result = await db_session.execute(
                text("UPDATE spend_uploads SET nome_arquivo = 'hacked' " "WHERE id = :uid"),
                {"uid": str(upload_id)},
            )
            assert result.rowcount == 0

    async with db_session.begin():
        async with tenant_context(db_session, tenant_b):
            result = await db_session.execute(
                text("SELECT nome_arquivo FROM spend_uploads WHERE id = :uid"),
                {"uid": str(upload_id)},
            )
            assert result.scalar_one() == "b_only.csv"


async def test_rls_applies_to_spend_clusters_and_spend_linhas(
    db_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """Verify RLS works on two more representative tables."""
    tenant_a, tenant_b = two_tenants

    async with db_session.begin():
        async with tenant_context(db_session, tenant_a):
            upload_id_a = await _seed_upload(db_session, tenant_a, "a.csv")
            cluster_id_a = (
                await db_session.execute(
                    text("""
                        INSERT INTO spend_clusters (tenant_id, upload_id, nome_cluster)
                        VALUES (:tid, :uid, 'A cluster') RETURNING id
                        """),
                    {"tid": str(tenant_a), "uid": str(upload_id_a)},
                )
            ).scalar_one()
            await db_session.execute(
                text("""
                    INSERT INTO spend_linhas
                        (tenant_id, upload_id, descricao_original, cluster_id)
                    VALUES (:tid, :uid, 'item A', :cid)
                    """),
                {
                    "tid": str(tenant_a),
                    "uid": str(upload_id_a),
                    "cid": str(cluster_id_a),
                },
            )

    async with db_session.begin():
        async with tenant_context(db_session, tenant_b):
            n_clusters = (
                await db_session.execute(text("SELECT COUNT(*) FROM spend_clusters"))
            ).scalar_one()
            n_linhas = (
                await db_session.execute(text("SELECT COUNT(*) FROM spend_linhas"))
            ).scalar_one()
    assert n_clusters == 0
    assert n_linhas == 0
