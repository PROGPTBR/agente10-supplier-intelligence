import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, CheckConstraint, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "cnpj IS NULL OR length(cnpj) = 14",
            name="tenants_cnpj_len_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    cnpj: Mapped[str | None] = mapped_column(VARCHAR(14), nullable=True)
    plano: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, server_default="standard")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
