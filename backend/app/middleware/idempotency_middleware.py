"""Idempotency-Key middleware (PR-6).

Prevents duplicate POST/PUT/PATCH submissions when client retries due to
network errors. If the same Idempotency-Key header is sent twice within
the cache window, the second request returns the cached response instead
of re-executing the handler.

Audit (PR-6) found this was missing — mobile clients that retry on
timeout could create duplicate appointments / payments / patients.

Implementation: in-memory LRU cache keyed by (user_id, idempotency_key),
PLUS an optional Redis-backed distributed claim layer (Codex R1 #3092 P1).

Codex R1 (PR #3092): staging runs two backend workers
(ops/compose.staging.yml); a per-process cache records the key only AFTER the
handler completes, so a lost response retried on ANOTHER worker — or a retry
overlapping the first request — re-executes /registrar/cart and creates
duplicate visits/invoices despite the reused key.

Distributed layer (active when IDEMPOTENCY_REDIS_URL or ARQ_REDIS_URL is
reachable):
  1. Atomic in-flight claim: SET idem:{user}:{key}:claim <token> NX EX TTL.
     A request that fails to claim either replays the stored response
     (idem:{user}:{key}:resp) or receives 409 Conflict (still in flight on
     another worker) — the handler is never executed twice for one key.
  2. Completed 2xx responses are stored in Redis and replayed by any worker;
     non-2xx responses release the claim so the client can retry.
Redis unavailability degrades to the original per-process in-memory behavior
(claimed-but-never-finished keys expire via TTL, so a crashed worker cannot
lock a key forever).
"""
from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from collections import OrderedDict
from typing import Any

import redis as redis_lib

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


