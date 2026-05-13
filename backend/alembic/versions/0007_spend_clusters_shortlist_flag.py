"""empresas: spend_clusters.shortlist_gerada idempotency flag

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spend_clusters",
        sa.Column(
            "shortlist_gerada",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("spend_clusters", "shortlist_gerada")
