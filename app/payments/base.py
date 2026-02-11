"""
Payment Provider - Abstract base for payment gateways.

Implementations: ManualProvider (admin confirms), Stripe, MercadoPago, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass
class CheckoutResult:
    """Result of creating a checkout (one-time or subscription)."""
    success: bool
    external_id: Optional[str] = None
    checkout_url: Optional[str] = None
    message: Optional[str] = None  # Instructions for manual payment
    error: Optional[str] = None


@dataclass
class PaymentStatus:
    """Current status of a payment."""
    external_id: str
    status: str  # pending, processing, confirmed, failed, refunded
    paid_at: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None


@dataclass
class SubscriptionResult:
    """Result of creating a subscription."""
    success: bool
    external_subscription_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class WebhookEvent:
    """Parsed webhook event from gateway."""
    event_type: str  # payment.confirmed, subscription.cancelled, etc.
    external_id: str
    payload: Dict[str, Any]


class PaymentProvider(ABC):
    """Abstract payment provider. Implement for Stripe, MercadoPago, manual, etc."""

    @abstractmethod
    def get_name(self) -> str:
        """Provider display name."""
        pass

    @abstractmethod
    def create_checkout(
        self,
        order_id: int,
        amount: Decimal,
        currency: str,
        payment_type: str,  # "setup" | "subscription"
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CheckoutResult:
        """Create a checkout session / payment link. Returns URL or instructions."""
        pass

    @abstractmethod
    def verify_payment(self, external_id: str) -> PaymentStatus:
        """Verify payment status by external ID."""
        pass

    def create_subscription(
        self,
        order_id: int,
        amount: Decimal,
        currency: str,
        interval: str = "monthly",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionResult:
        """Create recurring subscription. Optional override for gateways that support it."""
        return SubscriptionResult(success=False, error="Not supported by this provider")

    def cancel_subscription(self, external_subscription_id: str) -> bool:
        """Cancel a subscription. Optional override."""
        return False

    def handle_webhook(self, payload: bytes, headers: Optional[Dict[str, str]] = None) -> Optional[WebhookEvent]:
        """Parse and validate webhook payload. Returns event or None if invalid."""
        return None
