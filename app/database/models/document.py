from typing import TYPE_CHECKING, Dict, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.database.models.model_base import SqlAlchemyModel

if TYPE_CHECKING:
    from app.database.models.process import Process


class Document(SqlAlchemyModel):
    __tablename__ = "documents"

    process_id: Mapped[int] = mapped_column(
        ForeignKey("processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    document_type: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="not_downloaded")
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))

    extra_metadata: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    process: Mapped["Process"] = relationship(
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return f"<Document number={self.document_number} process_id={self.process_id}>"
