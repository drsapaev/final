"""
Rate Limiting Configuration — M5.7 (Epic M5 — Enterprise Security).

Rate limits for sensitive endpoints using slowapi (already in requirements).

Limits:
- Login: 5 attempts / 5 min per IP
- Report download: 10 / min per user
- Data export: 3 / hour per user
- Password reset: 3 / hour per IP
- Emergency token: 2 / hour per admin

Usage in endpoints:
    from app.services.rate_limits import limiter

    @router.post("/auth/login")
    @limiter.limit("5/5minutes")
    def login(request: Request, ...):
        ...
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Check if slowapi is available
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    logger.warning("slowapi not installed — rate limiting disabled")


# ─── Rate limit definitions ────────────────────────────────────────────────

RATE_LIMITS: dict[str, str] = {
    # Auth endpoints
    "login": "5/5minutes",
    "refresh": "10/5minutes",
    "password_reset": "3/hour",
    "2fa_verify": "5/5minutes",

    # Patient endpoints
    "report_download": "10/minute",
    "cabinet_summary": "20/minute",
    "form_submit": "5/minute",
    "appointment_create": "5/minute",

    # Admin endpoints
    "data_export": "3/hour",
    "bulk_operation": "2/hour",
    "user_create": "10/hour",
    "emergency_token": "2/hour",

    # General API
    "default": "60/minute",
}


# ─── Limiter instance ───────────────────────────────────────────────────────

if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMITS["default"]])
else:
    # No-op limiter when slowapi not available
    class _NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def init_app(self, *args, **kwargs):
            pass

    limiter = _NoOpLimiter()


def get_rate_limit(endpoint: str) -> str:
    """Get the rate limit string for an endpoint."""
    return RATE_LIMITS.get(endpoint, RATE_LIMITS["default"])


def is_rate_limiting_active() -> bool:
    """Check if rate limiting is active (slowapi installed)."""
    return SLOWAPI_AVAILABLE
