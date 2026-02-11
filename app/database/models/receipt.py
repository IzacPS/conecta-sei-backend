from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.database.models.model_base import SqlAlchemyModel

if TYPE_CHECKING:
    from app.database.models.process import Process


class Receipt(SqlAlchemyModel):
    __tablename__ = "receipts"

    process_id: Mapped[int] = mapped_column(
        ForeignKey("processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    number: Mapped[str] = mapped_column(String(50), nullable=False)
    signatory: Mapped[Optional[str]] = mapped_column(String(255))
    document_numbers: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)

    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    process: Mapped["Process"] = relationship(
        back_populates="receipts",
    )

    def __repr__(self) -> str:
        return f"<Receipt number={self.number} process_id={self.process_id}>"
