import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user, require_roles
from app.config.database import get_db
from app.modules.product.models import Product
from app.modules.product.schemas import CreateProductRequest, UpdateProductRequest
from app.modules.user.models import User

router = APIRouter(prefix="/products", tags=["Products"])


def _serialize_product(p: Product) -> dict:
    return {
        "_id": str(p.id),
        "seller": str(p.seller_id),
        "title": p.title,
        "description": p.description,
        "price": p.price,
        "discountedPrice": p.discounted_price,
        "category": p.category,
        "images": p.images or [],
        "stock": p.stock,
        "stats": {"totalSales": p.total_sales, "totalRevenue": p.total_revenue},
        "rating": {"average": p.rating_average, "totalReviews": p.rating_total_reviews},
        "isActive": p.is_active,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/")
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Product).where(Product.is_active.is_(True))
    count_query = select(func.count()).select_from(Product).where(Product.is_active.is_(True))

    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    products = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return {
        "products": [_serialize_product(p) for p in products],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product(
    body: CreateProductRequest,
    user: User = Depends(require_roles("BRAND", "INFLUENCER")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    product = Product(
        seller_id=user.id,
        title=body.title,
        description=body.description,
        price=body.price,
        discounted_price=body.discounted_price,
        category=body.category,
        images=body.images,
        stock=body.stock,
    )
    db.add(product)
    await db.flush()
    return {"product": _serialize_product(product)}


@router.get("/mine")
async def get_my_products(
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Product).where(Product.seller_id == user.id, Product.is_active.is_(True))
    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    products = result.scalars().all()

    total_result = await db.execute(
        select(func.count())
        .select_from(Product)
        .where(Product.seller_id == user.id, Product.is_active.is_(True))
    )
    total = total_result.scalar() or 0
    return {"products": [_serialize_product(p) for p in products], "total": total}


@router.get("/by-ids")
async def get_products_by_ids(
    ids: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    id_list = [uuid.UUID(i.strip()) for i in ids.split(",") if i.strip()]
    result = await db.execute(
        select(Product).where(Product.id.in_(id_list), Product.is_active.is_(True))
    )
    products = result.scalars().all()
    return {"products": [_serialize_product(p) for p in products]}


@router.get("/{product_id}")
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product": _serialize_product(product)}


@router.patch("/{product_id}")
async def update_product(
    product_id: uuid.UUID,
    body: UpdateProductRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.seller_id != user.id:
        raise HTTPException(status_code=403, detail="Not your product")

    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(product, key, value)
    await db.flush()
    return {"product": _serialize_product(product)}


@router.delete("/{product_id}")
async def delete_product(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.seller_id != user.id:
        raise HTTPException(status_code=403, detail="Not your product")

    product.is_active = False
    await db.flush()
    return {"message": "Product deleted"}
