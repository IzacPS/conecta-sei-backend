"""
Manual Payment Provider - Admin confirms payments in the system.

No gateway integration. Admin marks payment as confirmed via API.
Checkout returns instructions for the client (e.g. PIX key, bank transfer).
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from app.payments.base import CheckoutResult, PaymentProvider, PaymentStatus


class ManualProvider(PaymentProvider):
    """Provider that does not integrate with a gateway. Admin confirms payments manually."""

    def get_name(self) -> str:
        return "manual"

    def create_checkout(
        self,
        order_id: int,
        amount: Decimal,
        currency: str,
        payment_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CheckoutResult:
        # No URL; client pays via PIX/transfer and admin confirms in admin panel
        return CheckoutResult(
            success=True,
            external_id=f"manual-{order_id}-{payment_type}",
            checkout_url=None,
            message="Pagamento manual: efetue o pagamento e aguarde a confirmação pela nossa equipe.",
        )

    def verify_payment(self, external_id: str) -> PaymentStatus:
        # Manual provider does not verify externally; admin confirms in app
        return PaymentStatus(
            external_id=external_id,
            status="pending",
            paid_at=None,
            amount=None,
            currency=None,
        )
