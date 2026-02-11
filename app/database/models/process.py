from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
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
    from app.database.models.institution import Institution
    from app.database.models.document import Document
    from app.database.models.receipt import Receipt


class Process(SqlAlchemyModel):
    __tablename__ = "processes"

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    process_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    links: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    best_current_link: Mapped[Optional[str]] = mapped_column(String(500))

    access_type: Mapped[Optional[str]] = mapped_column(String(20))
    category: Mapped[Optional[str]] = mapped_column(String(50))
    category_status: Mapped[Optional[str]] = mapped_column(String(50))

    unit: Mapped[Optional[str]] = mapped_column(String(255))
    authority: Mapped[Optional[str]] = mapped_column(String(255))

    no_valid_links: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    nickname: Mapped[Optional[str]] = mapped_column(String(255))

    documents_data: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    extra_metadata: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    institution: Mapped["Institution"] = relationship(
        back_populates="processes",
    )

    documents: Mapped[List["Document"]] = relationship(
        back_populates="process",
        cascade="all, delete-orphan",
    )

    receipts: Mapped[List["Receipt"]] = relationship(
        back_populates="process",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Process number={self.process_number} "
            f"institution={self.institution_id}>"
        )
