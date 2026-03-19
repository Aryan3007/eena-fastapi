import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user, require_roles
from app.config.database import get_db
from app.modules.cart.models import CartItem
from app.modules.order.models import Order, OrderItem
from app.modules.order.schemas import CreateOrderRequest, UpdateOrderStatusRequest
from app.modules.product.models import Product
from app.modules.revenue.commission import settle_commissions
from app.modules.user.models import User

router = APIRouter(prefix="/orders", tags=["Orders"])


async def _serialize_order(db: AsyncSession, o: Order) -> dict:
    result = await db.execute(select(OrderItem).where(OrderItem.order_id == o.id))
    items = result.scalars().all()
    return {
        "_id": str(o.id),
        "user": str(o.user_id),
        "items": [
            {
                "product": str(item.product_id),
                "seller": str(item.seller_id),
                "quantity": item.quantity,
                "price": item.price,
                "platformCommission": item.platform_commission,
                "influencerCommission": item.influencer_commission,
                "brandRevenue": item.brand_revenue,
            }
            for item in items
        ],
        "totalAmount": o.total_amount,
        "paymentStatus": o.payment_status,
        "orderStatus": o.order_status,
        "sourceReel": str(o.source_reel_id) if o.source_reel_id else None,
        "createdAt": o.created_at.isoformat() if o.created_at else None,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order(
    body: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = list(result.scalars().all())
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order = Order(
        user_id=user.id,
        payment_status="PAID",
        source_reel_id=uuid.UUID(body.source_reel) if body.source_reel else None,
    )
    db.add(order)
    await db.flush()  # Get order.id

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

        # Reduce stock
        product.stock -= cart_item.quantity
        product.total_sales += cart_item.quantity

    order.total_amount = round(total, 2)

    # Clear cart
    for ci in cart_items:
        await db.delete(ci)

    await db.flush()

    # Settle commissions
    await settle_commissions(db, order)

    return {"order": await _serialize_order(db, order)}


@router.get("/")
async def list_orders(
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offset = (page - 1) * limit
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    orders = result.scalars().all()

    total_result = await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user.id)
    )
    total = total_result.scalar() or 0

    return {
        "orders": [await _serialize_order(db, o) for o in orders],
        "total": total,
    }


@router.get("/brand")
async def brand_orders(
    user: User = Depends(require_roles("BRAND")),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offset = (page - 1) * limit
    # Find orders that contain items sold by this brand
    order_ids_query = select(OrderItem.order_id).where(OrderItem.seller_id == user.id).distinct()
    result = await db.execute(
        select(Order)
        .where(Order.id.in_(order_ids_query))
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    orders = result.scalars().all()

    total_result = await db.execute(
        select(func.count()).select_from(Order).where(Order.id.in_(order_ids_query))
    )
    total = total_result.scalar() or 0

    return {
        "orders": [await _serialize_order(db, o) for o in orders],
        "total": total,
    }


@router.get("/{order_id}")
async def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != user.id:
        # Allow brand to view orders with their products
        item_result = await db.execute(
            select(OrderItem.seller_id).where(OrderItem.order_id == order_id).distinct()
        )
        seller_ids = {row[0] for row in item_result.all()}
        if user.id not in seller_ids:
            raise HTTPException(status_code=403, detail="Not authorized")
    return {"order": await _serialize_order(db, order)}


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: uuid.UUID,
    body: UpdateOrderStatusRequest,
    user: User = Depends(require_roles("BRAND")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.status not in ("SHIPPED", "DELIVERED"):
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    item_result = await db.execute(
        select(OrderItem.seller_id).where(OrderItem.order_id == order_id).distinct()
    )
    seller_ids = {row[0] for row in item_result.all()}
    if user.id not in seller_ids:
        raise HTTPException(status_code=403, detail="Not your order")

    order.order_status = body.status
    await db.flush()
    return {"order": await _serialize_order(db, order)}
