"""
Payment providers - abstraction for payment gateways.

Usage:
    from app.payments import get_payment_provider

    provider = get_payment_provider()
    result = provider.create_checkout(order_id=1, amount=Decimal("100.00"), ...)

Set PAYMENT_PROVIDER env var to "manual" (default), "stripe", "mercadopago", etc.
"""

import os
from app.payments.base import (
    CheckoutResult,
    PaymentProvider,
    PaymentStatus,
    SubscriptionResult,
    WebhookEvent,
)
from app.payments.manual_provider import ManualProvider


def get_payment_provider() -> PaymentProvider:
    """Return the configured payment provider instance."""
    name = (os.getenv("PAYMENT_PROVIDER") or "manual").strip().lower()
    if name == "manual":
        return ManualProvider()
    # Future: if name == "stripe": return StripeProvider(); etc.
    return ManualProvider()


__all__ = [
    "get_payment_provider",
    "PaymentProvider",
    "ManualProvider",
    "CheckoutResult",
    "PaymentStatus",
    "SubscriptionResult",
    "WebhookEvent",
]
