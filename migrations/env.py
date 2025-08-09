import asyncio
import importlib.util
import pathlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

db_path = pathlib.Path(__file__).resolve().parents[1] / "router" / "core" / "db.py"
spec = importlib.util.spec_from_file_location("core.db", db_path)
if spec is None:
    raise ImportError(f"Could not load spec from {db_path}")
db = importlib.util.module_from_spec(spec)
if db is None:
    raise ImportError(f"Could not load module from {db_path}")
if spec.loader is None:
    raise ImportError(f"Spec loader is None for {db_path}")
spec.loader.exec_module(db)

DATABASE_URL = getattr(db, "DATABASE_URL", "sqlite+aiosqlite:///keys.db")

config = context.config
if config.config_file_name is None:
    raise ValueError("config_file_name is None")
fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
