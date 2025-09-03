# --- BEGIN app/main.py ---
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

# -----------------------------------------------------------------------------
# Логирование
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("clinic.main")

# -----------------------------------------------------------------------------
# Конфиг
# -----------------------------------------------------------------------------
API_V1_STR = os.getenv("API_V1_STR", "/api/v1")

CORS_DISABLE = os.getenv("CORS_DISABLE", "0") == "1"
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]

# -----------------------------------------------------------------------------
# Приложение
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Clinic Manager API",
    version=os.getenv("APP_VERSION", "0.1.0"),
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# -----------------------------------------------------------------------------
# WebSocket роутер (подключаем рано, чтобы точно были /ws/queue)
# -----------------------------------------------------------------------------
from app.ws.queue_ws import router as queue_ws_router, ws_queue  # noqa: E402

app.include_router(queue_ws_router)  # /ws/queue
app.add_api_websocket_route("/ws/dev-queue", ws_queue)

# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
if not CORS_DISABLE:
    cfg = dict(allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    if CORS_ALLOW_ALL:
        app.add_middleware(CORSMiddleware, allow_origins=["*"], **cfg)
    else:
        app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, **cfg)

# -----------------------------------------------------------------------------
# Попытка импортировать реальную аутентификацию.
# Если не получилось — включим dev-fallback ниже.
# -----------------------------------------------------------------------------
_USE_DEV_AUTH_FALLBACK = False
try:
    from app.api.deps import (  # type: ignore  # noqa: E402
        create_access_token,
        get_current_user,
    )
except Exception as e:  # pragma: no cover
    log.error("dev-fallback: cannot import deps auth (%s) -> will use dummy token", e)
    _USE_DEV_AUTH_FALLBACK = True

# -----------------------------------------------------------------------------
# Основные API-роутеры проекта
# -----------------------------------------------------------------------------
from app.api.v1.api import api_router as v1_router  # noqa: E402

app.include_router(v1_router, prefix=API_V1_STR)
log.info("Included api.v1.api router at %s", API_V1_STR)

# -----------------------------------------------------------------------------
# DEV fallback для аутентификации — регистрируем ТОЛЬКО если импорты auth упали
# -----------------------------------------------------------------------------
if _USE_DEV_AUTH_FALLBACK:
    log.warning("Using DEV auth fallback endpoints at %s/auth", API_V1_STR)

    def create_access_token(sub: str) -> str:  # type: ignore[no-redef]
        # простой dev-токен
        return f"dev.{sub}"

    @app.post(f"{API_V1_STR}/auth/login", tags=["auth"], summary="DEV fallback login")
    async def _fallback_login(form: OAuth2PasswordRequestForm = Depends()):
        token = create_access_token(form.username)
        return {"access_token": token, "token_type": "bearer"}

    @app.get(f"{API_V1_STR}/auth/me", tags=["auth"], summary="DEV fallback me")
    async def _fallback_me():
        return {"username": "dev", "role": "Admin", "is_active": True}


# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# Диагностика подключённых маршрутов
# -----------------------------------------------------------------------------
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


# --- END app/main.py ---
