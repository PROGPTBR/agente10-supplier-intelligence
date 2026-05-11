import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BOOLEAN,
    INTEGER,
    NUMERIC,
    TIMESTAMP,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class SupplierShortlist(Base):
    """Final supplier shortlist for a category (output of Estágios 3 + 4)."""

    __tablename__ = "supplier_shortlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    concentracao_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concentracao_categorias.id"),
        nullable=True,
    )
    cnae: Mapped[str] = mapped_column(VARCHAR(7), nullable=False)
    cnpj_fornecedor: Mapped[str] = mapped_column(
        VARCHAR(14), ForeignKey("empresas.cnpj"), nullable=False
    )
    score_total: Mapped[Decimal | None] = mapped_column(NUMERIC(3, 2), nullable=True)
    scores_por_dimensao: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rank_estagio3: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    rank_estagio4: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    enriquecimento_completo: Mapped[bool] = mapped_column(
        BOOLEAN, nullable=False, server_default="false"
    )
    handoff_rfx: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default="false")
    notas_internas: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_geracao: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
