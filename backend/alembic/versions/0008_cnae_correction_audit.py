"""cnae_correction_audit table — captures human CNAE corrections for training

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cnae_correction_audit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        # Not a FK to spend_clusters — we want audit to survive cluster deletion
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("descricao_cluster", sa.Text, nullable=False),
        sa.Column("cnae_antes", sa.VARCHAR(7), nullable=True),
        sa.Column("metodo_antes", sa.VARCHAR(20), nullable=True),
        sa.Column("cnae_depois", sa.VARCHAR(7), nullable=False),
        sa.Column("notas_revisor", sa.Text, nullable=True),
        sa.Column(
            "corrigido_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_audit_tenant_ts",
        "cnae_correction_audit",
        ["tenant_id", sa.text("corrigido_em DESC")],
    )

    # RLS — same pattern as other tenant-scoped tables (NULLIF for empty session var)
    op.execute("ALTER TABLE cnae_correction_audit ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cnae_correction_audit FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_select ON cnae_correction_audit
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_modify ON cnae_correction_audit
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID)
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
            )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON cnae_correction_audit")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON cnae_correction_audit")
    op.execute("ALTER TABLE cnae_correction_audit DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_audit_tenant_ts", table_name="cnae_correction_audit")
    op.drop_table("cnae_correction_audit")
