"""Subscription model - recurring subscription for scraper access."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.model_base import SqlAlchemyModel


class Subscription(SqlAlchemyModel):
    __tablename__ = "subscriptions"

    order_id: Mapped[int] = mapped_column(
        ForeignKey("scraper_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )  # active, paused, cancelled, past_due
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    interval: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")

    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    external_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order = relationship("ScraperOrder", back_populates="subscriptions")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} order_id={self.order_id} status={self.status}>"
