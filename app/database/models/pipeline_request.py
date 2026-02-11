"""PipelineRequest model - self-service pipeline onboarding."""

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.model_base import SqlAlchemyModel


class PipelineRequest(SqlAlchemyModel):
    __tablename__ = "pipeline_requests"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sei_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    institution_name: Mapped[Optional[str]] = mapped_column(String(255))

    detected_version: Mapped[Optional[str]] = mapped_column(String(50))
    detected_family: Mapped[Optional[str]] = mapped_column(String(20))

    scraper_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="analyzing",
    )

    institution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"),
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User")
    institution = relationship("Institution")
    scraper_order = relationship(
        "ScraperOrder",
        back_populates="pipeline_request",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PipelineRequest id={self.id} url={self.sei_url} status={self.status}>"
