from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _engine_from_url(url: str):
    connect_args = {}
    if url.startswith("sqlite:"):
        # SQLite в контейнере/локально — разрешаем работу из разных потоков
        connect_args = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)


engine = _engine_from_url(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)