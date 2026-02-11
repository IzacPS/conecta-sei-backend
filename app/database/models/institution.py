from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.models.model_base import SqlAlchemyModel

if TYPE_CHECKING:
    from app.database.models.extraction_schedule import ExtractionSchedule
    from app.database.models.extraction_task import ExtractionTask
    from app.database.models.process import Process


class Institution(SqlAlchemyModel):
    __tablename__ = "institutions"

    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sei_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    processes: Mapped[List["Process"]] = relationship(
        back_populates="institution",
        cascade="all, delete-orphan",
    )

    scraper_bindings = relationship(
        "InstitutionScraper",
        back_populates="institution",
        cascade="all, delete-orphan",
    )

    credentials = relationship(
        "InstitutionCredential",
        back_populates="institution",
        cascade="all, delete-orphan",
    )

    extraction_schedule = relationship(
        "ExtractionSchedule",
        back_populates="institution",
        uselist=False,
        cascade="all, delete-orphan",
    )

    extraction_tasks = relationship(
        "ExtractionTask",
        back_populates="institution",
        cascade="all, delete-orphan",
    )

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Institution id={self.id} name={self.name}>"
