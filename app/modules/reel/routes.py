import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user, get_optional_user
from app.config.database import get_db
from app.modules.collaboration.models import Collaboration
from app.modules.reel.models import Reel
from app.modules.reel.recommendation import score_reels_for_user
from app.modules.reel.schemas import CreateReelRequest
from app.modules.user.models import User

router = APIRouter(prefix="/reels", tags=["Reels"])


def _serialize_reel(r: Reel) -> dict:
    return {
        "_id": str(r.id),
        "creator": str(r.creator_id),
        "videoUrl": r.video_url,
        "thumbnailUrl": r.thumbnail_url,
        "caption": r.caption,
        "hashtags": r.hashtags or [],
        "taggedProducts": r.tagged_products or [],
        "metrics": {
            "views": r.views,
            "likes": r.likes,
            "comments": r.comments,
            "shares": r.shares,
            "watchTime": r.watch_time,
        },
        "boost": {
            "isActive": r.boost_is_active,
            "score": r.boost_score,
            "expiresAt": r.boost_expires_at.isoformat() if r.boost_expires_at else None,
        },
        "isSponsored": r.is_sponsored,
        "sponsorBrand": str(r.sponsor_brand_id) if r.sponsor_brand_id else None,
        "status": r.status,
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/")
async def list_reels(
    cursor: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Reel).where(Reel.status == "ACTIVE")
    if cursor:
        # Cursor-based pagination: get reels created before cursor reel
        cursor_result = await db.execute(select(Reel.created_at).where(Reel.id == cursor))
        cursor_time = cursor_result.scalar_one_or_none()
        if cursor_time:
            query = query.where(Reel.created_at < cursor_time)

    query = query.order_by(Reel.created_at.desc()).limit(limit)
    result = await db.execute(query)
    reels = list(result.scalars().all())

    next_cursor = str(reels[-1].id) if reels else None
    return {
        "reels": [_serialize_reel(r) for r in reels],
        "nextCursor": next_cursor,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_reel(
    body: CreateReelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tagged = [{"product": tp.product, "x": tp.x, "y": tp.y} for tp in body.tagged_products]

    reel = Reel(
        creator_id=user.id,
        video_url=body.video_url,
        thumbnail_url=body.thumbnail_url,
        caption=body.caption,
        hashtags=body.hashtags,
        tagged_products=tagged,
        is_sponsored=body.is_sponsored,
        sponsor_brand_id=uuid.UUID(body.sponsor_brand) if body.sponsor_brand else None,
        sponsored_campaign_id=uuid.UUID(body.sponsored_campaign_id)
        if body.sponsored_campaign_id
        else None,
        status="ACTIVE",
    )
    db.add(reel)

    # Auto-promote USER to INFLUENCER
    if user.role == "USER":
        user.role = "INFLUENCER"

    user.reels_count += 1
    await db.flush()

    return {"reel": _serialize_reel(reel)}


@router.get("/feed")
async def personalized_feed(
    cursor: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=30),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Reel).where(Reel.status == "ACTIVE")
    if cursor:
        cursor_result = await db.execute(select(Reel.created_at).where(Reel.id == cursor))
        cursor_time = cursor_result.scalar_one_or_none()
        if cursor_time:
            query = query.where(Reel.created_at < cursor_time)

    query = query.order_by(Reel.created_at.desc()).limit(limit * 3)
    result = await db.execute(query)
    reels = list(result.scalars().all())

    user_id = str(user.id) if user else None
    scored = await score_reels_for_user(db, reels, user_id)
    result_reels = scored[:limit]

    next_cursor = str(result_reels[-1].id) if result_reels else None
    return {
        "reels": [_serialize_reel(r) for r in result_reels],
        "nextCursor": next_cursor,
    }


@router.get("/mine")
async def my_reels(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Reel).where(Reel.creator_id == user.id).order_by(Reel.created_at.desc())
    )
    reels = result.scalars().all()
    return {"reels": [_serialize_reel(r) for r in reels]}


@router.get("/stats")
async def reel_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(
            func.count(Reel.id),
            func.coalesce(func.sum(Reel.views), 0),
            func.coalesce(func.sum(Reel.likes), 0),
            func.coalesce(func.sum(Reel.comments), 0),
        ).where(Reel.creator_id == user.id)
    )
    row = result.one()
    return {
        "stats": {
            "totalReels": row[0],
            "totalViews": row[1],
            "totalLikes": row[2],
            "totalComments": row[3],
        }
    }


@router.get("/collaborations")
async def my_collaborations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Collaboration).where(
            Collaboration.influencer_id == user.id, Collaboration.status == "ACCEPTED"
        )
    )
    collabs = result.scalars().all()
    return {
        "collaborations": [
            {
                "_id": str(c.id),
                "brand": str(c.brand_id),
                "campaignTitle": c.campaign_title,
                "product": str(c.product_id),
                "commissionPercentage": c.commission_percentage,
                "status": c.status,
            }
            for c in collabs
        ]
    }


@router.get("/user/{user_id}")
async def reels_by_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Reel)
        .where(Reel.creator_id == user_id, Reel.status == "ACTIVE")
        .order_by(Reel.created_at.desc())
    )
    reels = result.scalars().all()
    return {"reels": [_serialize_reel(r) for r in reels]}


@router.delete("/{reel_id}")
async def delete_reel(
    reel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Reel).where(Reel.id == reel_id))
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")
    if reel.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not your reel")

    await db.delete(reel)
    user.reels_count = max(0, user.reels_count - 1)
    await db.flush()
    return {"message": "Reel deleted"}
