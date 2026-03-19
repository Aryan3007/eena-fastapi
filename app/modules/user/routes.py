import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user
from app.config.database import get_db
from app.modules.user.models import User
from app.modules.user.schemas import CreateStoreRequest, UpdateProfileRequest

router = APIRouter(prefix="/users", tags=["Users"])


def _serialize_user(user: User) -> dict:
    return {
        "_id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "profile": {
            "name": user.profile_name,
            "avatar": user.profile_avatar,
            "bio": user.profile_bio,
            "website": user.profile_website,
        },
        "stats": {
            "followersCount": user.followers_count,
            "followingCount": user.following_count,
            "reelsCount": user.reels_count,
        },
        "store": {
            "storeName": user.store_name,
            "storeDescription": user.store_description,
            "storeLogo": user.store_logo,
        }
        if user.store_name
        else None,
        "isVerified": user.is_verified,
    }


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    return {"user": _serialize_user(user)}


@router.patch("/me")
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.name is not None:
        user.profile_name = body.name
    if body.bio is not None:
        user.profile_bio = body.bio
    if body.avatar is not None:
        user.profile_avatar = body.avatar
    if body.website is not None:
        user.profile_website = body.website
    await db.flush()
    return {"user": _serialize_user(user)}


@router.post("/store", status_code=status.HTTP_201_CREATED)
async def create_store(
    body: CreateStoreRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if user.role == "BRAND":
        raise HTTPException(status_code=400, detail="Already a brand")

    user.role = "BRAND"
    user.store_name = body.store_name
    user.store_description = body.store_description
    user.store_logo = body.store_logo
    await db.flush()
    return {"user": _serialize_user(user)}


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pattern = f"%{q}%"
    result = await db.execute(
        select(User)
        .where(
            User.is_active.is_(True),
            or_(
                User.username.ilike(pattern),
                User.profile_name.ilike(pattern),
            ),
        )
        .limit(20)
    )
    users = result.scalars().all()

    return {
        "users": [
            {
                "_id": str(u.id),
                "username": u.username,
                "profile": {
                    "name": u.profile_name,
                    "avatar": u.profile_avatar,
                    "bio": u.profile_bio,
                    "website": u.profile_website,
                },
                "role": u.role,
            }
            for u in users
        ]
    }


@router.get("/{username}")
async def get_user_by_username(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User).where(User.username == username, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": _serialize_user(user)}
