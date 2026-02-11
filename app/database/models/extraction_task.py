from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.model_base import SqlAlchemyModel


class ExtractionTask(SqlAlchemyModel):
    __tablename__ = "extraction_tasks"

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    trigger_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    total_processes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    processed_processes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    last_error: Mapped[Optional[str]] = mapped_column(Text)

    result_summary: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    institution = relationship("Institution", back_populates="extraction_tasks")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ExtractionTask id={self.id} status={self.status}>"
