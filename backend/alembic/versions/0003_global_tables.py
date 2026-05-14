"""create global tables (empresas, cnae_taxonomy, empresa_signals, spend_classification_cache)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # postgis intentionally not required — `empresas.geom` column was removed
    # (was unused, only declared). Railway's stock Postgres lacks postgis.
    # Re-add if geo queries are needed later via custom Postgres image.

    # empresas
    op.create_table(
        "empresas",
        sa.Column("cnpj", sa.VARCHAR(14), primary_key=True),
        sa.Column("razao_social", sa.Text, nullable=False),
        sa.Column("nome_fantasia", sa.Text, nullable=True),
        sa.Column("cnae_primario", sa.VARCHAR(7), nullable=False),
        sa.Column(
            "cnaes_secundarios",
            postgresql.ARRAY(sa.VARCHAR(7)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("situacao_cadastral", sa.VARCHAR(20), nullable=True),
        sa.Column("data_abertura", sa.DATE, nullable=True),
        sa.Column("porte", sa.VARCHAR(20), nullable=True),
        sa.Column("capital_social", sa.NUMERIC(15, 2), nullable=True),
        sa.Column("faixa_funcionarios", sa.VARCHAR(20), nullable=True),
        sa.Column("natureza_juridica", sa.VARCHAR(10), nullable=True),
        sa.Column("uf", sa.CHAR(2), nullable=True),
        sa.Column("municipio", sa.Text, nullable=True),
        sa.Column("cep", sa.VARCHAR(8), nullable=True),
        sa.Column("endereco", sa.Text, nullable=True),
        sa.Column("telefone", sa.Text, nullable=True),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("ultima_atualizacao_rf", sa.DATE, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_empresas_cnae_primario", "empresas", ["cnae_primario"])
    op.create_index("idx_empresas_uf_municipio", "empresas", ["uf", "municipio"])
    op.create_index("idx_empresas_situacao", "empresas", ["situacao_cadastral"])

    # cnae_taxonomy
    op.create_table(
        "cnae_taxonomy",
        sa.Column("codigo", sa.VARCHAR(7), primary_key=True),
        sa.Column("secao", sa.CHAR(1), nullable=True),
        sa.Column("divisao", sa.VARCHAR(2), nullable=True),
        sa.Column("grupo", sa.VARCHAR(3), nullable=True),
        sa.Column("classe", sa.VARCHAR(5), nullable=True),
        sa.Column("denominacao", sa.Text, nullable=False),
        sa.Column("notas_explicativas", sa.Text, nullable=True),
        sa.Column("exemplos_atividades", sa.Text, nullable=True),
    )
    op.execute("ALTER TABLE cnae_taxonomy ADD COLUMN embedding vector(1024)")

    # empresa_signals
    op.create_table(
        "empresa_signals",
        sa.Column(
            "cnpj",
            sa.VARCHAR(14),
            sa.ForeignKey("empresas.cnpj"),
            primary_key=True,
        ),
        sa.Column(
            "emite_nfe_categorias",
            postgresql.ARRAY(sa.VARCHAR(7)),
            nullable=True,
        ),
        sa.Column("nfe_volume_12m", sa.NUMERIC, nullable=True),
        sa.Column("nfe_ultima_emissao", sa.DATE, nullable=True),
        sa.Column("arquivei_ttl", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("faturamento_estimado", sa.NUMERIC, nullable=True),
        sa.Column("contatos", postgresql.JSONB, nullable=True),
        sa.Column("site", sa.Text, nullable=True),
        sa.Column("certificacoes", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("econodata_ttl", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("score_credito", sa.INTEGER, nullable=True),
        sa.Column("serasa_ttl", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "em_ceis",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "em_cnep",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "compliance_ultima_check",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # spend_classification_cache
    op.create_table(
        "spend_classification_cache",
        sa.Column("descricao_hash", sa.CHAR(32), primary_key=True),
        sa.Column("descricao_normalizada", sa.Text, nullable=False),
        sa.Column("cnae", sa.VARCHAR(7), nullable=False),
        sa.Column("confianca", sa.NUMERIC(3, 2), nullable=False),
        sa.Column("metodo", sa.VARCHAR(20), nullable=False),
        sa.Column("ttl", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("spend_classification_cache")
    op.drop_table("empresa_signals")
    op.drop_table("cnae_taxonomy")
    op.drop_index("idx_empresas_situacao", table_name="empresas")
    op.drop_index("idx_empresas_uf_municipio", table_name="empresas")
    op.drop_index("idx_empresas_cnae_primario", table_name="empresas")
    op.drop_table("empresas")
