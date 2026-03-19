from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user
from app.common.middleware.rate_limiter import limiter
from app.common.utils.jwt import create_token
from app.common.utils.password import hash_password, verify_password
from app.config.database import get_db
from app.modules.auth.schemas import GoogleAuthRequest, LoginRequest, RegisterRequest
from app.modules.user.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


def _user_response(user: User, token: str) -> dict:
    return {
        "token": token,
        "user": {
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
            "isVerified": user.is_verified,
        },
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/15minutes")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User).where(or_(User.email == body.email, User.username == body.username))
    )
    existing = result.scalar_one_or_none()
    if existing:
        field = "email" if existing.email == body.email else "username"
        raise HTTPException(status_code=409, detail=f"{field} already exists")

    user = User(
        username=body.username,
        email=body.email,
        password=hash_password(body.password),
        profile_name=body.name,
    )
    db.add(user)
    await db.flush()

    token = create_token(str(user.id))
    return _user_response(user, token)


@router.post("/login")
@limiter.limit("10/15minutes")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(str(user.id))
    return _user_response(user, token)


@router.post("/google")
@limiter.limit("10/15minutes")
async def google_auth(
    request: Request,
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    from app.config.settings import settings

    try:
        payload = id_token.verify_oauth2_token(
            body.id_token, GoogleRequest(), settings.GOOGLE_CLIENT_ID
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = payload.get("email", "")
    name = payload.get("name", "")
    google_id = payload.get("sub", "")
    avatar = payload.get("picture")

    result = await db.execute(
        select(User).where(or_(User.google_id == google_id, User.email == email))
    )
    user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id = google_id
            if avatar and not user.profile_avatar:
                user.profile_avatar = avatar
            await db.flush()
    else:
        username = email.split("@")[0]
        base = username
        counter = 1
        while True:
            res = await db.execute(select(User).where(User.username == username))
            if not res.scalar_one_or_none():
                break
            username = f"{base}{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            google_id=google_id,
            profile_name=name,
            profile_avatar=avatar,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

    token = create_token(str(user.id))
    return _user_response(user, token)


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    return {
        "user": {
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
            "wallet": {
                "balance": user.wallet_balance,
                "totalEarnings": user.wallet_total_earnings,
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
    }
