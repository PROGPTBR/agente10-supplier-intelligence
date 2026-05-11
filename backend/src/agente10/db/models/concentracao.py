import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import INTEGER, NUMERIC, TIMESTAMP, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class ConcentracaoCategoria(Base):
    """Estágio 2 output — HHI/diagnóstico por CNAE.

    Empty in modo catálogo (no transactional values to compute HHI).
    """

    __tablename__ = "concentracao_categorias"

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
    cnae: Mapped[str] = mapped_column(VARCHAR(7), nullable=False)
    spend_periodo: Mapped[Decimal | None] = mapped_column(NUMERIC(15, 2), nullable=True)
    fornecedores_unicos: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    transacoes: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    hhi: Mapped[Decimal | None] = mapped_column(NUMERIC(8, 2), nullable=True)
    fornecedor_dominante_cnpj: Mapped[str | None] = mapped_column(VARCHAR(14), nullable=True)
    fornecedor_dominante_share: Mapped[Decimal | None] = mapped_column(NUMERIC(3, 2), nullable=True)
    diagnostico_tipo: Mapped[str | None] = mapped_column(VARCHAR(30), nullable=True)
    diagnostico_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    prioridade: Mapped[Decimal | None] = mapped_column(NUMERIC(5, 2), nullable=True)
    data_calculo: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
