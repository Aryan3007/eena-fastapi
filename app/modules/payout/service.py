"""Payout processing service - mirrors Node.js payout.service.ts.

Uses arq (async Redis queue) as the BullMQ equivalent.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.razorpay_client import get_razorpay_client
from app.config.settings import settings
from app.modules.payout.models import Payout
from app.modules.revenue.models import WalletTransaction
from app.modules.user.models import User

logger = logging.getLogger(__name__)


async def schedule_payouts(db: AsyncSession, order_id: uuid.UUID, items: list[dict]) -> None:
    """Schedule delayed payouts for each seller/influencer in the order."""
    delay_ms = settings.PAYOUT_DELAY_MS
    scheduled_at = datetime.now(timezone.utc) + timedelta(milliseconds=delay_ms)

    for item in items:
        if item.get("brand_revenue", 0) > 0:
            db.add(
                Payout(
                    user_id=uuid.UUID(item["seller"]),
                    order_id=order_id,
                    amount=item["brand_revenue"],
                    type="BRAND_REVENUE",
                    scheduled_at=scheduled_at,
                )
            )

        if item.get("influencer_commission", 0) > 0 and item.get("influencer_id"):
            db.add(
                Payout(
                    user_id=uuid.UUID(item["influencer_id"]),
                    order_id=order_id,
                    amount=item["influencer_commission"],
                    type="INFLUENCER_COMMISSION",
                    scheduled_at=scheduled_at,
                )
            )

    await db.flush()


async def process_single_payout(db: AsyncSession, payout_id: uuid.UUID) -> None:
    """Process a single payout via Razorpay."""
    result = await db.execute(select(Payout).where(Payout.id == payout_id))
    payout = result.scalar_one_or_none()
    if not payout or payout.status != "PENDING":
        return

    payout.status = "PROCESSING"
    await db.flush()

    try:
        user_result = await db.execute(select(User).where(User.id == payout.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            payout.status = "FAILED"
            payout.failure_reason = "User not found"
            await db.flush()
            return

        bank = user.bank_account
        if not bank or not bank.get("razorpay_fund_account_id"):
            payout.status = "SKIPPED"
            payout.failure_reason = "No bank account configured"
            await db.flush()
            return

        client = get_razorpay_client()
        rz_result = client.payout.create(
            {
                "account_number": settings.RAZORPAY_ACCOUNT_NUMBER,
                "fund_account_id": bank["razorpay_fund_account_id"],
                "amount": int(payout.amount * 100),
                "currency": "INR",
                "mode": settings.RAZORPAY_PAYOUT_MODE,
                "purpose": "payout",
            }
        )

        payout.razorpay_payout_id = rz_result.get("id")
        payout.status = "PAID"
        payout.processed_at = datetime.now(timezone.utc)

        user.wallet_balance -= payout.amount

        db.add(
            WalletTransaction(
                user_id=payout.user_id,
                order_id=payout.order_id,
                amount=-payout.amount,
                type="PAYOUT",
                description=f"Payout processed: {payout.razorpay_payout_id}",
            )
        )
        await db.flush()

    except Exception as exc:
        logger.exception("Payout %s failed", payout_id)
        payout.status = "FAILED"
        payout.failure_reason = str(exc)
        await db.flush()


async def process_pending_payouts(db: AsyncSession) -> int:
    """Process all payouts that are due. Called by the arq worker."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Payout).where(Payout.status == "PENDING", Payout.scheduled_at <= now)
    )
    pending = result.scalars().all()

    processed = 0
    for payout in pending:
        await process_single_payout(db, payout.id)
        processed += 1

    return processed
