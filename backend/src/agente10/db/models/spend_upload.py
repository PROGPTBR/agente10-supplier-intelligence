import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    INTEGER,
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class SpendUpload(Base):
    """Each upload of a spend file (XLSX/CSV).

    Tenant-scoped (RLS protected). The `modo` column drives the pipeline:
    'catalogo' (no values, categorias only) or 'transacional' (full spend lines).
    """

    __tablename__ = "spend_uploads"
    __table_args__ = (
        CheckConstraint(
            "modo IN ('catalogo', 'transacional')",
            name="spend_uploads_modo_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    nome_arquivo: Mapped[str] = mapped_column(Text, nullable=False)
    object_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    data_upload: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    linhas_total: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="0")
    linhas_classificadas: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="0")
    modo: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, server_default="catalogo")
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, server_default="pending")
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadados: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
