# app/api/v1/endpoints/health.py
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health", summary="Простой healthcheck + проверка БД")
def get_health():
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e.__class__.__name__}"
    return {"ok": True, "db": db_status}


# Небольшой алиас — кое-где фронт стучится в /status
@router.get("/status", summary="Короткий статус сервера")
def get_status():
    return {"status": "ok"}
