from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.models.model_base import SqlAlchemyModel
if TYPE_CHECKING:
    from app.database.models.institution import Institution


class ExtractionSchedule(SqlAlchemyModel):
    __tablename__ = "extraction_schedules"

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    schedule_type: Mapped[str] = mapped_column(
        String(20),  # interval | cron
        nullable=False,
    )

    interval_minutes: Mapped[Optional[int]]
    cron_hour: Mapped[Optional[int]]
    cron_minute: Mapped[Optional[int]]

    active: Mapped[bool] = mapped_column(default=True)

    institution = relationship("Institution", back_populates="extraction_schedule")
