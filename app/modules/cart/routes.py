import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user
from app.config.database import get_db
from app.modules.cart.models import CartItem
from app.modules.cart.schemas import AddCartItemRequest, UpdateCartItemRequest
from app.modules.user.models import User

router = APIRouter(prefix="/cart", tags=["Cart"])


def _serialize_cart(items: list[CartItem]) -> list[dict]:
    return [
        {"product": str(item.product_id), "quantity": item.quantity}
        for item in items
    ]


@router.get("/")
async def get_cart(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    items = list(result.scalars().all())
    return {"cart": {"user": str(user.id), "items": _serialize_cart(items)}}


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def add_item(
    body: AddCartItemRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    product_id = uuid.UUID(body.product)

    result = await db.execute(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.quantity += body.quantity
    else:
        db.add(CartItem(user_id=user.id, product_id=product_id, quantity=body.quantity))

    await db.flush()

    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    items = list(result.scalars().all())
    return {"cart": {"user": str(user.id), "items": _serialize_cart(items)}}


@router.patch("/items")
async def update_item(
    body: UpdateCartItemRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    product_id = uuid.UUID(body.product)

    if body.quantity == 0:
        await db.execute(
            delete(CartItem).where(
                CartItem.user_id == user.id, CartItem.product_id == product_id
            )
        )
    else:
        result = await db.execute(
            select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Item not in cart")
        item.quantity = body.quantity

    await db.flush()

    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    items = list(result.scalars().all())
    return {"cart": {"user": str(user.id), "items": _serialize_cart(items)}}


@router.delete("/items/{product_id}")
async def remove_item(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await db.execute(
        delete(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id)
    )
    await db.flush()

    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    items = list(result.scalars().all())
    return {"cart": {"user": str(user.id), "items": _serialize_cart(items)}}


@router.delete("/")
async def clear_cart(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.flush()
    return {"message": "Cart cleared"}
