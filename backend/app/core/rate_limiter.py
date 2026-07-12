"""
Rate limiting infrastructure using slowapi.

PR-34 (Sprint 4 P0): Redis-backed rate limiting + X-Forwarded-For whitelist.

Changes:
1. Custom get_client_ip key function that respects X-Forwarded-For ONLY when
   the request comes from a trusted proxy (TRUSTED_PROXIES env var, comma-separated).
   Prevents IP spoofing from arbitrary clients.

2. Redis storage backend when REDIS_URL is configured. Without Redis, slowapi
   uses in-memory storage — rate limits are per-process. With 4 uvicorn workers,
   the effective limit is 4x what's configured. Redis makes limits shared.

3. Configurable rate limit thresholds via env vars (CHAT-10.1 P2).
   Operators can tune limits without code changes.
"""
from __future__ import annotations

import logging
import os
from ipaddress import AddressValueError, ip_address

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Disable rate limiting in test mode to prevent 429 failures
_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# PR-34: Trusted proxy whitelist for X-Forwarded-For
# ---------------------------------------------------------------------------

def _load_trusted_proxies() -> set[str]:
    """Load trusted proxy IPs from TRUSTED_PROXIES env var.

    Format: comma-separated list of IPs or CIDR ranges.
    Example: TRUSTED_PROXIES=10.0.0.1,10.0.0.2,172.16.0.0/12

    Default: empty set (no trusted proxies — always use direct peer IP).
    """
    raw = os.getenv("TRUSTED_PROXIES", "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


TRUSTED_PROXIES = _load_trusted_proxies()


def _is_trusted_proxy(peer_ip: str) -> bool:
    """Check if the direct peer IP is in the trusted proxy whitelist.

    Supports both exact IP match and CIDR range match.
    """
    if not TRUSTED_PROXIES:
        return False
    try:
        peer = ip_address(peer_ip)
    except (ValueError, AddressValueError):
        return False

    for entry in TRUSTED_PROXIES:
        try:
            if "/" in entry:
                # CIDR range
                import ipaddress
                network = ipaddress.ip_network(entry, strict=False)
                if peer in network:
                    return True
            else:
                # Exact IP match
                if peer == ip_address(entry):
                    return True
        except (ValueError, AddressValueError):
            continue
    return False


def get_client_ip(request: Request) -> str:
    """Custom key function for slowapi Limiter.

    Returns the real client IP, respecting X-Forwarded-For ONLY when the
    request comes from a trusted proxy. This prevents IP spoofing via
    X-Forwarded-For from arbitrary clients.

    Logic:
    1. Get the direct TCP peer IP (request.client.host).
    2. If peer is a trusted proxy, parse X-Forwarded-For and return the
       leftmost (original client) IP.
    3. Otherwise, return the direct peer IP.
    """
    peer_ip = request.client.host if request.client else "0.0.0.0"

    if _is_trusted_proxy(peer_ip):
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            # X-Forwarded-For: client, proxy1, proxy2, ...
            # The leftmost entry is the original client.
            first = xff.split(",")[0].strip()
            try:
                # Validate it's a real IP
                ip_address(first)
                return first
            except (ValueError, AddressValueError):
                logger.warning("Invalid IP in X-Forwarded-For header: %r", first)
                return peer_ip

    return peer_ip


# ---------------------------------------------------------------------------
# PR-34: Redis storage backend
# ---------------------------------------------------------------------------

def _get_storage_uri() -> str | None:
    """Return Redis storage URI if REDIS_URL is configured, else None (in-memory)."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    return redis_url


_STORAGE_URI = _get_storage_uri() if not _TESTING else None


# PR-34: Use custom get_client_ip instead of slowapi's get_remote_address.
# Use Redis storage if configured (shared across workers), else in-memory.
limiter = Limiter(
    key_func=get_client_ip,
    enabled=not _TESTING,
    storage_uri=_STORAGE_URI,
)


# ---------------------------------------------------------------------------
# PR-34 / CHAT-10.1 P2: Configurable rate limits via env vars
# ---------------------------------------------------------------------------

def _env_rate_limit(key: str, default: str) -> str:
    """Read a rate limit from env var RATE_LIMIT_<KEY>, fall back to default."""
    env_name = f"RATE_LIMIT_{key.upper()}"
    return os.getenv(env_name, default).strip() or default


RATE_LIMITS = {
    "login": _env_rate_limit("login", "5/minute"),
    "sms_send": _env_rate_limit("sms_send", "10/minute"),
    "email_send": _env_rate_limit("email_send", "20/minute"),
    "ai_request": _env_rate_limit("ai_request", "30/minute"),
    "payment_init": _env_rate_limit("payment_init", "10/minute"),
    "broadcast": _env_rate_limit("broadcast", "1/5minute"),
    "file_upload": _env_rate_limit("file_upload", "20/minute"),
    "export": _env_rate_limit("export", "5/minute"),
    "migration": _env_rate_limit("migration", "1/minute"),
    "default": _env_rate_limit("default", "60/minute"),
}


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting middleware on the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    if _STORAGE_URI:
        logger.info("Rate limiter using Redis storage: %s", _STORAGE_URI)
    else:
        logger.info("Rate limiter using in-memory storage (set REDIS_URL for shared limits)")
    if TRUSTED_PROXIES:
        logger.info("Rate limiter trusting X-Forwarded-For from proxies: %s", TRUSTED_PROXIES)


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
