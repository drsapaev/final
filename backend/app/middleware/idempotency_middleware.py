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
  1. Atomic in-flight claim: SET idem:{user}:{key}:claim <token> NX EX lease.
     A request that fails to claim either replays the stored response
     (idem:{user}:{key}:resp) or receives 409 Conflict (still in flight on
     another worker) — the handler is never executed twice for one key.
  2. Completed 2xx responses are stored in Redis and replayed by any worker;
     non-2xx responses release the claim so the client can retry.
Redis unavailability degrades to the original per-process in-memory behavior
(claimed-but-never-finished keys expire via the lease TTL, so a crashed
worker cannot lock a key forever).

Codex R2 (PR #3092):
  - P1: the Redis URL is redacted before logging (credentials in URI
    userinfo must not reach logs — see ops/docker-compose.yml REDIS_PASSWORD).
  - P1: transient Redis failures no longer permanently disable the
    distributed layer; the connection re-probes after a short cooldown.
  - P2: the in-flight claim uses a short renewable lease (default 90 s)
    instead of the full 24 h response TTL — a worker that dies mid-request
    locks its key for seconds, not a day.
  - P1: the key is bound to the request payload hash. A retry with the SAME
    key and a DIFFERENT body is rejected with 409 instead of replaying the
    original success (changed data was never persisted — the registrar must
    not be told it was).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
import uuid
from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import jwt
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

# Codex R2 #3092 (P2): the in-flight claim is a SHORT renewable lease, not
# the response TTL. If a worker dies mid-request, same-key retries receive
# 409 only until the lease lapses (seconds), after which the operation may
# re-run — the response was never stored, so no cached success is lost.
_IN_FLIGHT_LEASE_SECONDS = 90

# Codex R2 #3092 (P1): after a transient Redis failure the layer degrades to
# in-memory and re-probes at most once per cooldown. A Redis restart/timeout
# therefore recovers automatically instead of disabling coordination until
# the backend process is restarted.
_RECONNECT_COOLDOWN_SECONDS = 5.0

# Codex R3 #3092 (P1): the in-flight claim is OWNED by the worker that acquired
# it. A worker whose lease lapsed during a Redis outage/long pause must not be
# able to renew or release the replacement claim acquired by another worker:
# renew is compare-and-expire, release is compare-and-delete — both verify the
# stored ownership token, so a stale owner can no longer overwrite or delete
# a live claim (which had allowed a third request to execute and duplicate
# visits/invoices/queue positions).
_LEASE_RENEW_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
)
_LEASE_RELEASE_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


def redact_redis_url(url: str) -> str:
    """Strip URI userinfo credentials from a Redis URL before logging.

    Codex R2 #3092 (P1): ARQ_REDIS_URL may carry a password (as in
    ops/docker-compose.yml). Logging it verbatim would leak the Redis
    credential into routine logs and attached monitoring.
    """
    try:
        parts = urlsplit(url)
        if parts.username is None and parts.password is None:
            return url
        netloc = parts.hostname or ""
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:  # pragma: no cover - defensive
        return "<redis-url-unparseable>"


def payload_hash(body: bytes | None) -> str:
    """Canonical request-body hash binding a key to its payload (Codex R2 #3092)."""
    return hashlib.sha256(body or b"").hexdigest()


