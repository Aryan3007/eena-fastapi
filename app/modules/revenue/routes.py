from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.admin import verify_admin
from app.config.database import get_db
from app.config.revenue_config import get_revenue_config, patch_revenue_config
from app.modules.revenue.models import PlatformRevenue, WalletTransaction
from app.modules.user.models import User

router = APIRouter(prefix="/admin/revenue", tags=["Revenue Admin"])


@router.get("/config", dependencies=[Depends(verify_admin)])
async def get_config() -> dict:
    return {"config": get_revenue_config()}


@router.patch("/config", dependencies=[Depends(verify_admin)])
async def update_config(body: dict) -> dict:
    updated = patch_revenue_config(body)
    return {"config": updated}


@router.get("/summary", dependencies=[Depends(verify_admin)])
async def revenue_summary(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(PlatformRevenue)
    if from_date:
        query = query.where(PlatformRevenue.created_at >= datetime.fromisoformat(from_date))
    if to_date:
        query = query.where(PlatformRevenue.created_at <= datetime.fromisoformat(to_date))

    result = await db.execute(query)
    revenues = result.scalars().all()

    by_source: dict[str, float] = {}
    total = 0.0
    for rev in revenues:
        by_source[rev.source] = by_source.get(rev.source, 0) + rev.amount
        total += rev.amount

    return {
        "summary": {
            "total": round(total, 2),
            "bySource": by_source,
            "count": len(revenues),
        }
    }


@router.get("/wallets", dependencies=[Depends(verify_admin)])
async def top_wallets(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(User)
        .where(User.wallet_balance > 0)
        .order_by(User.wallet_balance.desc())
        .limit(50)
    )
    users = result.scalars().all()

    return {
        "wallets": [
            {
                "userId": str(u.id),
                "username": u.username,
                "role": u.role,
                "balance": u.wallet_balance,
                "totalEarnings": u.wallet_total_earnings,
            }
            for u in users
        ]
    }


@router.get("/transactions", dependencies=[Depends(verify_admin)])
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offset = (page - 1) * limit
    result = await db.execute(
        select(WalletTransaction)
        .order_by(WalletTransaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    txns = result.scalars().all()

    total_result = await db.execute(select(func.count()).select_from(WalletTransaction))
    total = total_result.scalar() or 0

    return {
        "transactions": [
            {
                "_id": str(t.id),
                "user": str(t.user_id),
                "amount": t.amount,
                "type": t.type,
                "description": t.description,
                "createdAt": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ],
        "total": total,
    }


@router.get("/subscriptions", dependencies=[Depends(verify_admin)])
async def list_subscriptions() -> dict:
    return {"subscriptions": []}
