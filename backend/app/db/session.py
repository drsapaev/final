from __future__ import annotations

import os
import sys
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import URL

def _get_db_url_from_env_or_settings() -> str:
    # 1) settings (если есть)
    try:
        from app.core.config import settings  # type: ignore
        url = getattr(settings, "SQLALCHEMY_DATABASE_URI", None) or getattr(settings, "DATABASE_URL", None)
        if url:
            return str(url)
    except Exception:
        pass

    # 2) env var
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    # 3) fallback
    return "sqlite+aiosqlite:///./data.db"

def _ensure_sqlite_uses_aiosqlite(url: str) -> str:
    # если это sqlite и не содержит "+aiosqlite", дополним
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        # преобразуем sqlite:///./path -> sqlite+aiosqlite:///./path
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url

# Получаем URL
DATABASE_URL = _get_db_url_from_env_or_settings()
DATABASE_URL = _ensure_sqlite_uses_aiosqlite(DATABASE_URL)

# небольшая диагностика при импорте (в лог / stderr)
print(f"[app.db.session] Using DATABASE_URL = {DATABASE_URL}", file=sys.stderr)

# Создаём асинхронный движок
engine = create_async_engine(DATABASE_URL, future=True, echo=False, pool_pre_ping=True)

# async session factory
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Совместимые имена
async_session = SessionLocal
sessionmaker = SessionLocal  # type: ignore

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

# для совместимости
get_async_session = get_db
