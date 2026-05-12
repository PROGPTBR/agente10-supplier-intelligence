"""create tenant tables + RLS policies

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that get RLS policies
RLS_TABLES = (
    "spend_uploads",
    "spend_linhas",
    "spend_clusters",
    "concentracao_categorias",
    "supplier_shortlists",
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation_select ON {table}
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID)
        """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_modify ON {table}
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID)
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
            )
        """)


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {table}")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {table}")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # spend_uploads
    op.create_table(
        "spend_uploads",
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
        sa.Column("nome_arquivo", sa.Text, nullable=False),
        sa.Column("object_storage_path", sa.Text, nullable=False),
        sa.Column(
            "data_upload",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("linhas_total", sa.INTEGER, nullable=False, server_default="0"),
        sa.Column("linhas_classificadas", sa.INTEGER, nullable=False, server_default="0"),
        sa.Column("modo", sa.VARCHAR(20), nullable=False, server_default="catalogo"),
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="pending"),
        sa.Column("erro", sa.Text, nullable=True),
        sa.Column(
            "metadados",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            "modo IN ('catalogo', 'transacional')",
            name="spend_uploads_modo_chk",
        ),
    )

    # spend_clusters (before spend_linhas — FK target)
    op.create_table(
        "spend_clusters",
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
        sa.Column(
            "upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spend_uploads.id"),
            nullable=False,
        ),
        sa.Column("nome_cluster", sa.Text, nullable=False),
        sa.Column("cnae", sa.VARCHAR(7), nullable=True),
        sa.Column("cnae_confianca", sa.NUMERIC(3, 2), nullable=True),
        sa.Column("cnae_metodo", sa.VARCHAR(20), nullable=True),
        sa.Column("num_linhas", sa.INTEGER, nullable=False, server_default="0"),
        sa.Column(
            "revisado_humano",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notas_revisor", sa.Text, nullable=True),
        sa.Column(
            "data_geracao",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_clusters_tenant_upload",
        "spend_clusters",
        ["tenant_id", "upload_id"],
    )
    op.create_index("idx_clusters_tenant_cnae", "spend_clusters", ["tenant_id", "cnae"])

    # spend_linhas
    op.create_table(
        "spend_linhas",
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
        sa.Column(
            "upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spend_uploads.id"),
            nullable=False,
        ),
        sa.Column("id_linha_origem", sa.Text, nullable=True),
        sa.Column("agrupamento", sa.Text, nullable=True),
        sa.Column("descricao_original", sa.Text, nullable=False),
        sa.Column("descricao_normalizada", sa.Text, nullable=True),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spend_clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fornecedor_atual", sa.Text, nullable=True),
        sa.Column("cnpj_fornecedor", sa.VARCHAR(14), nullable=True),
        sa.Column("valor_total", sa.NUMERIC(15, 2), nullable=True),
        sa.Column("quantidade", sa.NUMERIC, nullable=True),
        sa.Column("uf_solicitante", sa.CHAR(2), nullable=True),
        sa.Column("municipio_solicitante", sa.Text, nullable=True),
        sa.Column("centro_custo", sa.Text, nullable=True),
        sa.Column("data_compra", sa.DATE, nullable=True),
        sa.Column("cnae", sa.VARCHAR(7), nullable=True),
        sa.Column("cnae_confianca", sa.NUMERIC(3, 2), nullable=True),
        sa.Column("cnae_metodo", sa.VARCHAR(20), nullable=True),
        sa.Column(
            "extras",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "idx_spend_linhas_tenant_upload",
        "spend_linhas",
        ["tenant_id", "upload_id"],
    )
    op.create_index("idx_spend_linhas_tenant_cnae", "spend_linhas", ["tenant_id", "cnae"])
    op.create_index("idx_spend_linhas_cluster", "spend_linhas", ["cluster_id"])

    # concentracao_categorias
    op.create_table(
        "concentracao_categorias",
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
        sa.Column(
            "upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spend_uploads.id"),
            nullable=False,
        ),
        sa.Column("cnae", sa.VARCHAR(7), nullable=False),
        sa.Column("spend_periodo", sa.NUMERIC(15, 2), nullable=True),
        sa.Column("fornecedores_unicos", sa.INTEGER, nullable=True),
        sa.Column("transacoes", sa.INTEGER, nullable=True),
        sa.Column("hhi", sa.NUMERIC(8, 2), nullable=True),
        sa.Column("fornecedor_dominante_cnpj", sa.VARCHAR(14), nullable=True),
        sa.Column("fornecedor_dominante_share", sa.NUMERIC(3, 2), nullable=True),
        sa.Column("diagnostico_tipo", sa.VARCHAR(30), nullable=True),
        sa.Column("diagnostico_texto", sa.Text, nullable=True),
        sa.Column("prioridade", sa.NUMERIC(5, 2), nullable=True),
        sa.Column(
            "data_calculo",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX idx_concentracao_tenant_upload_prio "
        "ON concentracao_categorias(tenant_id, upload_id, prioridade DESC)"
    )

    # supplier_shortlists
    op.create_table(
        "supplier_shortlists",
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
        sa.Column(
            "concentracao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concentracao_categorias.id"),
            nullable=True,
        ),
        sa.Column("cnae", sa.VARCHAR(7), nullable=False),
        sa.Column(
            "cnpj_fornecedor",
            sa.VARCHAR(14),
            sa.ForeignKey("empresas.cnpj"),
            nullable=False,
        ),
        sa.Column("score_total", sa.NUMERIC(3, 2), nullable=True),
        sa.Column("scores_por_dimensao", postgresql.JSONB, nullable=True),
        sa.Column("rank_estagio3", sa.INTEGER, nullable=True),
        sa.Column("rank_estagio4", sa.INTEGER, nullable=True),
        sa.Column(
            "enriquecimento_completo",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "handoff_rfx",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notas_internas", sa.Text, nullable=True),
        sa.Column(
            "data_geracao",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_shortlists_tenant_cnae",
        "supplier_shortlists",
        ["tenant_id", "cnae"],
    )

    # Enable RLS on all 5 tables
    for table in RLS_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in RLS_TABLES:
        _disable_rls(table)

    op.drop_index("idx_shortlists_tenant_cnae", table_name="supplier_shortlists")
    op.drop_table("supplier_shortlists")
    op.drop_index("idx_concentracao_tenant_upload_prio", table_name="concentracao_categorias")
    op.drop_table("concentracao_categorias")
    op.drop_index("idx_spend_linhas_cluster", table_name="spend_linhas")
    op.drop_index("idx_spend_linhas_tenant_cnae", table_name="spend_linhas")
    op.drop_index("idx_spend_linhas_tenant_upload", table_name="spend_linhas")
    op.drop_table("spend_linhas")
    op.drop_index("idx_clusters_tenant_cnae", table_name="spend_clusters")
    op.drop_index("idx_clusters_tenant_upload", table_name="spend_clusters")
    op.drop_table("spend_clusters")
    op.drop_table("spend_uploads")
