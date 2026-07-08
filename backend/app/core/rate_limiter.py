"""
Rate limiting infrastructure using slowapi.

Provides per-IP and per-user rate limiting for sensitive endpoints.
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import FastAPI

# Disable rate limiting in test mode to prevent 429 failures
_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")

# Create limiter instance (disabled in test mode)
limiter = Limiter(key_func=get_remote_address, enabled=not _TESTING)

# Rate limit configurations
RATE_LIMITS = {
    "login": "5/minute",
    "sms_send": "10/minute",
    "email_send": "20/minute",
    "ai_request": "30/minute",
    "payment_init": "10/minute",
    "broadcast": "1/5minute",
    "file_upload": "20/minute",
    "export": "5/minute",
    "migration": "1/minute",
    "default": "60/minute",
}


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting middleware on the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": getattr(exc, "retry_after", None),
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
        },
    )