def _user_authorized_in_db(db: Any, user_id: int | None, username: str | None, jti: Any) -> bool:
    """Pure DB-backed authorization query — fails CLOSED (Codex R3 #3092).

    Same semantics as app.api.deps._get_user_with_blacklist: the user must
    exist, be active, and the token must not be blacklisted (jti match or
    the all_user_tokens sentinel). One SQL roundtrip.
    """
    if db is None or (user_id is None and not username):
        return False
    try:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from app.models.authentication import TokenBlacklist
        from app.models.user import User

        if user_id is not None:
            subject_filter = User.id == user_id
        else:
            subject_filter = User.username == username

        jti_bl = select(TokenBlacklist.id).where(TokenBlacklist.jti == jti).exists()
        sentinel_bl = (
            select(TokenBlacklist.id)
            .where(
                TokenBlacklist.user_id == User.id,
                TokenBlacklist.reason.like("all_user_tokens:%"),
                TokenBlacklist.expires_at > datetime.now(UTC),
            )
            .exists()
        )
        stmt = select(User.id, User.is_active, jti_bl.label("jti_bl"), sentinel_bl.label("sentinel_bl")).where(
            subject_filter
        )
        row = db.execute(stmt).first()
        if row is None:
            return False
        _, is_active, jti_hit, sentinel_hit = row
        return bool(is_active) and not (jti_hit or sentinel_hit)
    except Exception:
        logger.warning(
            "Idempotency principal authorization query failed; refusing replay",
            exc_info=True,
        )
        return False


def _resolve_request_db(request: Any):
    """Open the SAME session source the request's endpoint will use.

    Production: app.api.deps.get_db → SessionLocal (the canonical DB).
    Test world: the app's dependency override (savepoint-isolated fixture
    session) — the middleware must authorize against the same users the
    endpoint authenticates against, not against a second connection that
    sees a different database.
    """
    from app.api.deps import get_db as canonical_get_db

    override = None
    try:
        override = request.app.dependency_overrides.get(canonical_get_db)
    except Exception:  # pragma: no cover - app object without overrides
        override = None
    return (override or canonical_get_db)()


def _check_principal_authorized_sync(
    request: Any, user_id: int | None, username: str | None, jti: Any
) -> bool:
    """DB-backed principal authorization for the replay path (Codex R3 #3092).

    Resolves the DB through the same session source the endpoint uses, runs
    the authorization query off the event loop, and fails CLOSED: a broken
    DB check never results in a replay.
    """
    try:
        generator = _resolve_request_db(request)
        try:
            db = next(generator)
            return _user_authorized_in_db(db, user_id, username, jti)
        finally:
            try:
                next(generator)
            except StopIteration:
                pass
            except Exception:  # pragma: no cover - generator teardown
                pass
    except Exception:
        logger.warning(
            "Idempotency principal authorization check failed; refusing replay",
            exc_info=True,
        )
        return False


