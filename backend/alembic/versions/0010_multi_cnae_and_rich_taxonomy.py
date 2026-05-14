"""multi-CNAE per cluster + rich taxonomy (hierarchy + rerank-friendly embedding)

Adds:
- spend_clusters.cnaes_secundarios: ARRAY of additional CNAEs the cluster covers
- spend_clusters.nome_cluster_refinado: LLM-refined name connected to CNAE intent
- cnae_taxonomy.divisao_descricao: Divisão-level intro from IBGE PDF
- cnae_taxonomy.grupo_descricao: Grupo-level intro from IBGE PDF
- cnae_taxonomy.embedding_rich: Voyage embedding of (denominacao + exemplos)
  for hybrid retrieval — separate column to preserve original `embedding`
  recall characteristics

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-14
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE spend_clusters "
        "ADD COLUMN cnaes_secundarios VARCHAR(7)[] NOT NULL DEFAULT '{}'::VARCHAR[]"
    )
    op.execute("ALTER TABLE spend_clusters ADD COLUMN nome_cluster_refinado TEXT")

    op.execute("ALTER TABLE cnae_taxonomy ADD COLUMN divisao_descricao TEXT")
    op.execute("ALTER TABLE cnae_taxonomy ADD COLUMN grupo_descricao TEXT")
    op.execute("ALTER TABLE cnae_taxonomy ADD COLUMN embedding_rich vector(1024)")
    # ivfflat (cosine) — keep small lists for now; can REINDEX with more lists later
    op.execute(
        "CREATE INDEX idx_cnae_taxonomy_embedding_rich "
        "ON cnae_taxonomy USING ivfflat (embedding_rich vector_cosine_ops) "
        "WITH (lists = 40)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cnae_taxonomy_embedding_rich")
    op.execute("ALTER TABLE cnae_taxonomy DROP COLUMN IF EXISTS embedding_rich")
    op.execute("ALTER TABLE cnae_taxonomy DROP COLUMN IF EXISTS grupo_descricao")
    op.execute("ALTER TABLE cnae_taxonomy DROP COLUMN IF EXISTS divisao_descricao")
    op.execute("ALTER TABLE spend_clusters DROP COLUMN IF EXISTS nome_cluster_refinado")
    op.execute("ALTER TABLE spend_clusters DROP COLUMN IF EXISTS cnaes_secundarios")
