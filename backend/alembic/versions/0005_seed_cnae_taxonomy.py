"""seed cnae taxonomy: ivfflat index

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-12
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS cnae_taxonomy_embedding_idx
        ON cnae_taxonomy
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 40);
        """
    )
    op.execute("ANALYZE cnae_taxonomy;")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS cnae_taxonomy_embedding_idx;")
