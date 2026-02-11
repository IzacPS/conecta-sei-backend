from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from app.database.models.model_base import SqlAlchemyModel
from sqlalchemy.orm import Mapped, mapped_column, relationship

class InstitutionScraper(SqlAlchemyModel):
    __tablename__ = "institution_scrapers"

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scraper_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    institution = relationship("Institution", back_populates="scraper_bindings")