class DistributedIdempotencyClaim:
    """Redis-backed atomic claim + response replay for Idempotency-Key.

    Contract (Codex R1 #3092 P1):
      - acquire(user_id, key) -> bool: True iff THIS caller may execute the
        handler. Uses SET NX (atomic across workers/processes).
      - store_response(user_id, key, response, ttl): persist a 2xx snapshot
        for cross-worker replay.
      - load_response(user_id, key) -> Response | None: replay snapshot.
      - release(user_id, key): drop the in-flight claim (called on handler
        completion, success or failure).
      - Every operation is best-effort: a Redis failure never breaks traffic,
        it only degrades to the per-process in-memory cache.
    """

    def __init__(self, redis_url: str, ttl: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._prefix = "idem"
        try:
            self._client = redis_lib.Redis.from_url(
                redis_url,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                decode_responses=True,
            )
            self._client.ping()
            self._available = True
            logger.info("Idempotency distributed claim active via Redis (%s)", redis_url)
        except Exception as exc:  # pragma: no cover - depends on deployment
            logger.warning("Idempotency Redis unavailable (%s); using in-memory cache only", exc)
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @staticmethod
    def _claim_key(user_id: int, key: str) -> str:
        return f"idem:{user_id}:{key}:claim"

    @staticmethod
    def _resp_key(user_id: int, key: str) -> str:
        return f"idem:{user_id}:{key}:resp"

    def _run(self, op, *args, **kwargs):
        try:
            return op(*args, **kwargs)
        except Exception as exc:
            logger.warning("Idempotency Redis op failed: %s", exc)
            self._available = False
            return None

    def acquire(self, user_id: int, key: str) -> bool:
        if not self._available or self._client is None:
            return True  # degrade: caller proceeds (in-memory path)
        ok = self._run(
            self._client.set,
            self._claim_key(user_id, key),
            uuid.uuid4().hex,
            nx=True,
            ex=self._ttl,
        )
        return bool(ok)

    def load_response(self, user_id: int, key: str) -> Response | None:
        if not self._available or self._client is None:
            return None
        raw = self._run(self._client.get, self._resp_key(user_id, key))
        if not raw:
            return None
        try:
            snapshot = json.loads(raw)
            body = base64.b64decode(snapshot["body_b64"])
            return Response(
                content=body,
                status_code=int(snapshot["status"]),
                headers=dict(snapshot["headers"]),
                media_type=snapshot.get("media_type"),
            )
        except Exception as exc:
            logger.warning("Idempotency snapshot decode failed: %s", exc)
            return None

    def store_response(self, user_id: int, key: str, response: Response, ttl: int | None = None) -> None:
        if not self._available or self._client is None:
            return
        body = getattr(response, "body", b"") or b""
        snapshot = json.dumps(
            {
                "status": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "body_b64": base64.b64encode(body).decode("ascii"),
            }
        )
        self._run(
            self._client.set,
            self._resp_key(user_id, key),
            snapshot,
            ex=ttl or self._ttl,
        )

    def release(self, user_id: int, key: str) -> None:
        if not self._available or self._client is None:
            return
        self._run(self._client.delete, self._claim_key(user_id, key))

    def has_in_flight(self, user_id: int, key: str) -> bool:
        """Claim marker present = some worker is executing this key."""
        if not self._available or self._client is None:
            return False
        return bool(self._run(self._client.get, self._claim_key(user_id, key)))


_distributed_claim: DistributedIdempotencyClaim | None = None


def get_distributed_claim() -> DistributedIdempotencyClaim | None:
    """Lazily build the Redis claim layer from settings.

    IDEMPOTENCY_REDIS_URL takes precedence; None falls back to ARQ_REDIS_URL
    (the same Redis the arq worker already uses) so existing deployments gain
    the distributed guarantee without extra configuration.
    """
    global _distributed_claim
    if _distributed_claim is not None:
        return _distributed_claim
    try:
        from app.core.config import settings

        redis_url = settings.IDEMPOTENCY_REDIS_URL or settings.ARQ_REDIS_URL
    except Exception:  # pragma: no cover - settings not initialized (tests)
        return None
    if not redis_url:
        return None
    _distributed_claim = DistributedIdempotencyClaim(redis_url)
    return _distributed_claim


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

        # Check local (per-process) cache first — fastest path
        cached = _idempotency_cache.get(user_id, idempotency_key)
        if cached is not None:
            logger.info(
                "Idempotency hit: user=%s key=%s method=%s path=%s — returning cached response",
                user_id, idempotency_key, request.method, request.url.path,
            )
            return cached

        # Codex R1 #3092 (P1): distributed claim across workers. A retry may
        # land on a different worker (staging runs two) or overlap the first
        # request; the per-process cache alone cannot deduplicate either case.
        claim = get_distributed_claim()
        claim_acquired = True
        if claim is not None and claim.available:
            replayed = claim.load_response(user_id, idempotency_key)
            if replayed is not None:
                logger.info(
                    "Idempotency distributed replay: user=%s key=%s path=%s",
                    user_id, idempotency_key, request.url.path,
                )
                return replayed
            claim_acquired = claim.acquire(user_id, idempotency_key)
            if not claim_acquired:
                # Another worker holds the claim. Its response may have
                # completed between our acquire attempt and now — re-check
                # before rejecting.
                replayed = claim.load_response(user_id, idempotency_key)
                if replayed is not None:
                    logger.info(
                        "Idempotency distributed replay (post-inflight): user=%s key=%s",
                        user_id, idempotency_key,
                    )
                    return replayed
                logger.warning(
                    "Idempotency conflict: key=%s user=%s is in flight on another worker",
                    idempotency_key, user_id,
                )
                return Response(
                    status_code=409,
                    headers={"Retry-After": "1", "Cache-Control": "no-store"},
                    content=(
                        '{"detail": "Request with this Idempotency-Key is '
                        'still being processed. Retry with the same key."}'
                    ),
                    media_type="application/json",
                )

        # Execute handler
        try:
            response = await call_next(request)
        except Exception:
            # Handler crashed — release the claim so the client can retry.
            if claim is not None and claim.available and claim_acquired:
                claim.release(user_id, idempotency_key)
            raise

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
            if claim is not None and claim.available and claim_acquired:
                # Codex R1 #3092 (P1): snapshot for CROSS-WORKER replay, then
                # drop the in-flight claim so later retries replay instead
                # of conflicting.
                claim.store_response(user_id, idempotency_key, cached_response)
                claim.release(user_id, idempotency_key)
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

        # Non-2xx is not cached — release the claim so the client can retry
        # with the same key after fixing the issue.
        if claim is not None and claim.available and claim_acquired:
            claim.release(user_id, idempotency_key)
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
