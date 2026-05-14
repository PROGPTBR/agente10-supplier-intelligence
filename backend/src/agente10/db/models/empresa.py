from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, CHAR, DATE, NUMERIC, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class Empresa(Base):
    """Empresa cadastrada na base RF.

    CNPJ is the primary key — alphanumeric VARCHAR(14) per jul/2026 RF spec.
    CNAE columns are 7-digit numeric strings (no dots/slashes).
    """

    __tablename__ = "empresas"

    cnpj: Mapped[str] = mapped_column(VARCHAR(14), primary_key=True)
    razao_social: Mapped[str] = mapped_column(Text, nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnae_primario: Mapped[str] = mapped_column(VARCHAR(7), nullable=False)
    cnaes_secundarios: Mapped[list[str]] = mapped_column(
        ARRAY(VARCHAR(7)), nullable=False, server_default="{}"
    )
    situacao_cadastral: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    data_abertura: Mapped[date | None] = mapped_column(DATE, nullable=True)
    porte: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    capital_social: Mapped[Decimal | None] = mapped_column(NUMERIC(15, 2), nullable=True)
    faixa_funcionarios: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    natureza_juridica: Mapped[str | None] = mapped_column(VARCHAR(10), nullable=True)
    uf: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    municipio: Mapped[str | None] = mapped_column(Text, nullable=True)
    cep: Mapped[str | None] = mapped_column(VARCHAR(8), nullable=True)
    endereco: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    ultima_atualizacao_rf: Mapped[date] = mapped_column(DATE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
