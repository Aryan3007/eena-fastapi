import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config.database import Base
from app.config.settings import settings

# Import all models so metadata is populated
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

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
