import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user
from app.config.database import get_db
from app.config.redis import get_redis
from app.modules.engagement.models import Comment, Follow, Like
from app.modules.engagement.schemas import CreateCommentRequest
from app.modules.reel.models import Reel
from app.modules.user.models import User

router = APIRouter(prefix="/engagement", tags=["Engagement"])


# ── Likes ──


@router.post("/reels/{reel_id}/like")
async def toggle_like(
    reel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.reel_id == reel_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.execute(update(Reel).where(Reel.id == reel_id).values(likes=Reel.likes - 1))
        await db.flush()
        return {"liked": False}

    db.add(Like(user_id=user.id, reel_id=reel_id))
    await db.execute(update(Reel).where(Reel.id == reel_id).values(likes=Reel.likes + 1))
    await db.flush()
    return {"liked": True}


@router.get("/reels/{reel_id}/like")
async def check_like(
    reel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.reel_id == reel_id)
    )
    return {"liked": result.scalar_one_or_none() is not None}


# ── Comments ──


@router.post("/reels/{reel_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    reel_id: uuid.UUID,
    body: CreateCommentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Reel).where(Reel.id == reel_id))
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    comment = Comment(reel_id=reel_id, user_id=user.id, text=body.text)
    db.add(comment)
    await db.execute(update(Reel).where(Reel.id == reel_id).values(comments=Reel.comments + 1))
    await db.flush()

    return {
        "comment": {
            "_id": str(comment.id),
            "reel": str(reel_id),
            "user": str(user.id),
            "text": comment.text,
            "createdAt": comment.created_at.isoformat() if comment.created_at else None,
        }
    }


@router.get("/reels/{reel_id}/comments")
async def list_comments(
    reel_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offset = (page - 1) * limit
    result = await db.execute(
        select(Comment)
        .where(Comment.reel_id == reel_id)
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    comments = result.scalars().all()

    total_result = await db.execute(
        select(func.count()).select_from(Comment).where(Comment.reel_id == reel_id)
    )
    total = total_result.scalar() or 0

    return {
        "comments": [
            {
                "_id": str(c.id),
                "user": str(c.user_id),
                "text": c.text,
                "likesCount": c.likes_count,
                "createdAt": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ],
        "total": total,
    }


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your comment")

    reel_id = comment.reel_id
    await db.delete(comment)
    await db.execute(update(Reel).where(Reel.id == reel_id).values(comments=Reel.comments - 1))
    await db.flush()
    return {"message": "Comment deleted"}


# ── Follows ──


@router.post("/users/{target_user_id}/follow")
async def toggle_follow(
    target_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if user.id == target_user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    result = await db.execute(
        select(Follow).where(Follow.follower_id == user.id, Follow.following_id == target_user_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.execute(
            update(User).where(User.id == user.id).values(following_count=User.following_count - 1)
        )
        await db.execute(
            update(User)
            .where(User.id == target_user_id)
            .values(followers_count=User.followers_count - 1)
        )
        await db.flush()
        return {"following": False}

    db.add(Follow(follower_id=user.id, following_id=target_user_id))
    await db.execute(
        update(User).where(User.id == user.id).values(following_count=User.following_count + 1)
    )
    await db.execute(
        update(User)
        .where(User.id == target_user_id)
        .values(followers_count=User.followers_count + 1)
    )
    await db.flush()
    return {"following": True}


@router.get("/users/{target_user_id}/follow")
async def check_follow(
    target_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Follow).where(Follow.follower_id == user.id, Follow.following_id == target_user_id)
    )
    return {"following": result.scalar_one_or_none() is not None}


# ── Views ──


@router.post("/reels/{reel_id}/view")
async def record_view(
    reel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    redis = await get_redis()
    key = f"view:{user.id}:{reel_id}"

    already_viewed = await redis.get(key)
    if already_viewed:
        return {"counted": False}

    await redis.set(key, "1", ex=7 * 24 * 3600)
    await db.execute(update(Reel).where(Reel.id == reel_id).values(views=Reel.views + 1))
    await db.flush()
    return {"counted": True}
