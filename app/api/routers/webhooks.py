"""
Webhooks Router - Incoming webhooks from payment gateways.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.payment import Payment
from app.database.models.pipeline_request import PipelineRequest
from app.database.models.scraper_order import ScraperOrder
from app.database.session import get_db
from app.payments import get_payment_provider
from app.utils.enums import PipelineRequestStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/payment/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive webhook from payment provider (e.g. stripe, mercadopago)."""
    body = await request.body()
    headers = dict(request.headers) if request.headers else None
    pay_provider = get_payment_provider()
    if pay_provider.get_name() != provider and provider != "manual":
        logger.warning(f"Webhook provider mismatch: path={provider}, configured={pay_provider.get_name()}")
    event = pay_provider.handle_webhook(body, headers)
    if event is None:
        return {"received": True}
    if event.event_type == "payment.confirmed":
        result = await db.execute(select(Payment).where(Payment.external_id == event.external_id))
        payment = result.scalar_one_or_none()
        if payment:
            if payment.status != "confirmed":
                payment.status = "confirmed"
                payment.paid_at = datetime.utcnow()
                await db.flush()
                order_result = await db.execute(select(ScraperOrder).where(ScraperOrder.id == payment.order_id))
                order = order_result.scalar_one_or_none()
                if order and order.status == "pending_payment" and payment.payment_type == "setup":
                    order.status = "setup_paid"
                    pr_result = await db.execute(
                        select(PipelineRequest).where(PipelineRequest.id == order.pipeline_request_id)
                    )
                    pr = pr_result.scalar_one_or_none()
                    if pr:
                        pr.status = PipelineRequestStatus.IN_DEVELOPMENT
                    await db.flush()
            return {"received": True, "payment_id": payment.id}
    return {"received": True}
