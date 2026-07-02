from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event, pool, text  # create_engine добавлен

# --- ensure backend root on sys.path (so `import app` works) ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# ----------------------------------------------------------------

# Импорты после настройки sys.path
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: F401, E402

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
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)
    
    # ✅ SECURITY: Enable foreign key enforcement for SQLite in Alembic migrations
    # ✅ FIX: Передаем url как параметр через замыкание, чтобы избежать проблем с областью видимости
    def _make_fk_enabler(database_url: str):
        """Factory function to create FK enabler with captured URL"""
        def _enable_sqlite_fk_for_alembic(dbapi_conn, connection_record):
            """Enable foreign key enforcement for SQLite connections in Alembic"""
            if database_url.startswith("sqlite"):
                try:
                    cursor = dbapi_conn.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    # Verify
                    cursor.execute("PRAGMA foreign_keys")
                    fk_status = cursor.fetchone()
                    if fk_status and fk_status[0] == 1:
                        print("[alembic.env] ✅ Foreign keys enabled for migration connection", file=sys.stderr)
                    else:
                        print(f"[alembic.env] ⚠️  WARNING: Foreign keys NOT enabled (status: {fk_status})", file=sys.stderr)
                    cursor.close()
                except Exception as e:
                    print(f"[alembic.env] ❌ ERROR enabling foreign keys: {e}", file=sys.stderr)
                    raise
        return _enable_sqlite_fk_for_alembic
    
    # Register event listener for FK enforcement
    if url.startswith("sqlite"):
        event.listen(connectable, "connect", _make_fk_enabler(url))

    with connectable.connect() as connection:
        # ✅ SECURITY: Ensure FK is enabled for this migration connection
        if url.startswith("sqlite"):
            connection.execute(text("PRAGMA foreign_keys=ON"))
            # Verify
            fk_status = connection.execute(text("PRAGMA foreign_keys")).scalar()
            if fk_status != 1:
                raise RuntimeError(
                    f"CRITICAL: Foreign key enforcement failed during migration. "
                    f"PRAGMA foreign_keys returned {fk_status} instead of 1. "
                    f"Aborting migration to prevent data corruption."
                )
        
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
