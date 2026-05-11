"""extend tenants with cnpj, plano, config

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("cnpj", sa.VARCHAR(14), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "plano",
            sa.VARCHAR(20),
            nullable=False,
            server_default="standard",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "config",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "tenants_cnpj_len_chk",
        "tenants",
        "cnpj IS NULL OR length(cnpj) = 14",
    )


def downgrade() -> None:
    op.drop_constraint("tenants_cnpj_len_chk", "tenants", type_="check")
    op.drop_column("tenants", "config")
    op.drop_column("tenants", "plano")
    op.drop_column("tenants", "cnpj")
