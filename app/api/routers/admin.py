"""
Admin Router - Admin-only endpoints for pipeline requests, orders, payments.

All endpoints require get_current_admin (role=admin).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_admin
from app.database.session import get_db
from app.database.models.pipeline_request import PipelineRequest
from app.database.models.scraper_order import ScraperOrder
from app.database.models.payment import Payment
from app.database.models.subscription import Subscription
from app.database.models.institution import Institution
from app.database.models.institution_scraper import InstitutionScraper
from app.database.models.user import User
from app.utils.enums import PipelineRequestStatus

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──

class PipelineRequestListItem(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    sei_url: str
    institution_name: Optional[str]
    detected_version: Optional[str]
    detected_family: Optional[str]
    scraper_available: bool
    status: str
    institution_id: Optional[int]
    error_message: Optional[str]
    created_at: Optional[datetime] = None


class PipelineRequestDetailResponse(BaseModel):
    id: int
    user_id: int
    sei_url: str
    institution_name: Optional[str]
    detected_version: Optional[str]
    detected_family: Optional[str]
    scraper_available: bool
    status: str
    institution_id: Optional[int]
    error_message: Optional[str]
    created_at: Optional[datetime] = None
    user_email: Optional[str] = None


class CreateOrderSchema(BaseModel):
    pipeline_request_id: int = Field(..., description="Pipeline request to quote")
    setup_price: float = Field(0, ge=0)
    monthly_price: float = Field(0, ge=0)
    currency: str = Field("BRL", max_length=3)
    client_notes: Optional[str] = None
    admin_notes: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None


class UpdateOrderSchema(BaseModel):
    setup_price: Optional[float] = Field(None, ge=0)
    monthly_price: Optional[float] = Field(None, ge=0)
    client_notes: Optional[str] = None
    admin_notes: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None


class OrderListItem(BaseModel):
    id: int
    pipeline_request_id: int
    user_id: int
    setup_price: Decimal
    monthly_price: Decimal
    currency: str
    status: str
    estimated_delivery_at: Optional[datetime]
    created_at: Optional[datetime] = None
    user_email: Optional[str] = None
    institution_name: Optional[str] = None


class PaymentListItem(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    currency: str
    payment_type: str
    status: str
    payment_method: str
    paid_at: Optional[datetime]
    created_at: Optional[datetime] = None


class OrderDetailResponse(BaseModel):
    id: int
    pipeline_request_id: int
    user_id: int
    setup_price: Decimal
    monthly_price: Decimal
    currency: str
    status: str
    admin_notes: Optional[str]
    client_notes: Optional[str]
    estimated_delivery_at: Optional[datetime]
    quoted_at: Optional[datetime]
    accepted_at: Optional[datetime]
    delivered_at: Optional[datetime]
    created_at: Optional[datetime] = None
    user_email: Optional[str] = None
    sei_url: Optional[str] = None
    institution_name: Optional[str] = None
    detected_version: Optional[str] = None
    institution_id: Optional[int] = None
    payments: List[PaymentListItem] = []


class ConfirmPaymentSchema(BaseModel):
    payment_id: Optional[int] = None  # If not set, confirm latest pending setup payment
    payment_method: str = Field("manual", max_length=20)


class SubscriptionListItem(BaseModel):
    id: int
    order_id: int
    user_id: int
    status: str
    amount: Decimal
    currency: str
    interval: str
    current_period_end: Optional[datetime]
    created_at: Optional[datetime] = None


class AdminStatsResponse(BaseModel):
    pipeline_requests_pending: int
    orders_pending_payment: int
    orders_in_development: int
    revenue_this_month: float
    active_subscriptions: int


# ── Pipeline requests ──

@router.get("/pipeline-requests", response_model=dict)
async def list_admin_pipeline_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all pipeline requests (admin). Optional filter by status."""
    q = select(PipelineRequest).order_by(PipelineRequest.created_at.desc())
    if status:
        q = q.where(PipelineRequest.status == status)
    res = await db.execute(q)
    requests = res.scalars().all()
    result = []
    for r in requests:
        u_res = await db.execute(select(User).where(User.id == r.user_id))
        u = u_res.scalar_one_or_none()
        result.append(PipelineRequestListItem(
            id=r.id,
            user_id=r.user_id,
            user_email=u.email if u else None,
            sei_url=r.sei_url,
            institution_name=r.institution_name,
            detected_version=r.detected_version,
            detected_family=r.detected_family,
            scraper_available=r.scraper_available,
            status=r.status,
            institution_id=r.institution_id,
            error_message=r.error_message,
            created_at=getattr(r, "created_at", None),
        ).model_dump())
    return {"requests": result}


