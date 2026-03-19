import hashlib
import hmac
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user
from app.common.middleware.rate_limiter import limiter
from app.config.database import get_db
from app.config.razorpay_client import get_razorpay_client
from app.config.settings import settings
from app.modules.cart.models import CartItem
from app.modules.order.models import Order, OrderItem
from app.modules.payment.schemas import CreatePaymentOrderRequest, VerifyPaymentRequest
from app.modules.product.models import Product
from app.modules.revenue.commission import settle_commissions
from app.modules.user.models import User

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.post("/create-order")
@limiter.limit("20/15minutes")
async def create_payment_order(
    request: Request,
    body: CreatePaymentOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    client = get_razorpay_client()

    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = result.scalars().all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    razorpay_order = client.order.create(
        {
            "amount": body.amount,
            "currency": "INR",
            "receipt": f"order_{user.id}",
        }
    )

    return {
        "razorpayOrderId": razorpay_order["id"],
        "amount": body.amount,
        "currency": "INR",
        "keyId": settings.RAZORPAY_KEY_ID,
    }


@router.post("/verify")
async def verify_payment(
    body: VerifyPaymentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Verify HMAC signature
    message = f"{body.razorpay_order_id}|{body.razorpay_payment_id}"
    expected_signature = hmac.HMAC(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if expected_signature != body.razorpay_signature:
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # Build order from cart
    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = list(result.scalars().all())
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order = Order(
        user_id=user.id,
        payment_status="PAID",
        razorpay_order_id=body.razorpay_order_id,
        payment_intent_id=body.razorpay_payment_id,
        payment_method="razorpay",
        source_reel_id=uuid.UUID(body.source_reel) if body.source_reel else None,
    )
    db.add(order)
    await db.flush()

    total = 0.0
    for cart_item in cart_items:
        prod_result = await db.execute(select(Product).where(Product.id == cart_item.product_id))
        product = prod_result.scalar_one_or_none()
        if not product or not product.is_active:
            raise HTTPException(
                status_code=400, detail=f"Product {cart_item.product_id} not available"
            )
        if product.stock < cart_item.quantity:
            raise HTTPException(
                status_code=400, detail=f"Insufficient stock for {product.title}"
            )

        price = product.discounted_price or product.price
        item_total = price * cart_item.quantity
        total += item_total

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                seller_id=product.seller_id,
                quantity=cart_item.quantity,
                price=price,
            )
        )

        product.stock -= cart_item.quantity
        product.total_sales += cart_item.quantity

    order.total_amount = round(total, 2)

    # Clear cart
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))

    await db.flush()

    # Commission settlement
    await settle_commissions(db, order)

    return {
        "message": "Payment verified",
        "order": {
            "_id": str(order.id),
            "totalAmount": order.total_amount,
            "paymentStatus": order.payment_status,
        },
    }
