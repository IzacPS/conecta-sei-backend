from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.models.model_base import SqlAlchemyModel


class DocumentHistory(SqlAlchemyModel):
    __tablename__ = "document_history"

    process_id: Mapped[int] = mapped_column(
        ForeignKey("processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    old_status: Mapped[Optional[str]] = mapped_column(String(50))
    new_status: Mapped[Optional[str]] = mapped_column(String(50))

    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size: Mapped[Optional[str]] = mapped_column(String(50))

    performed_by: Mapped[str] = mapped_column(
        String(255),
        default="system",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    extra_metadata: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentHistory doc={self.document_number} "
            f"action={self.action}>"
        )
