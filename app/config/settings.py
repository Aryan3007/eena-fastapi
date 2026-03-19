from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Core
    PORT: int = 5000
    ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/eena"
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "change-me-to-a-long-secure-secret-at-least-32-chars"
    JWT_EXPIRES_IN: str = "7d"

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Revenue
    ENABLE_SALE_COMMISSION: bool = True
    ENABLE_AFFILIATE_TRACKING: bool = True
    ENABLE_SPONSORED_REELS: bool = False
    ENABLE_BOOST_ADS: bool = False
    ENABLE_INFLUENCER_SUBSCRIPTION: bool = False
    ENABLE_BRAND_ANALYTICS: bool = False
    PLATFORM_COMMISSION_RATE: float = 0.10
    INFLUENCER_COMMISSION_RATE: float = 0.10
    SPONSORED_PLATFORM_FEE_RATE: float = 0.15
    BOOST_MAX_SCORE: int = 30

    # Admin
    ADMIN_SECRET: str = "changeme_admin_secret"

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_ACCOUNT_NUMBER: str = ""
    RAZORPAY_PAYOUT_MODE: str = "IMPS"
    PAYOUT_DELAY_MS: int = 604800000  # 7 days

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def jwt_expires_seconds(self) -> int:
        val = self.JWT_EXPIRES_IN
        if val.endswith("d"):
            return int(val[:-1]) * 86400
        if val.endswith("h"):
            return int(val[:-1]) * 3600
        return int(val)


settings = Settings()
