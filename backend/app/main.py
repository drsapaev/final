from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("clinic.main")

API_V1_STR = os.getenv("API_V1_STR", "/api/v1")

app = FastAPI(
    title="Clinic Manager API",
    version=os.getenv("APP_VERSION", "0.9.0"),
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- WS подключаем рано, чтобы гарантированно были /ws/*
from app.ws.queue_ws import router as queue_ws_router, ws_queue  # noqa: E402

app.include_router(queue_ws_router)         # /ws/queue
app.add_api_websocket_route("/ws/dev-queue", ws_queue)

# --- CORS
CORS_DISABLE = os.getenv("CORS_DISABLE", "0") == "1"
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
if not CORS_DISABLE:
    cfg = dict(allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    if CORS_ALLOW_ALL:
        app.add_middleware(CORSMiddleware, allow_origins=["*"], **cfg)
    else:
        app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, **cfg)


# --- Fallback JWT login, который ВСЕГДА даёт корректный JWT из ENV
def _make_jwt(sub: str) -> str:
    from jose import jwt

    secret = os.getenv("JWT_SECRET", "dev-secret")
    alg = os.getenv("JWT_ALG", "HS256")
    ttl = int(os.getenv("JWT_TTL", "7200"))
    exp = datetime.utcnow() + timedelta(seconds=ttl)
    payload = {"sub": sub, "exp": exp}
    return jwt.encode(payload, secret, algorithm=alg)


@app.post(f"{API_V1_STR}/auth/login", tags=["auth"], summary="DEV fallback login (JWT via ENV)")
async def _fallback_login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Простая точка входа на случай, если «родной» /auth/login не поднимется.
    Возвращает настоящий JWT, совместимый с get_current_user (секрет из ENV).
    """
    token = _make_jwt(form.username)
    return {"access_token": token, "token_type": "bearer"}


@app.get(f"{API_V1_STR}/auth/me", tags=["auth"], summary="DEV fallback me")
async def _fallback_me():
    # лёгкая заглушка; когда «родной» auth подключится — он переопределит свои пути ниже
    return {"username": "dev", "role": "Admin", "is_active": True}


# --- Подключаем основные роутеры проекта
try:
    from app.api.v1.api import api_router as v1_router  # noqa: E402

    app.include_router(v1_router, prefix=API_V1_STR)
    log.info("Included api.v1.api router at %s", API_V1_STR)
except Exception as e:
    log.error("Failed to include api.v1.api: %s", e)

# Пытаемся также смонтировать «родной» auth, если он есть
try:
    from app.api.v1.endpoints import auth as auth_ep  # noqa: E402

    app.include_router(auth_ep.router, prefix=f"{API_V1_STR}/auth", tags=["auth"])
    app.include_router(auth_ep.router, prefix="/auth", tags=["auth"])  # запасной префикс
    log.info("Included AUTH router at %s/auth and /auth", API_V1_STR)
except Exception as e:
    log.warning("WARN: failed to include AUTH router (%s).", e)


# --- Health & диагностика
@app.get("/")
def root():
    return {
        "status": "ok",
        "name": "Clinic Queue Manager",
        "version": os.getenv("APP_VERSION", "0.9.0"),
        "api_v1": API_V1_STR,
        "env": os.getenv("APP_ENV", "dev"),
        "docs": "/docs",
        "openapi": "/openapi.json",
        "cors_disabled": CORS_DISABLE,
        "cors_allow_all": CORS_ALLOW_ALL,
        "origins": CORS_ORIGINS,
    }


@app.on_event("startup")
async def _print_routes() -> None:
    try:
        lines: List[str] = []
        for r in app.router.routes:
            path = getattr(r, "path", "")
            methods = ",".join(sorted(getattr(r, "methods", []) or []))
            name = getattr(r, "name", "")
            lines.append(f"{methods:20s}  {path:40s}  {name}")
        log.info("Mounted routes:\n%s", "\n".join(lines))
        log.info(
            "Flags: WS_DEV_ALLOW=%s CORS_DISABLE=%s",
            os.getenv("WS_DEV_ALLOW"),
            os.getenv("CORS_DISABLE"),
        )
    except Exception:
        pass


@app.get("/_routes")
def _routes():
    items = []
    for r in app.router.routes:
        items.append(
            {
                "type": r.__class__.__name__,
                "path": getattr(r, "path", ""),
                "methods": list(getattr(r, "methods", []) or []),
                "name": getattr(r, "name", ""),
            }
        )
    return items
