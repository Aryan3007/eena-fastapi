from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.admin import verify_admin
from app.config.database import get_db
from app.modules.payout.models import Payout

router = APIRouter(prefix="/admin/payouts", tags=["Payout Admin"])


@router.get("/", dependencies=[Depends(verify_admin)])
async def list_payouts(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Payout)
    if status:
        query = query.where(Payout.status == status)
    query = query.order_by(Payout.created_at.desc()).limit(50)

    result = await db.execute(query)
    payouts = result.scalars().all()

    return {
        "payouts": [
            {
                "_id": str(p.id),
                "user": str(p.user_id),
                "orderId": str(p.order_id),
                "amount": p.amount,
                "type": p.type,
                "status": p.status,
                "scheduledAt": p.scheduled_at.isoformat() if p.scheduled_at else None,
                "processedAt": p.processed_at.isoformat() if p.processed_at else None,
                "failureReason": p.failure_reason,
            }
            for p in payouts
        ]
    }
