# app/api/v1/endpoints/health.py
from __future__ import annotations

import os
import re
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"])

# Keep the revision of the running process even if its checkout changes later.
_startup_revision = os.getenv("APP_GIT_REVISION", "")
if not re.fullmatch(r"[0-9a-f]{40}", _startup_revision):
    _startup_revision = ""


@router.get(
    "/health",
    summary="Простой healthcheck + проверка БД",
    response_model=dict[str, Any],
)
def get_health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e.__class__.__name__}"
    health = {"ok": True, "db": db_status}
    if _startup_revision:
        health["revision"] = _startup_revision
    return health


# Небольшой алиас — кое-где фронт стучится в /status
@router.get("/status", summary="Короткий статус сервера", response_model=dict[str, Any])
def get_status():
    return {"status": "ok"}
