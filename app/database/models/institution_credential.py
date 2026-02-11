from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.model_base import SqlAlchemyModel


class InstitutionCredential(SqlAlchemyModel):
    __tablename__ = "institution_credentials"

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    credential_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="login",
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    secret_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    rotated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    institution = relationship("Institution", back_populates="credentials")

    def __repr__(self) -> str:
        return f"<InstitutionCredential institution_id={self.institution_id} type={self.credential_type}>"
