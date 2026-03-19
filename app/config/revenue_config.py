from app.config.settings import settings

# Mutable runtime config (hot-patchable via admin endpoint)
_revenue_config: dict = {}


def get_revenue_config() -> dict:
    if not _revenue_config:
        reset_revenue_config()
    return _revenue_config


def reset_revenue_config() -> None:
    _revenue_config.clear()
    _revenue_config.update(
        {
            "ENABLE_SALE_COMMISSION": settings.ENABLE_SALE_COMMISSION,
            "ENABLE_AFFILIATE_TRACKING": settings.ENABLE_AFFILIATE_TRACKING,
            "ENABLE_SPONSORED_REELS": settings.ENABLE_SPONSORED_REELS,
            "ENABLE_BOOST_ADS": settings.ENABLE_BOOST_ADS,
            "ENABLE_INFLUENCER_SUBSCRIPTION": settings.ENABLE_INFLUENCER_SUBSCRIPTION,
            "ENABLE_BRAND_ANALYTICS": settings.ENABLE_BRAND_ANALYTICS,
            "PLATFORM_COMMISSION_RATE": settings.PLATFORM_COMMISSION_RATE,
            "INFLUENCER_COMMISSION_RATE": settings.INFLUENCER_COMMISSION_RATE,
            "SPONSORED_PLATFORM_FEE_RATE": settings.SPONSORED_PLATFORM_FEE_RATE,
            "BOOST_MAX_SCORE": settings.BOOST_MAX_SCORE,
        }
    )


def patch_revenue_config(updates: dict) -> dict:
    cfg = get_revenue_config()
    for key, value in updates.items():
        if key in cfg:
            cfg[key] = value
    return cfg
