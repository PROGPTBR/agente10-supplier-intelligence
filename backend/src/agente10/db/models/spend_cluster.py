import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BOOLEAN,
    INTEGER,
    NUMERIC,
    TIMESTAMP,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class SpendCluster(Base):
    """AI-grouped cluster of spend lines that share a single CNAE.

    Output of Estágio 1 in catalogo mode: lines with similar descriptions
    (e.g., 'gerador', 'Locação gerador', 'locação de gerador') get grouped
    into one cluster, and that cluster gets a single CNAE assigned.
    """

    __tablename__ = "spend_clusters"

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
    nome_cluster: Mapped[str] = mapped_column(Text, nullable=False)
    cnae: Mapped[str | None] = mapped_column(VARCHAR(7), nullable=True)
    cnae_confianca: Mapped[Decimal | None] = mapped_column(NUMERIC(3, 2), nullable=True)
    cnae_metodo: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    num_linhas: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default="0")
    revisado_humano: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default="false")
    notas_revisor: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_geracao: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
