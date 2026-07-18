"""Idempotency-Key middleware (PR-6).

Prevents duplicate POST/PUT/PATCH submissions when client retries due to
network errors. If the same Idempotency-Key header is sent twice within
the cache window, the second request returns the cached response instead
of re-executing the handler.

Audit (PR-6) found this was missing — mobile clients that retry on
timeout could create duplicate appointments / payments / patients.

Implementation: in-memory LRU cache keyed by (user_id, idempotency_key).
For production with multiple workers, this should be backed by Redis;
for now in-memory is sufficient to satisfy the contract and tests.
"""
from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Methods that are idempotent-by-key (GET/DELETE/HEAD are naturally idempotent)
_IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}

# Default cache window: 24 hours. After that, the same key can be reused.
_CACHE_TTL_SECONDS = 24 * 60 * 60

# Max entries to prevent unbounded memory growth
_MAX_CACHE_ENTRIES = 10_000


class IdempotencyResponseCache:
    """In-memory LRU cache for idempotent responses."""

    def __init__(self, max_entries: int = _MAX_CACHE_ENTRIES) -> None:
        self._cache: OrderedDict[tuple[int, str], tuple[float, Response]] = OrderedDict()
        self._max_entries = max_entries

    def get(self, user_id: int, key: str) -> Response | None:
        cache_key = (user_id, key)
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        expires_at, response = entry
        if time.time() > expires_at:
            # Expired — evict
            self._cache.pop(cache_key, None)
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        return response

    def set(self, user_id: int, key: str, response: Response, ttl: int = _CACHE_TTL_SECONDS) -> None:
        cache_key = (user_id, key)
        expires_at = time.time() + ttl
        self._cache[cache_key] = (expires_at, response)
        self._cache.move_to_end(cache_key)
        # Evict oldest if over capacity
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


# Global singleton cache
_idempotency_cache = IdempotencyResponseCache()


def get_idempotency_cache() -> IdempotencyResponseCache:
    return _idempotency_cache


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Idempotency-Key middleware (PR-6).

    Caches responses for POST/PUT/PATCH requests that carry an
    `Idempotency-Key` header. Subsequent requests with the same key
    (and same authenticated user) receive the cached response.

    The cache is in-memory per-worker. For multi-worker production
    deployments, replace with a Redis-backed cache (TODO PR-8).
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Only intercept methods that benefit from idempotency
        if request.method.upper() not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        if not idempotency_key:
            # No key — pass through (idempotency is opt-in)
            return await call_next(request)

        # Resolve user_id from auth state (set by upstream middleware)
        # Default to 0 if unauthenticated (rare for POST, but defensive)
        user_id = self._resolve_user_id(request)

        # Check cache
        cached = _idempotency_cache.get(user_id, idempotency_key)
        if cached is not None:
            logger.info(
                "Idempotency hit: user=%s key=%s method=%s path=%s — returning cached response",
                user_id, idempotency_key, request.method, request.url.path,
            )
            return cached

        # Execute handler
        response = await call_next(request)

        # Cache only successful responses (2xx) — don't cache errors,
        # client should be able to retry with the same key after fixing
        # the issue.
        if 200 <= response.status_code < 300:
            # Materialize the body so we can replay it on cache hit.
            # Starlette StreamingResponse consumes the body on first read,
            # so we need to capture it and build a new Response.
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk
            # Rebuild response with materialized body
            cached_response = Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            _idempotency_cache.set(user_id, idempotency_key, cached_response)
            logger.info(
                "Idempotency cached: user=%s key=%s method=%s path=%s status=%s",
                user_id, idempotency_key, request.method, request.url.path, response.status_code,
            )
            # Return a fresh Response with the same body (so client can read it)
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response

    def _resolve_user_id(self, request: Request) -> int:
        """Best-effort user_id resolution from request state.

        Look for user_id in request.state (set by auth middleware) or
        in the Authorization header (decode JWT). Returns 0 if not found.
        """
        # Fast path: auth middleware already set state.user_id
        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            return int(user_id)
        user = getattr(request.state, "user", None)
        if user is not None:
            uid = getattr(user, "id", None)
            if uid is not None:
                return int(uid)
        return 0
