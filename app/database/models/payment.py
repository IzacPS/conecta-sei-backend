"""Payment model - individual payment record for scraper orders."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.model_base import SqlAlchemyModel


class Payment(SqlAlchemyModel):
    __tablename__ = "payments"

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

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")

    payment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "setup" | "subscription"
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )  # pending, processing, confirmed, failed, refunded
    payment_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
    )  # pix, boleto, card, transfer, manual
    external_provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual",
    )  # stripe, mercadopago, manual, etc.
    external_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    external_checkout_url: Mapped[Optional[str]] = mapped_column(Text)

    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    order = relationship("ScraperOrder", back_populates="payments")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} order_id={self.order_id} status={self.status}>"