class IdempotencyResponseCache:
    """In-memory LRU cache for idempotent responses.

    Codex R2 #3092 (P1): each entry also stores the SHA-256 of the request
    body it was produced from; get() reports a payload mismatch so the
    middleware can reject changed data replayed under an old key.
    """

    def __init__(self, max_entries: int = _MAX_CACHE_ENTRIES) -> None:
        self._cache: OrderedDict[tuple[str, str], tuple[float, Response, str]] = OrderedDict()
        self._max_entries = max_entries

    def get(self, user_id: str, key: str, body_hash: str | None = None) -> tuple[Response | None, bool]:
        """Return (cached_response, payload_mismatch)."""
        cache_key = (user_id, key)
        entry = self._cache.get(cache_key)
        if entry is None:
            return None, False
        expires_at, response, stored_hash = entry
        if time.time() > expires_at:
            # Expired — evict
            self._cache.pop(cache_key, None)
            return None, False
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        mismatch = bool(body_hash and stored_hash and body_hash != stored_hash)
        return response, mismatch

    def set(self, user_id: str, key: str, response: Response, body_hash: str = "", ttl: int = _CACHE_TTL_SECONDS) -> None:
        cache_key = (user_id, key)
        expires_at = time.time() + ttl
        self._cache[cache_key] = (expires_at, response, body_hash)
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
        handler. Uses SET NX (atomic across workers).
      - store_response(user_id, key, response, ttl, payload_hash): persist a
        2xx snapshot for cross-worker replay.
      - load_response(user_id, key) -> (Response | None, stored_hash | None):
        replay snapshot with its payload binding.
      - release(user_id, key): drop the in-flight claim (called on handler
        completion, success or failure).
      - renew(user_id, key): extend the short in-flight lease while the
        handler is still running (Codex R2 #3092 P2).
      - Every operation is best-effort: a Redis failure never breaks traffic;
        it only degrades to the per-process in-memory cache — and after a
        transient failure the connection is re-probed (Codex R2 #3092 P1),
        so coordination resumes instead of staying disabled.
    """

    # Class-level defaults keep object.__new__-built instances (tests) valid.
    _lease_seconds: int = _IN_FLIGHT_LEASE_SECONDS
    _failed_at: float = 0.0

    def __init__(self, redis_url: str, ttl: int = _CACHE_TTL_SECONDS, lease_seconds: int = _IN_FLIGHT_LEASE_SECONDS) -> None:
        self._ttl = ttl
        self._lease_seconds = lease_seconds
        self._prefix = "idem"
        self._client: redis_lib.Redis | None = None
        self._available = False
        self._failed_at = 0.0
        try:
            client = redis_lib.Redis.from_url(
                redis_url,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                decode_responses=True,
            )
            client.ping()
            self._client = client
            self._available = True
            # Codex R2 #3092 (P1): never log credentials from the URI.
            logger.info("Idempotency distributed claim active via Redis (%s)", redact_redis_url(redis_url))
        except Exception as exc:  # pragma: no cover - depends on deployment
            # Keep the (unverified) client so _ensure_available() can adopt a
            # Redis that comes up after the backend did.
            try:
                self._client = client  # noqa: F821 - defined when from_url succeeded
            except NameError:
                self._client = None
            self._failed_at = time.time()
            logger.warning(
                "Idempotency Redis unavailable (%s); in-memory only, re-probing every %.0fs",
                exc, _RECONNECT_COOLDOWN_SECONDS,
            )

    @property
    def available(self) -> bool:
        return self._available

    def try_available(self) -> bool:
        """Dispatch-time availability check (Codex R2 #3092 P1).

        Unlike the raw ``available`` flag this re-probes Redis after the
        cooldown, so a worker whose distributed layer degraded from a
        transient failure rejoins coordination without a restart.
        """
        return self._ensure_available()

    @property
    def lease_seconds(self) -> int:
        return self._lease_seconds

    @staticmethod
    def _claim_key(user_id: int | str, key: str) -> str:
        return f"idem:{user_id}:{key}:claim"

    @staticmethod
    def _resp_key(user_id: int | str, key: str) -> str:
        return f"idem:{user_id}:{key}:resp"

    def _ensure_available(self) -> bool:
        """Recover the Redis connection after a transient failure.

        Codex R2 #3092 (P1): a timeout / Redis restart must not permanently
        disable the distributed layer on this worker. Probes are rate-limited
        to one per cooldown; ping is idempotent, so a concurrent double-probe
        is harmless.
        """
        if self._available:
            return True
        if self._client is None:
            return False
        now = time.time()
        if now - self._failed_at < _RECONNECT_COOLDOWN_SECONDS:
            return False
        self._failed_at = now  # probe starts: throttle further probes
        try:
            self._client.ping()
            self._available = True
            logger.info("Idempotency Redis connection recovered after transient failure")
            return True
        except Exception as exc:
            logger.warning("Idempotency Redis reconnect failed: %s", exc)
            return False

    def _run(self, op, *args, **kwargs):
        if not self._ensure_available():
            return None
        try:
            return op(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                "Idempotency Redis op failed (%s); degrading for %.0fs, then re-probing",
                exc, _RECONNECT_COOLDOWN_SECONDS,
            )
            self._available = False
            self._failed_at = time.time()
            return None

    def acquire(self, user_id: int | str, key: str) -> str | None:
        """Acquire the in-flight claim; return the OWNERSHIP TOKEN.

        Codex R3 #3092 (P1): the token binds renew/release to the acquirer —
        a stale worker cannot renew or delete a replacement claim.
        Returns:
          - a non-empty token string: the caller owns the claim and may execute;
          - None: the claim is held elsewhere (409 to the client) or the Redis
            op failed (conservative: refuse execution, same as before R3).
          Degraded mode (Redis unavailable before the claim attempt) returns a
          synthetic token so the request proceeds on the in-memory path.
        """
        if not self._ensure_available() or self._client is None:
            return f"local-{uuid.uuid4().hex}"  # degrade: caller proceeds (in-memory path)
        token = uuid.uuid4().hex
        ok = self._run(
            self._client.set,
            self._claim_key(user_id, key),
            token,
            nx=True,
            ex=self._lease_seconds,  # Codex R2 #3092 (P2): short renewable lease
        )
        return token if ok else None

    def renew(self, user_id: int | str, key: str, token: str) -> bool:
        """Extend the in-flight lease — only for the CURRENT owner (Codex R3).

        Compare-and-expire: the stored ownership token must match. A claim
        that lapsed and was re-acquired by another worker is never renewed
        by the stale owner (SET XX alone only checked existence).
        """
        if not self._ensure_available() or self._client is None:
            return False
        ok = self._run(
            self._client.eval,
            _LEASE_RENEW_LUA,
            1,
            self._claim_key(user_id, key),
            token,
            str(self._lease_seconds),
        )
        return bool(ok)

    def release(self, user_id: int | str, key: str, token: str) -> None:
        """Drop the in-flight claim — only if THIS caller still owns it (Codex R3)."""
        if not self._ensure_available() or self._client is None:
            return
        self._run(
            self._client.eval,
            _LEASE_RELEASE_LUA,
            1,
            self._claim_key(user_id, key),
            token,
        )

    def load_response(self, user_id: int | str, key: str) -> tuple[Response | None, str | None]:
        """Return (replay_response, stored_payload_hash)."""
        if not self._ensure_available() or self._client is None:
            return None, None
        raw = self._run(self._client.get, self._resp_key(user_id, key))
        if not raw:
            return None, None
        try:
            snapshot = json.loads(raw)
            body = base64.b64decode(snapshot["body_b64"])
            return Response(
                content=body,
                status_code=int(snapshot["status"]),
                headers=dict(snapshot["headers"]),
                media_type=snapshot.get("media_type"),
            ), snapshot.get("payload_hash")
        except Exception as exc:
            logger.warning("Idempotency snapshot decode failed: %s", exc)
            return None, None

    def store_response(self, user_id: int | str, key: str, response: Response, ttl: int | None = None, payload_hash: str = "") -> None:
        if not self._ensure_available() or self._client is None:
            return
        body = getattr(response, "body", b"") or b""
        snapshot = json.dumps(
            {
                "status": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "body_b64": base64.b64encode(body).decode("ascii"),
                "payload_hash": payload_hash,
            }
        )
        self._run(
            self._client.set,
            self._resp_key(user_id, key),
            snapshot,
            ex=ttl or self._ttl,
        )

    def has_in_flight(self, user_id: int | str, key: str) -> bool:
        """Claim marker present = some worker is executing this key."""
        if not self._ensure_available() or self._client is None:
            return False
        return bool(self._run(self._client.get, self._claim_key(user_id, key)))


_distributed_claim: DistributedIdempotencyClaim | None = None


async def _renew_lease_loop(claim: DistributedIdempotencyClaim, user_id: int | str, key: str, token: str) -> None:
    """Renew the in-flight claim lease while the handler is running.

    Codex R2 #3092 (P2): interval is half the lease, so a renewal burst of
    failures (Redis briefly down) still leaves the claim alive; if the task
    is cancelled (handler finished / worker died), the lease simply lapses
    after lease_seconds and same-key retries stop receiving 409.
    Codex R3 #3092 (P1): renewals carry the owner token — a stale loop can
    no longer extend a claim that now belongs to another worker.
    """
    interval = max(1.0, claim.lease_seconds / 2.0)
    try:
        while True:
            await asyncio.sleep(interval)
            claim.renew(user_id, key, token)
    except asyncio.CancelledError:
        return


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
    (and same authenticated user, and SAME request payload) receive the
    cached response. Codex R2 #3092 (P1): a retry with the same key but a
    changed body is rejected with 409 — the cached success belongs to the
    original payload, replaying it for different data would lie to the
    registrar ("saved" while the revision was never persisted).

    The in-flight claim is a short renewable lease (Codex R2 #3092 P2):
    while the handler runs, the middleware renews it so a legitimately slow
    request is not 409-locked for a day if the worker later dies.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Only intercept methods that benefit from idempotency
        if request.method.upper() not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        if not idempotency_key:
            # No key — pass through (idempotency is opt-in)
            return await call_next(request)

        # Codex R2 #3092 (P1): bind the key to the request payload. Reading
        # the body here is safe with BaseHTTPMiddleware — the buffered body
        # is replayed to the downstream app.
        try:
            request_body = await request.body()
        except Exception:  # pragma: no cover - body already consumed
            request_body = b""
        incoming_hash = payload_hash(request_body)

        # Codex R3 #3092 (P1): the cache namespace comes from a VERIFIED
        # principal. Authentication lives in endpoint dependencies — no
        # upstream middleware populates request.state.user_id, so the old
        # _resolve_user_id resolved EVERY request to user 0 and the Redis
        # lookup could replay a cached cart response to an unauthenticated
        # caller or across auth boundaries (same key + body, different
        # client). Now: the JWT in the Authorization header is verified
        # (signature + exp) and the namespace is derived from its sub claim;
        # requests without a verifiable identity bypass idempotency entirely
        # (the endpoint will 401 them — nothing is stored or replayed).
        principal_payload = self._verified_principal(request)
        if principal_payload is None:
            return await call_next(request)
        user_id = self._namespace(principal_payload)

        # Check local (per-process) cache first — fastest path
        cached, local_mismatch = _idempotency_cache.get(user_id, idempotency_key, incoming_hash)
        if local_mismatch:
            logger.warning(
                "Idempotency payload mismatch (local): user=%s key=%s path=%s — refusing to replay "
                "the original success for changed data",
                user_id, idempotency_key, request.url.path,
            )
            return self._payload_mismatch_response()
        if cached is not None:
            # Codex R3 #3092 (P1): replay only after authorization — the
            # principal must still resolve to an active, non-blacklisted user.
            if not await self._principal_authorized(request, principal_payload):
                logger.warning(
                    "Idempotency replay refused (principal not authorized): user=%s key=%s path=%s",
                    user_id, idempotency_key, request.url.path,
                )
                return await call_next(request)
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
        claim_token: str | None = None
        if claim is not None and claim.try_available():
            replayed, stored_hash = claim.load_response(user_id, idempotency_key)
            if replayed is not None:
                if stored_hash and stored_hash != incoming_hash:
                    logger.warning(
                        "Idempotency payload mismatch (distributed): user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    return self._payload_mismatch_response()
                # Codex R3 #3092 (P1): authorization before cross-worker replay.
                if not await self._principal_authorized(request, principal_payload):
                    logger.warning(
                        "Idempotency distributed replay refused (principal not authorized): user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    return await call_next(request)
                logger.info(
                    "Idempotency distributed replay: user=%s key=%s path=%s",
                    user_id, idempotency_key, request.url.path,
                )
                return replayed
            claim_token = claim.acquire(user_id, idempotency_key)
            claim_acquired = claim_token is not None
            if not claim_acquired:
                # Another worker holds the claim. Its response may have
                # completed between our acquire attempt and now — re-check
                # before rejecting.
                replayed, stored_hash = claim.load_response(user_id, idempotency_key)
                if replayed is not None:
                    if stored_hash and stored_hash != incoming_hash:
                        return self._payload_mismatch_response()
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

        # Execute handler with a lease-renewal loop (Codex R2 #3092 P2):
        # while this worker is still executing, the in-flight claim is
        # periodically extended so a slow-but-alive request never lapses;
        # if the worker dies, the loop dies with it and the short lease
        # expires on its own (no 24h 409 lockout). Codex R3 #3092 (P1):
        # renewals and release carry the OWNER TOKEN, so a stale worker can
        # neither extend nor delete a claim that now belongs to another.
        lease_task: asyncio.Task | None = None
        if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
            lease_task = asyncio.create_task(
                _renew_lease_loop(claim, user_id, idempotency_key, claim_token)
            )
        try:
            response = await call_next(request)
        except Exception:
            # Handler crashed — release the claim so the client can retry.
            if lease_task is not None:
                lease_task.cancel()
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                claim.release(user_id, idempotency_key, claim_token)
            raise
        finally:
            if lease_task is not None:
                lease_task.cancel()

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
            _idempotency_cache.set(user_id, idempotency_key, cached_response, incoming_hash)
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                # Codex R1 #3092 (P1): snapshot for CROSS-WORKER replay, then
                # drop the in-flight claim so later retries replay instead
                # of conflicting. Codex R2 #3092 (P1): the snapshot carries
                # the payload hash — changed data is never replayed as the
                # original success.
                claim.store_response(user_id, idempotency_key, cached_response, payload_hash=incoming_hash)
                claim.release(user_id, idempotency_key, claim_token)
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
        if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
            claim.release(user_id, idempotency_key, claim_token)
        return response

    @staticmethod
    def _payload_mismatch_response() -> Response:
        """409 for a reused key with a changed payload (Codex R2 #3092 P1)."""
        return Response(
            status_code=409,
            headers={"Cache-Control": "no-store"},
            content=(
                '{"detail": "This Idempotency-Key was already used with a '
                'different request payload. The original data may already be '
                'saved — do not retry changed data with the same key; verify '
                'the record state first."}'
            ),
            media_type="application/json",
        )

    _JWT_LEEWAY_SECONDS = 15

    def _verified_principal(self, request: Request) -> dict[str, Any] | None:
        """Verify the bearer JWT and return its payload (Codex R3 #3092 P1).

        The payload's `sub` becomes the idempotency namespace. Returns None
        when the request carries no verifiable identity — such requests
        bypass idempotency entirely (nothing stored, nothing replayed).
        """
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth_header:
            return None
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        try:
            from app.core.config import settings

            return jwt.decode(
                token.strip(),
                settings.SECRET_KEY,
                algorithms=[getattr(settings, "ALGORITHM", "HS256")],
                leeway=self._JWT_LEEWAY_SECONDS,
            )
        except Exception as exc:
            logger.debug("Idempotency: no verifiable principal (%s)", type(exc).__name__)
            return None

    @staticmethod
    def _namespace(principal_payload: dict[str, Any]) -> str:
        """Stable per-principal cache namespace from the verified sub claim.

        Hashed: no usernames/ids in Redis keys, no collision between a text
        sub (username) and a colon-bearing value.
        """
        sub = str(principal_payload.get("sub") or "")
        return hashlib.sha256(sub.encode("utf-8")).hexdigest()[:32]

    async def _principal_authorized(self, request: Request, principal_payload: dict[str, Any]) -> bool:
        """DB-backed authorization before any replay (Codex R3 #3092 P1).

        Mirrors get_current_user's semantics: the user must exist, be active,
        and the token must not be blacklisted (jti or all-user sentinel).
        Runs the sync query in a worker thread; fails CLOSED — a broken DB
        check never results in a replay (the request falls through to the
        endpoint, which re-authenticates anyway).
        """
        sub = principal_payload.get("sub")
        sub_text = str(sub) if sub is not None else ""
        user_id = int(sub_text) if sub_text.isdigit() else None
        username = None if user_id is not None else (sub_text or None)
        jti = principal_payload.get("jti")
        try:
            return await asyncio.to_thread(
                _check_principal_authorized_sync, request, user_id, username, jti
            )
        except Exception:  # pragma: no cover - to_thread failure is fail-closed
            logger.warning("Idempotency principal check crashed; refusing replay", exc_info=True)
            return False
