# --- BEGIN app/main.py ---
from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.prometheus import init_prometheus
from app.core.sentry import init_sentry as init_backend_sentry

# -----------------------------------------------------------------------------
# Логирование
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Конфиг
# -----------------------------------------------------------------------------
settings = get_settings()
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
setup_logging(level=log_level, structured=settings.LOG_STRUCTURED)

# Sentry — no-op if SENTRY_DSN env var is unset.
# Requires sentry-sdk (in backend/requirements-monitoring.txt).
init_backend_sentry()

log = logging.getLogger("clinic.main")
API_V1_STR = os.getenv("API_V1_STR", "/api/v1")

# Use settings for CORS configuration
CORS_DISABLE = settings.CORS_DISABLE
CORS_ALLOW_ALL = settings.CORS_ALLOW_ALL
ENV = os.getenv("ENV", "dev").lower()
IS_PROD = ENV in ("prod", "production")
TESTING = os.getenv("TESTING", "0").lower() in ("1", "true", "yes")


def _detect_local_lan_ip() -> str | None:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0)
        try:
            probe.connect(("8.8.8.8", 80))
            local_ip = probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            return None

    try:
        parsed_ip = ipaddress.ip_address(local_ip)
    except ValueError:
        return None
    if parsed_ip.is_loopback or parsed_ip.is_unspecified:
        return None
    return local_ip


def _is_local_cors_host(hostname: str | None) -> bool:
    host = str(hostname or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _with_dev_lan_cors_origins(origins: list[str]) -> list[str]:
    if IS_PROD:
        return origins

    local_ip = _detect_local_lan_ip()
    if not local_ip:
        return origins

    updated_origins = list(dict.fromkeys(origins))
    ports: set[int] = set()
    for origin in origins:
        parsed = urlsplit(str(origin or "").strip())
        if parsed.scheme != "http" or not _is_local_cors_host(parsed.hostname):
            continue
        try:
            ports.add(parsed.port or 80)
        except ValueError:
            continue

    for port in ports or {5173}:
        local_origin = urlunsplit(("http", f"{local_ip}:{port}", "", "", ""))
        if local_origin not in updated_origins:
            updated_origins.append(local_origin)
    return updated_origins


CORS_ORIGINS = _with_dev_lan_cors_origins(settings.BACKEND_CORS_ORIGINS)

# Fail fast on insecure CORS in production
if IS_PROD and (CORS_DISABLE or CORS_ALLOW_ALL):
    raise ValueError(
        "Refusing to start in production: CORS_DISABLE or CORS_ALLOW_ALL is enabled. "
        "Set BACKEND_CORS_ORIGINS to a strict whitelist."
    )

# PR-30 / High-10: The previous DEV auth fallback has been removed entirely.
# Previously: a non-prod env could register dummy /auth/login and /auth/me
# endpoints returning dev tokens. Now: auth imports must succeed in every
# environment; failures raise RuntimeError unconditionally (handled below).


# -----------------------------------------------------------------------------
# Lifespan Context Manager (replaces deprecated on_event)
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # === STARTUP ===
    await _startup_tasks()

    yield  # Application is running

    # === SHUTDOWN ===
    # Add any cleanup code here if needed
    log.info("Application shutdown complete")


# -----------------------------------------------------------------------------
# Приложение
# -----------------------------------------------------------------------------
app = FastAPI(
    title="MediClinic Pro API",
    description="""
    Medical clinic management system API.

    ## Authentication
    All endpoints (except /auth/login, /auth/csrf-token, /health) require
    a Bearer JWT token in the Authorization header.

    ## Rate Limiting
    Sensitive endpoints (login, SMS, broadcast) are rate-limited via slowapi.
    Rate limit headers are included in responses.

    ## Audit Logging
    Admin actions are logged to the AuditLog table for HIPAA compliance.

    ## WebSocket
    Real-time endpoints available at /ws/notifications, /ws/queue, /ws/cashier.
    Authentication via ?token= query parameter (JWT).
    """,
    version=settings.APP_VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Authentication and authorization"},
        {"name": "payments", "description": "Payment processing (Click, PayMe, Kaspi)"},
        {"name": "payment-webhooks", "description": "Payment provider webhooks"},
        {"name": "EMR v2", "description": "Electronic medical records (v2)"},
        {"name": "ai", "description": "AI-powered medical assistance"},
        {"name": "two-factor-auth", "description": "Two-factor authentication"},
        {"name": "telegram", "description": "Telegram bot integration"},
        {"name": "qr-queue", "description": "Queue management with QR codes"},
        {"name": "lab", "description": "Laboratory results and reporting"},
        {"name": "mcp", "description": "Model Context Protocol tools"},
    ],
)

# Prometheus metrics — no-op if prometheus-client not installed.
# Mounts /metrics endpoint + adds HTTP request tracking middleware.
# Disable via ENABLE_PROMETHEUS=0 env var.
init_prometheus(app)

