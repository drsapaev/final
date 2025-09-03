from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool  # create_engine добавлен

# --- ensure backend root on sys.path (so `import app` works) ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# ----------------------------------------------------------------

from app.core.config import settings  # our central Settings

# Now imports from our project work:
from app.db.base import Base  # noqa: F401

# this is the Alembic Config object, which provides access to the values
# within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def get_url() -> str:
    """Get SQLAlchemy URL from our settings or fall back to alembic.ini."""
    url = os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", None)
    if not url:
        url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set and sqlalchemy.url is missing in alembic.ini"
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode'."""
    # FIX: создаём engine напрямую, чтобы не споткнуться о ключ 'url'
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
