from __future__ import annotations

import os
import sys
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker as orm_sessionmaker


def _get_db_url_from_env_or_settings() -> str:
    # 1) settings (если есть)
    try:
        from app.core.config import settings  # type: ignore

        url = getattr(settings, "SQLALCHEMY_DATABASE_URI", None) or getattr(
            settings, "DATABASE_URL", None
        )
        if url:
            return str(url)
    except Exception:
        pass

    # 2) env var
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    # 3) fallback
    return "sqlite:///./clinic.db"


def _normalize_sqlite_to_sync(url: str) -> str:
    """
    Если URL асинхронный (sqlite+aiosqlite), приводим к синхронному sqlite:///...
    Ничего не трогаем для других драйверов.
    """
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


# Получаем URL
DATABASE_URL = _get_db_url_from_env_or_settings()
DATABASE_URL = _normalize_sqlite_to_sync(DATABASE_URL)

# небольшая диагностика при импорте (в лог / stderr)
print(f"[app.db.session] Using DATABASE_URL = {DATABASE_URL}", file=sys.stderr)

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
                print(f"[app.db.session] ✅ Foreign keys enabled on connection (verified: {fk_status[0]})", file=sys.stderr)
            else:
                print(f"[app.db.session] ⚠️  WARNING: Foreign keys NOT enabled on connection (status: {fk_status})", file=sys.stderr)
            cursor.close()
        except Exception as e:
            print(f"[app.db.session] ❌ ERROR enabling foreign keys: {e}", file=sys.stderr)
            raise

engine = create_engine(
    DATABASE_URL, 
    future=True, 
    echo=False, 
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# ✅ SECURITY: Register event listener for SQLite FK enforcement
if DATABASE_URL.startswith("sqlite"):
    event.listen(engine, "connect", _enable_sqlite_fk)
    print("[app.db.session] Foreign key enforcement enabled for SQLite via event listener", file=sys.stderr)

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
