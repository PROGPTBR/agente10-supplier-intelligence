"""spend_classification_cache: add embedding column for few-shot NN search

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-14
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE spend_classification_cache ADD COLUMN embedding vector(1024)")
    # ivfflat (cosine) for few-shot nearest-neighbor lookup. Small lists for the
    # cache (a few thousand rows at most); probes=10 default at query time.
    op.execute(
        "CREATE INDEX idx_cache_embedding "
        "ON spend_classification_cache USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 20)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cache_embedding")
    op.execute("ALTER TABLE spend_classification_cache DROP COLUMN IF EXISTS embedding")