@router.get("/pipeline-requests/{request_id}", response_model=PipelineRequestDetailResponse)
async def get_admin_pipeline_request(
    request_id: int,
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline request detail (admin)."""
    pr_res = await db.execute(select(PipelineRequest).where(PipelineRequest.id == request_id))
    pr = pr_res.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pipeline request not found")
    u_res = await db.execute(select(User).where(User.id == pr.user_id))
    u = u_res.scalar_one_or_none()
    return PipelineRequestDetailResponse(
        id=pr.id,
        user_id=pr.user_id,
        sei_url=pr.sei_url,
        institution_name=pr.institution_name,
        detected_version=pr.detected_version,
        detected_family=pr.detected_family,
        scraper_available=pr.scraper_available,
        status=pr.status,
        institution_id=pr.institution_id,
        error_message=pr.error_message,
        created_at=getattr(pr, "created_at", None),
        user_email=u.email if u else None,
    )


# ── Orders ──

@router.post("/orders", response_model=OrderDetailResponse)
async def create_order(
    data: CreateOrderSchema,
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a scraper order (quote) for a pipeline request."""
    pr_res = await db.execute(select(PipelineRequest).where(PipelineRequest.id == data.pipeline_request_id))
    pr = pr_res.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pipeline request not found")
    if pr.status != PipelineRequestStatus.PENDING_SCRAPER:
        raise HTTPException(
            status_code=400,
            detail="Only pipeline requests with status pending_scraper can receive a quote",
        )
    existing_res = await db.execute(
        select(ScraperOrder).where(ScraperOrder.pipeline_request_id == data.pipeline_request_id)
    )
    existing = existing_res.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Order already exists for this pipeline request")

    order = ScraperOrder(
        pipeline_request_id=data.pipeline_request_id,
        user_id=pr.user_id,
        setup_price=Decimal(str(data.setup_price)),
        monthly_price=Decimal(str(data.monthly_price)),
        currency=data.currency,
        status="quote_sent",
        client_notes=data.client_notes,
        admin_notes=data.admin_notes,
        estimated_delivery_at=data.estimated_delivery_at,
        quoted_at=datetime.utcnow(),
    )
    db.add(order)
    pr.status = PipelineRequestStatus.QUOTE_SENT
    await db.flush()

    u_res = await db.execute(select(User).where(User.id == order.user_id))
    u = u_res.scalar_one_or_none()
    return OrderDetailResponse(
        id=order.id,
        pipeline_request_id=order.pipeline_request_id,
        user_id=order.user_id,
        setup_price=order.setup_price,
        monthly_price=order.monthly_price,
        currency=order.currency,
        status=order.status,
        admin_notes=order.admin_notes,
        client_notes=order.client_notes,
        estimated_delivery_at=order.estimated_delivery_at,
        quoted_at=order.quoted_at,
        accepted_at=order.accepted_at,
        delivered_at=order.delivered_at,
        created_at=getattr(order, "created_at", None),
        user_email=u.email if u else None,
        sei_url=pr.sei_url,
        institution_name=pr.institution_name,
        detected_version=pr.detected_version,
        institution_id=pr.institution_id,
        payments=[],
    )


@router.get("/orders", response_model=dict)
async def list_admin_orders(
    status: Optional[str] = Query(None),
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all scraper orders (admin)."""
    q = select(ScraperOrder).order_by(ScraperOrder.created_at.desc())
    if status:
        q = q.where(ScraperOrder.status == status)
    res = await db.execute(q)
    orders = res.scalars().all()
    result = []
    for o in orders:
        u_res = await db.execute(select(User).where(User.id == o.user_id))
        u = u_res.scalar_one_or_none()
        pr_res = await db.execute(select(PipelineRequest).where(PipelineRequest.id == o.pipeline_request_id))
        pr = pr_res.scalar_one_or_none()
        result.append(OrderListItem(
            id=o.id,
            pipeline_request_id=o.pipeline_request_id,
            user_id=o.user_id,
            setup_price=o.setup_price,
            monthly_price=o.monthly_price,
            currency=o.currency,
            status=o.status,
            estimated_delivery_at=o.estimated_delivery_at,
            created_at=getattr(o, "created_at", None),
            user_email=u.email if u else None,
            institution_name=pr.institution_name if pr else None,
        ).model_dump())
    return {"orders": result}


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_admin_order(
    order_id: int,
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get order detail (admin)."""
    order_res = await db.execute(select(ScraperOrder).where(ScraperOrder.id == order_id))
    order = order_res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    pr_res = await db.execute(select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id))
    pr = pr_res.scalar_one_or_none()
    u_res = await db.execute(select(User).where(User.id == order.user_id))
    u = u_res.scalar_one_or_none()
    pay_res = await db.execute(
        select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
    )
    payments = pay_res.scalars().all()
    return OrderDetailResponse(
        id=order.id,
        pipeline_request_id=order.pipeline_request_id,
        user_id=order.user_id,
        setup_price=order.setup_price,
        monthly_price=order.monthly_price,
        currency=order.currency,
        status=order.status,
        admin_notes=order.admin_notes,
        client_notes=order.client_notes,
        estimated_delivery_at=order.estimated_delivery_at,
        quoted_at=order.quoted_at,
        accepted_at=order.accepted_at,
        delivered_at=order.delivered_at,
        created_at=getattr(order, "created_at", None),
        user_email=u.email if u else None,
        sei_url=pr.sei_url if pr else None,
        institution_name=pr.institution_name if pr else None,
        detected_version=pr.detected_version if pr else None,
        institution_id=pr.institution_id if pr else None,
        payments=[
            PaymentListItem(
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


@router.put("/orders/{order_id}", response_model=OrderDetailResponse)
async def update_admin_order(
    order_id: int,
    data: UpdateOrderSchema,
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update order (prices, notes, ETA)."""
    order_res = await db.execute(select(ScraperOrder).where(ScraperOrder.id == order_id))
    order = order_res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if data.setup_price is not None:
        order.setup_price = Decimal(str(data.setup_price))
    if data.monthly_price is not None:
        order.monthly_price = Decimal(str(data.monthly_price))
    if data.client_notes is not None:
        order.client_notes = data.client_notes
    if data.admin_notes is not None:
        order.admin_notes = data.admin_notes
    if data.estimated_delivery_at is not None:
        order.estimated_delivery_at = data.estimated_delivery_at
    await db.flush()
    return await get_admin_order(order_id, user, db)


@router.post("/orders/{order_id}/confirm-payment")
async def confirm_payment(
    order_id: int,
    data: ConfirmPaymentSchema,
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Confirm payment manually (for manual provider)."""
    order_res = await db.execute(select(ScraperOrder).where(ScraperOrder.id == order_id))
    order = order_res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if data.payment_id:
        pay_res = await db.execute(
            select(Payment).where(Payment.id == data.payment_id, Payment.order_id == order_id)
        )
        payment = pay_res.scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
    else:
        pay_res = await db.execute(
            select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.payment_type == "setup",
                Payment.status == "pending",
            )
            .order_by(Payment.created_at.desc())
        )
        payment = pay_res.scalars().first()
        if not payment:
            raise HTTPException(status_code=404, detail="No pending setup payment found")

    payment.status = "confirmed"
    payment.paid_at = datetime.utcnow()
    payment.payment_method = data.payment_method
    await db.flush()

    pr_res = await db.execute(select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id))
    pr = pr_res.scalar_one_or_none()
    if pr:
        pr.status = PipelineRequestStatus.IN_DEVELOPMENT
    order.status = "setup_paid"
    await db.flush()

    return {"ok": True, "payment_id": payment.id, "message": "Payment confirmed"}


@router.post("/orders/{order_id}/deliver")
async def deliver_order(
    order_id: int,
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark scraper as delivered: create ScraperBinding, activate Institution."""
    order_res = await db.execute(select(ScraperOrder).where(ScraperOrder.id == order_id))
    order = order_res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    pr_res = await db.execute(select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id))
    pr = pr_res.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pipeline request not found")
    if not pr.institution_id:
        raise HTTPException(
            status_code=400,
            detail="Pipeline request has no institution. Create institution first (e.g. when pending_scraper).",
        )

    inst_res = await db.execute(select(Institution).where(Institution.id == pr.institution_id))
    inst = inst_res.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    version = pr.detected_version or "4.2.0"
    binding = InstitutionScraper(
        institution_id=inst.id,
        scraper_version=version,
        active=True,
    )
    db.add(binding)
    inst.is_active = True
    order.delivered_at = datetime.utcnow()
    order.status = "active"
    pr.status = PipelineRequestStatus.READY
    await db.flush()

    if order.monthly_price and order.monthly_price > 0:
        start = datetime.utcnow()
        sub = Subscription(
            order_id=order.id,
            user_id=order.user_id,
            status="active",
            amount=order.monthly_price,
            currency=order.currency,
            interval="monthly",
            current_period_start=start,
            current_period_end=start,
        )
        db.add(sub)
        await db.flush()

    return {"ok": True, "institution_id": inst.id, "message": "Scraper delivered, institution activated"}


# ── Subscriptions ──

@router.get("/subscriptions", response_model=dict)
async def list_admin_subscriptions(
    status: Optional[str] = Query(None),
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List subscriptions (admin)."""
    q = select(Subscription).order_by(Subscription.created_at.desc())
    if status:
        q = q.where(Subscription.status == status)
    res = await db.execute(q)
    subs = res.scalars().all()
    return {
        "subscriptions": [
            SubscriptionListItem(
                id=s.id,
                order_id=s.order_id,
                user_id=s.user_id,
                status=s.status,
                amount=s.amount,
                currency=s.currency,
                interval=s.interval,
                current_period_end=s.current_period_end,
                created_at=getattr(s, "created_at", None),
            ).model_dump()
            for s in subs
        ]
    }


# ── Stats ──

@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    user: UserInfo = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard stats for admin."""
    pipeline_requests_pending = (
        await db.execute(
            select(func.count()).select_from(PipelineRequest).where(
                PipelineRequest.status == PipelineRequestStatus.PENDING_SCRAPER
            )
        )
    ).scalar_one() or 0
    orders_pending_payment = (
        await db.execute(
            select(func.count()).select_from(ScraperOrder).where(
                ScraperOrder.status.in_(["quote_sent", "accepted", "pending_payment"])
            )
        )
    ).scalar_one() or 0
    orders_in_development = (
        await db.execute(
            select(func.count()).select_from(ScraperOrder).where(ScraperOrder.status == "setup_paid")
        )
    ).scalar_one() or 0
    this_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_res = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == "confirmed",
            Payment.paid_at >= this_month_start,
        )
    )
    revenue_this_month = float(revenue_res.scalar_one() or 0)
    active_subscriptions = (
        await db.execute(
            select(func.count()).select_from(Subscription).where(Subscription.status == "active")
        )
    ).scalar_one() or 0
    return AdminStatsResponse(
        pipeline_requests_pending=pipeline_requests_pending,
        orders_pending_payment=orders_pending_payment,
        orders_in_development=orders_in_development,
        revenue_this_month=revenue_this_month,
        active_subscriptions=active_subscriptions,
    )
