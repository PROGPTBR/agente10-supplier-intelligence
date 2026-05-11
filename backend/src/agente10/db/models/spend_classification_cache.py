from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, NUMERIC, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from agente10.db.base import Base


class SpendClassificationCache(Base):
    """Global cross-tenant cache of description → CNAE classifications.

    Keyed by MD5 hash of the normalized description. TTL controls staleness.
    """

    __tablename__ = "spend_classification_cache"

    descricao_hash: Mapped[str] = mapped_column(CHAR(32), primary_key=True)
    descricao_normalizada: Mapped[str] = mapped_column(Text, nullable=False)
    cnae: Mapped[str] = mapped_column(VARCHAR(7), nullable=False)
    confianca: Mapped[Decimal] = mapped_column(NUMERIC(3, 2), nullable=False)
    metodo: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    ttl: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
