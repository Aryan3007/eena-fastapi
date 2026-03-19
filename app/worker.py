"""ARQ worker for background jobs (BullMQ equivalent).

Run with: arq app.worker.WorkerSettings
"""

import logging

from arq import cron
from arq.connections import RedisSettings

from app.config.database import async_session
from app.config.settings import settings
from app.modules.payout.service import process_pending_payouts

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    # Import models to register them
    from app.modules.cart import models as _ca  # noqa: F841
    from app.modules.collaboration import models as _co  # noqa: F841
    from app.modules.engagement import models as _e  # noqa: F841
    from app.modules.notification import models as _n  # noqa: F841
    from app.modules.order import models as _o  # noqa: F841
    from app.modules.payout import models as _pa  # noqa: F841
    from app.modules.product import models as _p  # noqa: F841
    from app.modules.reel import models as _r  # noqa: F841
    from app.modules.revenue import models as _re  # noqa: F841
    from app.modules.user import models as _u  # noqa: F841

    logger.info("Worker started")


async def shutdown(ctx: dict) -> None:
    logger.info("Worker shutting down")


async def run_payout_processing(ctx: dict) -> int:
    async with async_session() as db:
        count = await process_pending_payouts(db)
        await db.commit()
    logger.info("Processed %d payouts", count)
    return count


class WorkerSettings:
    functions = [run_payout_processing]
    cron_jobs = [
        cron(run_payout_processing, minute=0, hour=0),  # Run daily at midnight
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
