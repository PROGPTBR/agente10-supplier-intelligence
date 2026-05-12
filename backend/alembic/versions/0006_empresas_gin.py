"""empresas: GIN index on cnaes_secundarios

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-12
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS empresas_cnaes_secundarios_gin
        ON empresas USING GIN (cnaes_secundarios);
        """
    )
    op.execute("ANALYZE empresas;")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS empresas_cnaes_secundarios_gin;")
