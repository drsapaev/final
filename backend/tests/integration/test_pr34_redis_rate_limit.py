"""
PR-34 — Sprint 4 P0: Redis-backed rate limiting + X-Forwarded-For whitelist.

Tests for:
1. Rate limiter uses a custom key function that respects X-Forwarded-For
   ONLY when the request comes from a trusted proxy (whitelist).
2. Rate limiter uses Redis storage when REDIS_URL is configured (so rate
   limits are shared across multiple uvicorn workers).
3. Rate limit thresholds are configurable via env vars.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
RATE_LIMITER_PY = BACKEND_DIR / "app" / "core" / "rate_limiter.py"


# ---------- 1. X-Forwarded-For whitelist key function ----------

def test_rate_limiter_uses_custom_key_function():
    """The rate limiter must NOT use slowapi.util.get_remote_address directly.

    Default get_remote_address returns request.client.host (direct TCP peer).
    Behind a reverse proxy (nginx, Cloudflare, Vercel), all requests appear
    to come from the proxy's IP, so a single abuser can exhaust the rate
    limit for ALL users.

    Fix: use a custom key function that:
    - Returns the direct peer IP by default
    - If the request comes from a trusted proxy (whitelist), use X-Forwarded-For
    """
    src = RATE_LIMITER_PY.read_text(encoding="utf-8")
    # Must define a custom key function (not just use get_remote_address)
    assert re.search(r"def\s+get_client_ip\s*\(", src), (
        "Custom get_client_ip function not found in rate_limiter.py — "
        "must replace slowapi.util.get_remote_address with a whitelist-aware function"
    )


def test_rate_limiter_has_trusted_proxy_whitelist():
    """A TRUSTED_PROXIES env var must be consulted for the X-Forwarded-For whitelist.

    Only requests from trusted proxy IPs are allowed to use X-Forwarded-For.
    This prevents IP spoofing from arbitrary clients.
    """
    src = RATE_LIMITER_PY.read_text(encoding="utf-8")
    assert "TRUSTED_PROXIES" in src, (
        "TRUSTED_PROXIES env var not referenced in rate_limiter.py — "
        "must whitelist trusted proxies before trusting X-Forwarded-For"
    )


# ---------- 2. Redis storage backend ----------

def test_rate_limiter_supports_redis_storage():
    """The rate limiter must use Redis storage when REDIS_URL is configured.

    Without Redis, slowapi uses in-memory storage — rate limits are per-process.
    With 4 uvicorn workers, the effective limit is 4x what's configured.
    Redis makes rate limits shared across all workers.
    """
    src = RATE_LIMITER_PY.read_text(encoding="utf-8")
    # Must reference REDIS_URL and pass storage_uri to Limiter
    assert "REDIS_URL" in src, (
        "REDIS_URL not referenced in rate_limiter.py — must support Redis backend"
    )
    assert "storage_uri" in src, (
        "storage_uri parameter not passed to Limiter — must configure Redis backend"
    )


# ---------- 3. Configurable rate limits ----------

def test_rate_limits_are_configurable_via_env():
    """Rate limit thresholds must be configurable via env vars (CHAT-10.1 P2).

    Currently hardcoded in RATE_LIMITS dict. Operators need to tune limits
    without code changes (e.g., higher login limit for staging, lower for prod).
    """
    src = RATE_LIMITER_PY.read_text(encoding="utf-8")
    # Must reference env var for at least the default rate limit.
    # Acceptable patterns:
    #   getenv("RATE_LIMIT_DEFAULT", ...)
    #   getenv(f"RATE_LIMIT_{key}", ...)
    #   RATE_LIMIT_DEFAULT env var name in any form
    assert (
        re.search(r"RATE_LIMIT.*DEFAULT", src)
        or re.search(r'getenv\(\s*[\'"]RATE_LIMIT', src)
        or re.search(r'getenv\(\s*env_name', src)  # f-string pattern: env_name = f"RATE_LIMIT_{key}"
    ), (
        "RATE_LIMIT env var not referenced in rate_limiter.py — "
        "rate limits must be configurable via env (CHAT-10.1 P2)"
    )
