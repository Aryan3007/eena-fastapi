"""Feed scoring algorithm - matches Node.js recommendation.service.ts."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.revenue_config import get_revenue_config
from app.modules.engagement.models import Follow, Like
from app.modules.reel.models import Reel


async def score_reels_for_user(
    db: AsyncSession,
    reels: list[Reel],
    user_id: str | None,
    seen_reel_ids: set[str] | None = None,
) -> list[Reel]:
    if not reels:
        return []

    cfg = get_revenue_config()
    now = datetime.now(timezone.utc)
    seen = seen_reel_ids or set()

    following_ids: set[str] = set()
    liked_hashtags: list[str] = []

    if user_id:
        import uuid

        uid = uuid.UUID(user_id)

        # Get who user follows
        result = await db.execute(select(Follow.following_id).where(Follow.follower_id == uid))
        following_ids = {str(row[0]) for row in result.all()}

        # Get hashtags from recently liked reels
        result = await db.execute(
            select(Like.reel_id).where(Like.user_id == uid).order_by(Like.created_at.desc()).limit(50)
        )
        liked_reel_ids = [row[0] for row in result.all()]

        if liked_reel_ids:
            result = await db.execute(
                select(Reel.hashtags).where(Reel.id.in_(liked_reel_ids))
            )
            for (tags,) in result.all():
                if tags:
                    liked_hashtags.extend(tags)

    scored: list[tuple[float, Reel]] = []

    for reel in reels:
        score = 0.0
        reel_id_str = str(reel.id)

        # Already seen penalty
        if reel_id_str in seen:
            score -= 100

        # Followed creator bonus
        if str(reel.creator_id) in following_ids:
            score += 50

        # Hashtag affinity
        if reel.hashtags:
            for tag in reel.hashtags:
                if tag in liked_hashtags:
                    score += 10

        # Watch time bonus
        if reel.watch_time > 10:
            score += 10

        # Like ratio bonus
        if reel.views > 0:
            like_ratio = reel.likes / reel.views
            if like_ratio > 0.05:
                score += 8

        # Recency decay (max +15, decays over 7 days)
        created = reel.created_at.replace(tzinfo=timezone.utc) if reel.created_at.tzinfo is None else reel.created_at
        age_hours = (now - created).total_seconds() / 3600
        decay = max(0, 15 * (1 - age_hours / 168))
        score += decay

        # Viral boost
        if reel.views > 500:
            score += 5

        # Boost ads
        if cfg.get("ENABLE_BOOST_ADS") and reel.boost_is_active:
            if not reel.boost_expires_at or reel.boost_expires_at.replace(tzinfo=timezone.utc) > now:
                score += reel.boost_score

        # Small random factor
        score += (hash(reel_id_str) % 100) / 100.0

        scored.append((score, reel))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [reel for _, reel in scored]
