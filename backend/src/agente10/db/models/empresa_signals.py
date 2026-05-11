from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ARRAY, BOOLEAN, DATE, INTEGER, NUMERIC, TIMESTAMP, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class EmpresaSignals(Base):
    """Cached enrichment from external APIs (Arquivei, Econodata, Serasa, CEIS/CNEP).

    Shared across tenants (no RLS). One row per CNPJ.
    """

    __tablename__ = "empresa_signals"

    cnpj: Mapped[str] = mapped_column(VARCHAR(14), ForeignKey("empresas.cnpj"), primary_key=True)

    # Arquivei
    emite_nfe_categorias: Mapped[list[str] | None] = mapped_column(ARRAY(VARCHAR(7)), nullable=True)
    nfe_volume_12m: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)
    nfe_ultima_emissao: Mapped[date | None] = mapped_column(DATE, nullable=True)
    arquivei_ttl: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Econodata
    faturamento_estimado: Mapped[Decimal | None] = mapped_column(NUMERIC, nullable=True)
    contatos: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    site: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificacoes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    econodata_ttl: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Serasa
    score_credito: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    serasa_ttl: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Compliance
    em_ceis: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default="false")
    em_cnep: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default="false")
    compliance_ultima_check: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
