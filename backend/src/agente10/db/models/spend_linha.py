import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    DATE,
    NUMERIC,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class SpendLinha(Base):
    """One line from an uploaded spend file.

    Catalogo mode: only agrupamento + descricao_original required.
    Transacional mode: financial fields populated.
    `cluster_id` links to the AI-determined cluster (denormalized cnae for fast filters).
    """

    __tablename__ = "spend_linhas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spend_uploads.id"), nullable=False
    )
    id_linha_origem: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Catálogo
    agrupamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    descricao_original: Mapped[str] = mapped_column(Text, nullable=False)
    descricao_normalizada: Mapped[str | None] = mapped_column(Text, nullable=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spend_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Transacional (nullable em modo catálogo)
    fornecedor_atual: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnpj_fornecedor: Mapped[str | None] = mapped_column(VARCHAR(14), nullable=True)
    valor_total: Mapped[Decimal | None] = mapped_column(NUMERIC(15, 2), nullable=True)
    quantidade: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)
    uf_solicitante: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    municipio_solicitante: Mapped[str | None] = mapped_column(Text, nullable=True)
    centro_custo: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_compra: Mapped[date | None] = mapped_column(DATE, nullable=True)

    # Output Estágio 1 (denormalizado de spend_clusters.cnae)
    cnae: Mapped[str | None] = mapped_column(VARCHAR(7), nullable=True)
    cnae_confianca: Mapped[Decimal | None] = mapped_column(NUMERIC(3, 2), nullable=True)
    cnae_metodo: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)

    extras: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
