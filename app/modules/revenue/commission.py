"""Commission settlement service - mirrors Node.js commission.service.ts."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.revenue_config import get_revenue_config
from app.modules.order.models import Order, OrderItem
from app.modules.reel.models import Reel
from app.modules.revenue.models import PlatformRevenue, WalletTransaction
from app.modules.user.models import User

logger = logging.getLogger(__name__)


async def settle_commissions(db: AsyncSession, order: Order) -> None:
    """Non-blocking commission settlement after order creation."""
    try:
        cfg = get_revenue_config()

        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = list(result.scalars().all())

        for item in items:
            item_total = item.price * item.quantity
            platform_commission = 0.0
            influencer_commission = 0.0

            # Platform commission
            if cfg.get("ENABLE_SALE_COMMISSION"):
                rate = cfg.get("PLATFORM_COMMISSION_RATE", 0.10)
                platform_commission = round(item_total * rate, 2)

            # Influencer affiliate commission
            if cfg.get("ENABLE_AFFILIATE_TRACKING") and order.source_reel_id:
                reel_result = await db.execute(
                    select(Reel).where(Reel.id == order.source_reel_id)
                )
                reel = reel_result.scalar_one_or_none()
                if reel:
                    inf_rate = cfg.get("INFLUENCER_COMMISSION_RATE", 0.10)
                    influencer_commission = round(item_total * inf_rate, 2)

                    # Credit influencer wallet
                    inf_result = await db.execute(
                        select(User).where(User.id == reel.creator_id)
                    )
                    influencer = inf_result.scalar_one_or_none()
                    if influencer:
                        influencer.wallet_balance += influencer_commission
                        influencer.wallet_total_earnings += influencer_commission

                        db.add(
                            WalletTransaction(
                                user_id=reel.creator_id,
                                order_id=order.id,
                                reel_id=order.source_reel_id,
                                amount=influencer_commission,
                                type="COMMISSION",
                                description=f"Affiliate commission for order {order.id}",
                            )
                        )

            brand_revenue = round(item_total - platform_commission - influencer_commission, 2)

            # Update order item commissions
            item.platform_commission = platform_commission
            item.influencer_commission = influencer_commission
            item.brand_revenue = brand_revenue

            # Credit brand wallet
            brand_result = await db.execute(select(User).where(User.id == item.seller_id))
            brand = brand_result.scalar_one_or_none()
            if brand:
                brand.wallet_balance += brand_revenue
                brand.wallet_total_earnings += brand_revenue

                db.add(
                    WalletTransaction(
                        user_id=item.seller_id,
                        order_id=order.id,
                        amount=brand_revenue,
                        type="COMMISSION",
                        description=f"Sale revenue for order {order.id}",
                    )
                )

            # Record platform revenue
            if platform_commission > 0:
                db.add(
                    PlatformRevenue(
                        order_id=order.id,
                        source="SALE_COMMISSION",
                        amount=platform_commission,
                    )
                )

        await db.flush()

    except Exception:
        logger.exception("Commission settlement failed for order %s", order.id)