# -----------------------------------------------------------------------------
# Регистрация обработчиков исключений
# -----------------------------------------------------------------------------
from app.core.exception_handlers import register_exception_handlers  # noqa: E402

register_exception_handlers(app)
log.info("Exception handlers registered")

# -----------------------------------------------------------------------------
# F-005: SlowAPI rate limiter registration
# -----------------------------------------------------------------------------
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address as _get_remote_address

    _app_limiter = Limiter(key_func=_get_remote_address)
    app.state.limiter = _app_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    log.info("SlowAPI rate limiter registered")
except ImportError:
    log.warning("slowapi not installed, REST rate limiting disabled (install with: pip install slowapi)")


# -----------------------------------------------------------------------------
# WebSocket роутер (подключаем рано, чтобы точно были /ws/queue)
# -----------------------------------------------------------------------------
from app.ws.chat_ws import chat_websocket_handler  # noqa: E402
from app.ws.queue_ws import router as queue_ws_router  # noqa: E402
from app.ws.queue_ws import ws_queue  # noqa: E402

app.include_router(queue_ws_router)  # /ws/queue
app.add_api_websocket_route("/ws/dev-queue", ws_queue)
app.add_api_websocket_route("/ws/chat", chat_websocket_handler)  # User-to-user chat

# -----------------------------------------------------------------------------

# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """FRONTEND-SECURITY: Add security headers to all responses."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # CSP: allow inline styles (Tailwind), scripts from self, images from data: and https:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
log.info("Security headers middleware registered")

# Audit Middleware (должен быть ДО CORS для установки request_id)
# -----------------------------------------------------------------------------
from app.core.rate_limiter import setup_rate_limiting
from app.middleware.audit_middleware import AuditMiddleware  # noqa: E402

app.add_middleware(AuditMiddleware)
log.info("Audit middleware registered")

# Rate limiting
setup_rate_limiting(app)
log.info("Rate limiting middleware registered")

# -----------------------------------------------------------------------------
# Security Middleware (rate limiting, brute force protection, IP logging)
# -----------------------------------------------------------------------------
from app.middleware.security_middleware import SecurityMiddleware  # noqa: E402
from app.middleware.tenant_scope_middleware import TenantScopeMiddleware  # noqa: E402

if TESTING:
    log.info("Security middleware skipped in testing mode (TESTING=1)")
else:
    app.add_middleware(SecurityMiddleware)
    log.info("Security middleware registered")

# -----------------------------------------------------------------------------
# Tenant Scope Middleware (feature-flagged, multi-clinic rollout)
# -----------------------------------------------------------------------------
app.add_middleware(TenantScopeMiddleware)
log.info("Tenant scope middleware registered")

# -----------------------------------------------------------------------------
# Observability Middleware (SLIs, trace-id, structured request logs)
# -----------------------------------------------------------------------------
from app.middleware.observability_middleware import (  # noqa: E402
    ObservabilityMiddleware,
)

app.add_middleware(ObservabilityMiddleware)
log.info("Observability middleware registered")

# -----------------------------------------------------------------------------
# Idempotency Middleware (PR-6: prevents duplicate POST/PUT/PATCH submissions)
# -----------------------------------------------------------------------------
from app.middleware.idempotency_middleware import IdempotencyMiddleware  # noqa: E402

app.add_middleware(IdempotencyMiddleware)
log.info("Idempotency middleware registered")

# -----------------------------------------------------------------------------
# CSRF Protection Middleware (optional, enable via CSRF_ENABLED=1)
# -----------------------------------------------------------------------------
# PR-30 / High-12: CSRF protection defaults to ON in production.
# Set CSRF_ENABLED=0 to explicitly disable (e.g., for local dev).
CSRF_ENABLED = os.getenv("CSRF_ENABLED", "1" if IS_PROD else "0") == "1"
if CSRF_ENABLED:
    from app.middleware.csrf_middleware import CSRFMiddleware  # noqa: E402
    app.add_middleware(CSRFMiddleware, enabled=True)
    log.info("CSRF protection middleware registered (CSRF_ENABLED=%s, IS_PROD=%s)", CSRF_ENABLED, IS_PROD)
else:
    log.info("CSRF protection disabled (CSRF_ENABLED=0)")

# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
if not CORS_DISABLE:
    # PR-30: restrict allow_methods to the explicit set the API actually uses.
    # Wildcard ["*"] would also permit CONNECT/TRACE/PATCH verbs the API never
    # handles, expanding the attack surface for CORS preflight forgery.
    cfg = {
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
    }
    if CORS_ALLOW_ALL:
        app.add_middleware(CORSMiddleware, allow_origins=["*"], **cfg)
        log.info("[FIX:CORS] CORS middleware enabled for all origins in development mode")
    else:
        app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, **cfg)
        log.info("[FIX:CORS] CORS middleware enabled for origins: %s", CORS_ORIGINS)
else:
    log.warning("[FIX:CORS] CORS middleware is disabled via CORS_DISABLE=1")

