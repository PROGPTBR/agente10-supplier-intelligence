"""spend_uploads.data_conclusao — when the pipeline finished (or failed)

Used to compute and display total processing duration on the UI.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-14
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE spend_uploads ADD COLUMN data_conclusao TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    op.execute("ALTER TABLE spend_uploads DROP COLUMN IF EXISTS data_conclusao")
