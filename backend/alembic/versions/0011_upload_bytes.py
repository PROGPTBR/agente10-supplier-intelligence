"""spend_uploads.file_bytes — store CSV content in Postgres for cross-container access

The API container writes uploads to its local /app/data/uploads/ filesystem,
but the worker container (separate Railway service running arq) doesn't see
that filesystem. Solution: persist the raw bytes in Postgres alongside the
path, so the worker can read them via DATABASE_URL.

After _parse_stage succeeds (spend_linhas populated), the bytes are cleared
to NULL to save space — they're no longer needed since retry skips parse
when linhas already exist.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-14
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE spend_uploads ADD COLUMN file_bytes BYTEA")


def downgrade() -> None:
    op.execute("ALTER TABLE spend_uploads DROP COLUMN IF EXISTS file_bytes")
