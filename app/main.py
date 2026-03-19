import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.common.middleware.rate_limiter import limiter
from app.config.cloudinary_config import configure_cloudinary
from app.config.database import close_db, create_tables
from app.config.redis import close_redis
from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Creating database tables...")

    # Import all models so SQLAlchemy registers them
    from app.modules.cart import models as _ca  # noqa: F811, F841
    from app.modules.collaboration import models as _co  # noqa: F811, F841
    from app.modules.engagement import models as _e  # noqa: F811, F841
    from app.modules.notification import models as _n  # noqa: F811, F841
    from app.modules.order import models as _o  # noqa: F811, F841
    from app.modules.payout import models as _pa  # noqa: F811, F841
    from app.modules.product import models as _p  # noqa: F811, F841
    from app.modules.reel import models as _r  # noqa: F811, F841
    from app.modules.revenue import models as _re  # noqa: F811, F841
    from app.modules.user import models as _u  # noqa: F811, F841

    await create_tables()
    logger.info("Database tables ready")

    configure_cloudinary()
    logger.info("Cloudinary configured")

    yield

    # Shutdown
    await close_db()
    await close_redis()
    logger.info("Connections closed")


app = FastAPI(
    title="Eena API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Health check
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "env": settings.ENV}


# Register all routers
from app.modules.auth.routes import router as auth_router
from app.modules.cart.routes import router as cart_router
from app.modules.collaboration.routes import router as collab_router
from app.modules.engagement.routes import router as engagement_router
from app.modules.order.routes import router as order_router
from app.modules.payment.routes import router as payment_router
from app.modules.payout.routes import router as payout_router
from app.modules.product.routes import router as product_router
from app.modules.reel.routes import router as reel_router
from app.modules.revenue.routes import router as revenue_router
from app.modules.upload.routes import router as upload_router
from app.modules.user.routes import router as user_router

API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(user_router, prefix=API_PREFIX)
app.include_router(product_router, prefix=API_PREFIX)
app.include_router(reel_router, prefix=API_PREFIX)
app.include_router(engagement_router, prefix=API_PREFIX)
app.include_router(cart_router, prefix=API_PREFIX)
app.include_router(order_router, prefix=API_PREFIX)
app.include_router(collab_router, prefix=API_PREFIX)
app.include_router(payment_router, prefix=API_PREFIX)
app.include_router(revenue_router, prefix=API_PREFIX)
app.include_router(payout_router, prefix=API_PREFIX)
app.include_router(upload_router, prefix=API_PREFIX)
