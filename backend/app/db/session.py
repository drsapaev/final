from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker as orm_sessionmaker

logger = logging.getLogger(__name__)


def _get_db_url_from_env_or_settings() -> str:
    # 1) settings (если есть)
    try:
        from app.core.config import settings  # type: ignore

        url = getattr(settings, "SQLALCHEMY_DATABASE_URI", None) or getattr(
            settings, "DATABASE_URL", None
        )
        if url:
            return str(url)
    except Exception as exc:
        raise RuntimeError("Could not load database settings.") from exc

    # 2) env var
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    raise RuntimeError("DATABASE_URL must be set before creating the database engine.")


def _normalize_sqlite_to_sync(url: str) -> str:
    """
    Если URL асинхронный (sqlite+aiosqlite), приводим к синхронному sqlite:///...
    Ничего не трогаем для других драйверов.
    """
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def _is_sqlite_url(url: str) -> bool:
    return url.lower().startswith(("sqlite://", "sqlite+"))


def _allow_sqlite_database_url() -> bool:
    raw = os.getenv("ALLOW_SQLITE_DATABASE_URL", "")
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def _validate_runtime_database_url(url: str) -> None:
    if _is_sqlite_url(url) and not _allow_sqlite_database_url():
        raise RuntimeError(
            "SQLite DATABASE_URL is disabled for runtime. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for tests or explicit legacy tools."
        )


def _safe_database_url_for_log(url: str) -> str:
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database url>"


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


# Получаем URL
DATABASE_URL = _get_db_url_from_env_or_settings()
_validate_runtime_database_url(DATABASE_URL)
DATABASE_URL = _normalize_sqlite_to_sync(DATABASE_URL)

# небольшая диагностика при импорте
logger.info(
    "Using database URL database_url=%s",
    _safe_database_url_for_log(DATABASE_URL),
)

# Создаём СИНХРОННЫЙ движок
# ✅ SECURITY: Enable foreign key enforcement for SQLite via event listener
def _enable_sqlite_fk(dbapi_conn, connection_record):
    """
    Enable foreign key enforcement for SQLite connections.
    This is called automatically when a new connection is created.
    SQLite requires PRAGMA foreign_keys=ON on EACH connection.
    """
    if DATABASE_URL.startswith("sqlite"):
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # Verify it was set (for debugging)
            cursor.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()
            if fk_status and fk_status[0] == 1:
                logger.info("SQLite foreign keys enabled on connection")
            else:
                logger.warning(
                    "SQLite foreign keys not enabled on connection status=%s",
                    fk_status,
                )
            cursor.close()
        except Exception as exc:
            logger.error(
                "SQLite foreign key setup failed error_type=%s",
                type(exc).__name__,
            )
            raise

_is_sqlite = DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict[str, object] = {
    "future": True,
    "echo": False,
    "pool_pre_ping": True,
}
if not _is_sqlite:
    _engine_kwargs.update(
        {
            "pool_size": _get_int_env("DB_POOL_SIZE", 20),
            "max_overflow": _get_int_env("DB_POOL_OVERFLOW", 40),
            "pool_timeout": _get_int_env("DB_POOL_TIMEOUT", 60),
            "pool_recycle": _get_int_env("DB_POOL_RECYCLE", 1800),
        }
    )

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    **_engine_kwargs,
)

# ✅ SECURITY: Register event listener for SQLite FK enforcement
if _is_sqlite:
    event.listen(engine, "connect", _enable_sqlite_fk)
    logger.info("SQLite foreign key enforcement registered via event listener")

# sync session factory
SessionLocal = orm_sessionmaker(
    bind=engine, autocommit=False, autoflush=False, future=True
)

# Совместимые имена (некоторый внешний код импортирует "sessionmaker" как объект)
sessionmaker = SessionLocal  # type: ignore


def get_db() -> Generator[Session, None, None]:
    """
    Синхронный dependency — отдаёт обычный Session (как ожидают ваши эндпоинты).
    ✅ SECURITY: Foreign key enforcement is enabled via event listener for SQLite.
    Additional PRAGMA execution here ensures FK is enabled even if event listener fails.
    """
    db = SessionLocal()
    try:
        # ✅ SECURITY: Ensure foreign keys are enabled for this connection (SQLite)
        # Event listener should have already enabled it, but we verify/ensure here as well
        if DATABASE_URL.startswith("sqlite"):
            db.execute(text("PRAGMA foreign_keys=ON"))  # ✅ Используем text()
            # Verify FK is enabled (for safety)
            result = db.execute(text("PRAGMA foreign_keys")).scalar()
            if result != 1:
                raise RuntimeError(
                    f"CRITICAL: Foreign key enforcement failed to enable. "
                    f"PRAGMA foreign_keys returned {result} instead of 1. "
                    f"This is a security risk for medical data integrity."
                )
        yield db
    finally:
        db.close()