# -----------------------------------------------------------------------------
# PR-30 / High-10: Real auth imports are mandatory in every environment.
# Previously: a non-prod env could register dummy /auth/login and /auth/me
# endpoints returning dev tokens. That fallback is now removed — if auth
# imports fail, the app refuses to start.
# -----------------------------------------------------------------------------
try:
    from app.api.deps import (  # type: ignore  # noqa: E402
        create_access_token,
    )
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "Authentication dependencies unavailable — fix the import error. "
        "DEV auth fallback has been removed (PR-30 / High-10)."
    ) from e

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
# Comprehensive health check — for uptime monitoring + load balancer probes
# -----------------------------------------------------------------------------
@app.get(f"{API_V1_STR}/health/detailed", tags=["health"])
def detailed_health():
    """Comprehensive health check for uptime monitoring (e.g. UptimeRobot, BetterStack).

    Returns status of all subsystems. If any critical subsystem is down,
    returns HTTP 503 (suitable for load balancer health checks).

    Light check — does NOT hit external services (Sentry, Telegram API).
    Only checks local DB + Redis connectivity.

    Public endpoint (no auth) — safe to expose to uptime monitors.
    """
    import time
    from datetime import UTC, datetime

    checks = {}
    overall_ok = True

    # 1. Database
    try:
        from sqlalchemy import text as sql_text

        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            db.execute(sql_text("SELECT 1"))
            checks["database"] = {"status": "ok"}
        finally:
            db.close()
    except Exception as e:
        checks["database"] = {"status": "down", "error": str(e)[:100]}
        overall_ok = False

    # 2. Redis (optional — may not be configured in dev)
    try:
        import redis

        from app.core.config import settings
        redis_url = getattr(settings, "ARQ_REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        checks["redis"] = {"status": "ok"}
    except Exception:
        # Redis is optional in dev — don't fail health check
        checks["redis"] = {"status": "skipped", "reason": "not configured or unreachable"}

    # 3. Sentry SDK (check if initialized, don't send event)
    try:
        import sentry_sdk
        client = sentry_sdk.Hub.current.client
        checks["sentry"] = {"status": "ok" if client else "disabled"}
    except Exception:
        checks["sentry"] = {"status": "disabled"}

    # 4. App version + environment
    checks["app"] = {
        "version": os.getenv("APP_VERSION", "0.9.0"),
        "env": os.getenv("ENV", "dev"),
        "python": sys.version.split()[0] if 'sys' in dir() else "?",
    }

    # 5. Uptime (approximate — process start time)
    checks["uptime_seconds"] = int(time.time() - _app_start_time) if _app_start_time else 0

    response = {
        "status": "ok" if overall_ok else "degraded",
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "checks": checks,
    }

    from fastapi import Response
    if not overall_ok:
        return Response(
            content=json.dumps(response),
            status_code=503,
            media_type="application/json",
        )
    return response


# Track app start time for uptime calculation
import time as _time

_app_start_time = _time.time()


# -----------------------------------------------------------------------------
# Диагностика подключённых маршрутов (called from lifespan)
# -----------------------------------------------------------------------------
async def _startup_tasks() -> None:
    """Startup tasks - validates security settings and prints routes"""
    # Validate SECRET_KEY on startup
    try:
        from app.core.config import _DEFAULT_SECRET_KEY, get_settings

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
    backup_enabled = settings.AUTO_BACKUP_ENABLED
    if backup_enabled:
        try:
            from app.db.session import SessionLocal
            from app.services.scheduled_backup import ScheduledBackupService

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

    # #8 fix: Start lab notification scheduler as a safety net.
    # The primary notification path is inline in lab_reporting_service.finalize(),
    # but this scheduler catches any missed events (e.g. if the inline call
    # failed due to a transient error). Runs every 5 minutes.
    try:
        import asyncio

        from app.db.session import SessionLocal
        from app.services.lab_notification_service import LabNotificationService

        async def _run_lab_notifications_periodically():
            while True:
                try:
                    lab_db = SessionLocal()
                    LabNotificationService(lab_db).run_all_notifications()
                    lab_db.close()
                except Exception as exc:
                    log.warning("Lab notification scheduler error: %s", exc)
                await asyncio.sleep(300)  # 5 minutes

        asyncio.create_task(_run_lab_notifications_periodically())
        log.info("✅ Lab notification scheduler started (every 5 minutes)")
    except ImportError:
        log.debug("Lab notification service not available — scheduler skipped")
    except Exception as e:
        log.warning(f"Failed to start lab notification scheduler: {e}")

    # Print routes
    try:
        lines: list[str] = []
        for r in app.router.routes:
            path = getattr(r, "path", "")
            methods = ",".join(sorted(getattr(r, "methods", []) or []))
            name = getattr(r, "name", "")
            lines.append(f"{methods:20s}  {path:40s}  {name}")
        log.info("Mounted routes:\n%s", "\n".join(lines))
        log.info(
            "Flags: TESTING=%s CORS_DISABLE=%s",
            os.getenv("TESTING"),
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
