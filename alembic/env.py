import os
import asyncio
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.engine import Connection

from alembic import context

from ironforgedbot.models import Base

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Load environment variables from .env file
load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST", "localhost")

    if db_user and db_pass and db_name:
        database_url = f"mysql+aiomysql://{db_user}:{db_pass}@{db_host}/{db_name}"

if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline():
    """Run migrations in 'offline' mode (generates SQL scripts)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(sync_connection: Connection) -> None:
    """
    This function is called **inside** the greenlet context
    so that `context.run_migrations()` can emit DDL to the DB.
    """
    context.configure(
        connection=sync_connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an AsyncEngine."""
    connectable: AsyncEngine = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as async_conn:
        await async_conn.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
