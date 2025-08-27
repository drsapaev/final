from __future__ import annotations

import os
import sys
from typing import Generator
from sqlalchemy import create_engine
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
    return "sqlite:///./data.db"


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
engine = create_engine(DATABASE_URL, future=True, echo=False, pool_pre_ping=True)

# sync session factory
SessionLocal = orm_sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Совместимые имена (некоторый внешний код импортирует "sessionmaker" как объект)
sessionmaker = SessionLocal  # type: ignore


def get_db() -> Generator[Session, None, None]:
    """
    Синхронный dependency — отдаёт обычный Session (как ожидают ваши эндпоинты).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
