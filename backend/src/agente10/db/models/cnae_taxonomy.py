from pgvector.sqlalchemy import Vector
from sqlalchemy import CHAR, Text
from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class CnaeTaxonomy(Base):
    """Taxonomia CNAE 2.3 + embeddings Voyage-3 (1024 dim)."""

    __tablename__ = "cnae_taxonomy"

    codigo: Mapped[str] = mapped_column(VARCHAR(7), primary_key=True)
    secao: Mapped[str | None] = mapped_column(CHAR(1), nullable=True)
    divisao: Mapped[str | None] = mapped_column(VARCHAR(2), nullable=True)
    grupo: Mapped[str | None] = mapped_column(VARCHAR(3), nullable=True)
    classe: Mapped[str | None] = mapped_column(VARCHAR(5), nullable=True)
    denominacao: Mapped[str] = mapped_column(Text, nullable=False)
    notas_explicativas: Mapped[str | None] = mapped_column(Text, nullable=True)
    exemplos_atividades: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
