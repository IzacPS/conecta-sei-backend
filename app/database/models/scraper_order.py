"""ScraperOrder model - commercial order linked to a pipeline request."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.model_base import SqlAlchemyModel


class ScraperOrder(SqlAlchemyModel):
    __tablename__ = "scraper_orders"

    pipeline_request_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    setup_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    monthly_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="quote_sent",
    )

    admin_notes: Mapped[Optional[str]] = mapped_column(Text)
    client_notes: Mapped[Optional[str]] = mapped_column(Text)

    estimated_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    quoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    pipeline_request = relationship("PipelineRequest", back_populates="scraper_order")
    user = relationship("User")
    payments = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    subscriptions = relationship(
        "Subscription",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ScraperOrder id={self.id} status={self.status}>"
