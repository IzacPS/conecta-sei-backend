from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import (
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.session import Base


class SystemConfiguration(Base):
    __tablename__ = "system_configuration"

    key: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    value: Mapped[Dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    updated_by: Mapped[str] = mapped_column(
        String(255),
        default="system",
    )

    def __repr__(self) -> str:
        return f"<SystemConfiguration key={self.key}>"
