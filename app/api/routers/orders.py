"""
Orders Router - Client endpoints for scraper orders.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.models.payment import Payment
from app.database.models.pipeline_request import PipelineRequest
from app.database.models.scraper_order import ScraperOrder
from app.database.session import get_db
from app.payments import get_payment_provider
from app.utils.enums import PipelineRequestStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──

class OrderListItem(BaseModel):
    id: int
    pipeline_request_id: int
    setup_price: Decimal
    monthly_price: Decimal
    currency: str
    status: str
    client_notes: Optional[str]
    estimated_delivery_at: Optional[datetime]
    created_at: Optional[datetime]
    sei_url: Optional[str] = None
    institution_name: Optional[str] = None
    detected_version: Optional[str] = None


class PaymentItem(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    currency: str
    payment_type: str
    status: str
    payment_method: str
    paid_at: Optional[datetime]
    created_at: Optional[datetime]


class OrderDetailResponse(BaseModel):
    id: int
    pipeline_request_id: int
    setup_price: Decimal
    monthly_price: Decimal
    currency: str
    status: str
    client_notes: Optional[str]
    admin_notes: Optional[str]
    estimated_delivery_at: Optional[datetime]
    quoted_at: Optional[datetime]
    accepted_at: Optional[datetime]
    delivered_at: Optional[datetime]
    created_at: Optional[datetime]
    sei_url: Optional[str] = None
    institution_name: Optional[str] = None
    detected_version: Optional[str] = None
    institution_id: Optional[int] = None
    pipeline_request_status: Optional[str] = None
    payments: List[PaymentItem] = []


class CheckoutResponse(BaseModel):
    success: bool
    checkout_url: Optional[str] = None
    message: Optional[str] = None
    payment_id: Optional[int] = None
    error: Optional[str] = None


# ── Endpoints ──

@router.get("/orders", response_model=dict)
async def list_my_orders(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's scraper orders."""
    result = await db.execute(
        select(ScraperOrder)
        .where(ScraperOrder.user_id == user.db_id)
        .order_by(ScraperOrder.created_at.desc())
    )
    orders = result.scalars().all()
    out = []
    for o in orders:
        pr_result = await db.execute(select(PipelineRequest).where(PipelineRequest.id == o.pipeline_request_id))
        pr = pr_result.scalar_one_or_none()
        out.append(OrderListItem(
            id=o.id,
            pipeline_request_id=o.pipeline_request_id,
            setup_price=o.setup_price,
            monthly_price=o.monthly_price,
            currency=o.currency,
            status=o.status,
            client_notes=o.client_notes,
            estimated_delivery_at=o.estimated_delivery_at,
            created_at=getattr(o, "created_at", None),
            sei_url=pr.sei_url if pr else None,
            institution_name=pr.institution_name if pr else None,
            detected_version=pr.detected_version if pr else None,
        ).model_dump())
    return {"orders": out}


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_my_order(
    order_id: int,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get order detail (own orders only)."""
    order_result = await db.execute(
        select(ScraperOrder).where(
            ScraperOrder.id == order_id,
            ScraperOrder.user_id == user.db_id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    pr_result = await db.execute(select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id))
    pr = pr_result.scalar_one_or_none()
    payments_result = await db.execute(
        select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
    )
    payments = payments_result.scalars().all()
    return OrderDetailResponse(
        id=order.id,
        pipeline_request_id=order.pipeline_request_id,
        setup_price=order.setup_price,
        monthly_price=order.monthly_price,
        currency=order.currency,
        status=order.status,
        client_notes=order.client_notes,
        admin_notes=order.admin_notes,
        estimated_delivery_at=order.estimated_delivery_at,
        quoted_at=order.quoted_at,
        accepted_at=order.accepted_at,
        delivered_at=order.delivered_at,
        created_at=getattr(order, "created_at", None),
        sei_url=pr.sei_url if pr else None,
        institution_name=pr.institution_name if pr else None,
        detected_version=pr.detected_version if pr else None,
        institution_id=pr.institution_id if pr else None,
        pipeline_request_status=pr.status if pr else None,
        payments=[
            PaymentItem(
                id=p.id,
                order_id=p.order_id,
                amount=p.amount,
                currency=p.currency,
                payment_type=p.payment_type,
                status=p.status,
                payment_method=p.payment_method,
                paid_at=p.paid_at,
                created_at=getattr(p, "created_at", None),
            )
            for p in payments
        ],
    )


@router.post("/orders/{order_id}/accept")
async def accept_order(
    order_id: int,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept quote (move to pending_payment)."""
    order_result = await db.execute(
        select(ScraperOrder).where(
            ScraperOrder.id == order_id,
            ScraperOrder.user_id == user.db_id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "quote_sent":
        raise HTTPException(status_code=400, detail="Order is not in quote_sent status")
    pr_result = await db.execute(select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id))
    pr = pr_result.scalar_one_or_none()
    order.status = "pending_payment"
    order.accepted_at = datetime.utcnow()
    if pr:
        pr.status = PipelineRequestStatus.PENDING_PAYMENT
    await db.flush()
    return {"ok": True, "status": "pending_payment", "message": "Orçamento aceito. Efetue o pagamento."}


@router.post("/orders/{order_id}/reject")
async def reject_order(
    order_id: int,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject quote."""
    order_result = await db.execute(
        select(ScraperOrder).where(
            ScraperOrder.id == order_id,
            ScraperOrder.user_id == user.db_id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "quote_sent":
        raise HTTPException(status_code=400, detail="Order is not in quote_sent status")
    pr_result = await db.execute(select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id))
    pr = pr_result.scalar_one_or_none()
    order.status = "cancelled"
    if pr:
        pr.status = PipelineRequestStatus.REJECTED
    await db.flush()
    return {"ok": True, "message": "Orçamento recusado."}


@router.post("/orders/{order_id}/checkout", response_model=CheckoutResponse)
async def create_checkout(
    order_id: int,
    payment_type: str = "setup",
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start payment (setup or subscription). Returns checkout URL or instructions."""
    if payment_type not in ("setup", "subscription"):
        raise HTTPException(status_code=400, detail="payment_type must be setup or subscription")
    order_result = await db.execute(
        select(ScraperOrder).where(
            ScraperOrder.id == order_id,
            ScraperOrder.user_id == user.db_id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if payment_type == "setup" and order.setup_price <= 0:
        raise HTTPException(status_code=400, detail="Setup price is zero")
    if payment_type == "subscription" and order.monthly_price <= 0:
        raise HTTPException(status_code=400, detail="Monthly price is zero")

    provider = get_payment_provider()
    amount = order.setup_price if payment_type == "setup" else order.monthly_price
    result = provider.create_checkout(
        order_id=order.id,
        amount=amount,
        currency=order.currency,
        payment_type=payment_type,
        metadata={"user_id": user.db_id},
    )
    if not result.success:
        return CheckoutResponse(success=False, error=result.error or "Checkout failed")

    payment = Payment(
        order_id=order.id,
        user_id=user.db_id,
        amount=amount,
        currency=order.currency,
        payment_type=payment_type,
        status="pending",
        payment_method=provider.get_name(),
        external_provider=provider.get_name(),
        external_id=result.external_id,
        external_checkout_url=result.checkout_url,
        metadata_={},
    )
    db.add(payment)
    await db.flush()
    return CheckoutResponse(
        success=True,
        checkout_url=result.checkout_url,
        message=result.message,
        payment_id=payment.id,
    )


@router.get("/orders/{order_id}/payments", response_model=dict)
async def list_order_payments(
    order_id: int,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List payments for an order (own orders only)."""
    order_result = await db.execute(
        select(ScraperOrder).where(
            ScraperOrder.id == order_id,
            ScraperOrder.user_id == user.db_id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    payments_result = await db.execute(
        select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
    )
    payments = payments_result.scalars().all()
    return {
        "payments": [
            PaymentItem(
                id=p.id,
                order_id=p.order_id,
                amount=p.amount,
                currency=p.currency,
                payment_type=p.payment_type,
                status=p.status,
                payment_method=p.payment_method,
                paid_at=p.paid_at,
                created_at=getattr(p, "created_at", None),
            ).model_dump()
            for p in payments
        ]
    }
