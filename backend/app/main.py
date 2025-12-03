# --- BEGIN app/main.py ---
from __future__ import annotations

import logging
import os
from typing import List

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
        "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://localhost:8080,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000,http://127.0.0.1:8080",
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
# Регистрация обработчиков исключений
# -----------------------------------------------------------------------------
from app.core.exception_handlers import register_exception_handlers  # noqa: E402

register_exception_handlers(app)
log.info("Exception handlers registered")

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
    )
except Exception as e:  # pragma: no cover
    log.error("dev-fallback: cannot import deps auth (%s) -> will use dummy token", e)
    _USE_DEV_AUTH_FALLBACK = True

# -----------------------------------------------------------------------------
# Основные API-роутеры проекта
# -----------------------------------------------------------------------------
from app.api.v1.api import api_router as v1_router  # noqa: E402
from app.graphql import graphql_router  # noqa: E402

app.include_router(v1_router, prefix=API_V1_STR)
log.info("Included api.v1.api router at %s", API_V1_STR)

# GraphQL API
app.include_router(graphql_router, prefix="/api")
log.info("Included GraphQL router at /api/graphql")

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
        log.info("Using DEV fallback login for user: %s", form.username)
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
async def _startup_tasks() -> None:
    """Startup event handler - validates security settings and prints routes"""
    # Validate SECRET_KEY on startup
    try:
        from app.core.config import get_settings, _DEFAULT_SECRET_KEY
        
        settings = get_settings()
        env = os.getenv("ENV", "dev").lower()
        
        # Critical security check: fail if default SECRET_KEY in production
        if settings.SECRET_KEY == _DEFAULT_SECRET_KEY and env in ("prod", "production"):
            log.error("=" * 80)
            log.error("CRITICAL SECURITY ERROR: Default SECRET_KEY detected in production!")
            log.error("Set SECRET_KEY environment variable before starting the server.")
            log.error("Generate secure key: python -c 'import secrets; print(secrets.token_urlsafe(32))'")
            log.error("=" * 80)
            raise ValueError(
                "Cannot start in production with default SECRET_KEY. "
                "Set SECRET_KEY environment variable."
            )
        
        # Warn if SECRET_KEY is weak
        if len(settings.SECRET_KEY) < 32:
            log.warning(
                "SECRET_KEY is too short (%d chars). Should be at least 32 characters.",
                len(settings.SECRET_KEY)
            )
        
        log.info("Security validation passed: SECRET_KEY is configured")
        
    except Exception as e:
        log.error("Security validation failed: %s", e)
        if os.getenv("ENV", "dev").lower() in ("prod", "production"):
            raise  # Fail fast in production
        log.warning("Continuing in development mode despite security warning")
    
    # ✅ SECURITY: Start scheduled backups if enabled
    backup_enabled = os.getenv("AUTO_BACKUP_ENABLED", "false").lower() == "true"
    if backup_enabled:
        try:
            from app.services.scheduled_backup import ScheduledBackupService
            from app.db.session import SessionLocal
            
            backup_db = SessionLocal()
            backup_service = ScheduledBackupService(backup_db)
            
            # Get backup time from env (default: 2 AM)
            backup_hour = int(os.getenv("BACKUP_HOUR", "2"))
            backup_minute = int(os.getenv("BACKUP_MINUTE", "0"))
            from datetime import time
            backup_time = time(backup_hour, backup_minute)
            
            await backup_service.start_daily_backups(backup_time)
            log.info(f"✅ Scheduled backups enabled (daily at {backup_time})")
        except Exception as e:
            log.error(f"Failed to start backup scheduler: {e}")
    
    # Print routes
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
