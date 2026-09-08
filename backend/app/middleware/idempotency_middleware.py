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


def _user_authorized_in_db(
    db: Any, user_id: int | None, username: str | None, jti: Any
) -> tuple[bool, str | None, bool]:
    """Pure DB-backed authorization query — fails CLOSED (Codex R3/R4 #3092).

    Same semantics as app.api.deps._get_user_with_blacklist, plus the role:
    the user must exist, be active, and the token must not be blacklisted
    (jti match or the all_user_tokens sentinel). One SQL roundtrip.
    Returns (authorized, role, is_superuser) — the role binds stored
    responses to the RBAC policy they were produced under (Codex R4 #3092
    P1); is_superuser lets the replay evaluate require_roles' superuser
    bypass exactly as the endpoint would (Codex R6 #3092 P1).
    """
    if db is None or (user_id is None and not username):
        return False, None, False
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
        stmt = select(
            User.id,
            User.is_active,
            User.role,
            User.is_superuser,
            jti_bl.label("jti_bl"),
            sentinel_bl.label("sentinel_bl"),
        ).where(subject_filter)
        row = db.execute(stmt).first()
        if row is None:
            return False, None, False
        _, is_active, role, is_superuser, jti_hit, sentinel_hit = row
        role_label = str(role) if role is not None else None
        return (bool(is_active) and not (jti_hit or sentinel_hit)), role_label, bool(is_superuser)
    except Exception:
        logger.warning(
            "Idempotency principal authorization query failed; refusing replay",
            exc_info=True,
        )
        return False, None, False


def _user_id_from_principal(principal_payload: dict[str, Any]) -> tuple[int | None, str | None]:
    """Subject selection mirrored from deps.py (Codex R9 #3092 P1).

    The username claim is the canonical primary subject: numeric text
    resolves by id, text by username. Without it, a numeric sub resolves
    by id, a text sub by username. Shared by the namespace resolution
    (Codex R11 #3092 P1) and the DB authorization check so both see the
    SAME account for a given token.
    """
    username_claim = principal_payload.get("username")
    if isinstance(username_claim, str) and username_claim:
        user_id = int(username_claim) if username_claim.isdigit() else None
        return (user_id, None) if user_id is not None else (None, username_claim)
    sub = principal_payload.get("sub")
    if isinstance(sub, str) and sub:
        user_id = int(sub) if sub.isdigit() else None
        return (user_id, None) if user_id is not None else (None, sub)
    if isinstance(sub, int):
        # Legacy numeric (non-stringified) sub — get_current_user's
        # fallback resolves it by id.
        return sub, None
    return None, None


def _resolve_principal_id_sync(
    request: Any, user_id: int | None, username: str | None
) -> int | None:
    """Canonical DB user id for the namespace (Codex R11 #3092 P1).

    Mobile login tokens carry ``sub=username`` while /mobile/auth/refresh
    issues tokens with ``sub=user.id`` (+ username claim). Hashing the raw
    sub moved the same user's keys to a different namespace after token
    refresh, so a lost-response retry after the refresh could not find the
    stored outcome and re-executed the write (duplicate appointment).
    Resolution-only: is_active/blacklist checks stay with the fail-closed
    _principal_authorized. Returns None (missing row / broken DB) → the
    caller refuses non-executing (fail-closed, Codex R8-consistent): the
    endpoint never runs, nothing commits under a wrong namespace.
    """
    if user_id is None and not username:
        return None
    try:
        generator = _resolve_request_db(request)
        try:
            db = next(generator)
            from sqlalchemy import select

            from app.models.user import User

            stmt = (
                select(User.id).where(User.id == user_id)
                if user_id is not None
                else select(User.id).where(User.username == username)
            )
            row = db.execute(stmt).first()
            return int(row[0]) if row is not None else None
        finally:
            try:
                next(generator)
            except StopIteration:
                pass
            except Exception:  # pragma: no cover - generator teardown
                pass
    except Exception:
        # Fail CLOSED: without a canonical id there is NO namespace and no
        # idempotency protection can be evaluated — the caller refuses
        # non-executing instead of running the endpoint unprotected.
        logger.warning(
            "Idempotency principal namespace resolution failed; refusing",
            exc_info=True,
        )
        return None


def _principal_refusal_response() -> Response:
    """Codex R8 #3092 (P1): non-executing failure for a refused principal.

    Прежнее поведение — fall-through к эндпоинту — опиралось на допущение,
    что эндпоинт сам пере-аутентифицирует и откажет. Это неверно для
    деактивированного пользователя: get_current_user/require_roles не
    проверяют is_active, поэтому запрос ДЕАКТИВИРОВАННОГО регистратора
    проходил дальше, эндпоинт КОММИТИЛ корзину, а middleware не хранил
    исход — потерянный ответ с тем же ключом исполнял команду повторно
    (дубли визитов, счетов и позиций очереди). Теперь отказ принципалу —
    НЕИСПОЛНЯЮЩИЙ ответ 403: эндпоинт не запускается, ничего не коммитится,
    claim освобождается, привязка ключа сохраняется для восстановления.
    """
    return Response(
        status_code=403,
        content='{"detail": "Пользователь деактивирован или сессия недействительна"}',
        media_type="application/json",
    )


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
) -> tuple[bool, str | None, bool]:
    """DB-backed principal authorization for the replay path (Codex R3/R4 #3092).

    Resolves the DB through the same session source the endpoint uses, runs
    the authorization query off the event loop, and fails CLOSED: a broken
    DB check never results in a replay.
    Returns (authorized, current_role, is_superuser).
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
        return False, None, False


class IdempotencyResponseCache:
    """In-memory LRU cache for idempotent responses.

    Codex R2 #3092 (P1): each entry also stores the SHA-256 of the request
    body it was produced from; get() reports a payload mismatch so the
    middleware can reject changed data replayed under an old key.
    """

    def __init__(self, max_entries: int = _MAX_CACHE_ENTRIES) -> None:
        self._cache: OrderedDict[tuple[str, str], tuple[float, Response, str, str | None]] = OrderedDict()
        self._max_entries = max_entries

    def get(self, user_id: str, key: str, body_hash: str | None = None) -> tuple[Response | None, bool, str | None]:
        """Return (cached_response, payload_mismatch, bound_role)."""
        cache_key = (user_id, key)
        entry = self._cache.get(cache_key)
        if entry is None:
            return None, False, None
        expires_at, response, stored_hash, stored_role = entry
        if time.time() > expires_at:
            # Expired — evict
            self._cache.pop(cache_key, None)
            return None, False, None
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        mismatch = bool(body_hash and stored_hash and body_hash != stored_hash)
        return response, mismatch, stored_role

    def invalidate(self, user_id: str, key: str) -> None:
        """Drop a stored response whose role binding can never match again
        (Codex R4 #3092: role changed since execution)."""
        self._cache.pop((user_id, key), None)

    def set(self, user_id: str, key: str, response: Response, body_hash: str = "", ttl: int = _CACHE_TTL_SECONDS, principal_role: str | None = None) -> None:
        cache_key = (user_id, key)
        expires_at = time.time() + ttl
        self._cache[cache_key] = (expires_at, response, body_hash, principal_role)
        self._cache.move_to_end(cache_key)
        # Evict oldest if over capacity
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


# Global singleton cache
_idempotency_cache = IdempotencyResponseCache()


# ── Codex R9 #3092 (P1): in-process mirror of the execution-intent marker ───
# When Redis is unavailable the distributed claim layer degrades to
# in-memory coordination; the intent marker follows the same pattern so a
# retry on THIS worker never blindly re-executes after a lost outcome.
# Cross-worker reconciliation without Redis is impossible by design — the
# marker is best-effort, exactly like the claim itself.
_execution_intent_ttl_seconds = _CACHE_TTL_SECONDS
_local_execution_intents: OrderedDict[tuple[str, str], float] = OrderedDict()


def _sweep_local_execution_intents(now: float | None = None) -> None:
    now = time.time() if now is None else now
    stale = [k for k, expires_at in _local_execution_intents.items() if expires_at <= now]
    for k in stale:
        _local_execution_intents.pop(k, None)


def _mark_local_execution_intent(user_id: int | str, key: str) -> None:
    _sweep_local_execution_intents()
    _local_execution_intents[(str(user_id), key)] = time.time() + _execution_intent_ttl_seconds


def _clear_local_execution_intent(user_id: int | str, key: str) -> None:
    _local_execution_intents.pop((str(user_id), key), None)


def _local_execution_intent_exists(user_id: int | str, key: str) -> bool:
    _sweep_local_execution_intents()
    return (str(user_id), key) in _local_execution_intents


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

    def load_response(self, user_id: int | str, key: str) -> tuple[Response | None, str | None, str | None]:
        """Return (replay_response, stored_payload_hash, bound_principal_role)."""
        if not self._ensure_available() or self._client is None:
            return None, None, None
        raw = self._run(self._client.get, self._resp_key(user_id, key))
        if not raw:
            return None, None, None
        try:
            snapshot = json.loads(raw)
            body = base64.b64decode(snapshot["body_b64"])
            return Response(
                content=body,
                status_code=int(snapshot["status"]),
                headers=dict(snapshot["headers"]),
                media_type=snapshot.get("media_type"),
            ), snapshot.get("payload_hash"), snapshot.get("principal_role")
        except Exception as exc:
            logger.warning("Idempotency snapshot decode failed: %s", exc)
            return None, None, None

    def store_response(self, user_id: int | str, key: str, response: Response, ttl: int | None = None, payload_hash: str = "", principal_role: str | None = None) -> None:
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
                "principal_role": principal_role,
            }
        )
        self._run(
            self._client.set,
            self._resp_key(user_id, key),
            snapshot,
            ex=ttl or self._ttl,
        )

    def forget_response(self, user_id: int | str, key: str) -> None:
        """Drop the stored response snapshot (stale role binding — Codex R4
        #3092): the next request re-executes and re-stores with the fresh
        binding instead of being refused forever."""
        if not self._ensure_available() or self._client is None:
            return
        self._run(self._client.delete, self._resp_key(user_id, key))

    def has_in_flight(self, user_id: int | str, key: str) -> bool:
        """Claim marker present = some worker is executing this key."""
        if not self._ensure_available() or self._client is None:
            return False
        return bool(self._run(self._client.get, self._claim_key(user_id, key)))

    # ── Codex R9 #3092 (P1): durable pre-execution intent marker ──────────
    #
    # The endpoint commits the cart INSIDE call_next while the idempotency
    # outcome is only stored AFTER the response materializes. A worker that
    # dies in between loses its short renewable claim (90 s) and the same-key
    # retry re-executes the write — duplicating visits, invoices and queue
    # entries. The intent marker is written BEFORE the handler runs and lives
    # as long as the response snapshot would have (_ttl): a retry that finds
    # an intent but NO stored response knows a previous attempt reached
    # execution with an UNKNOWN outcome and must not blindly re-execute.

    @staticmethod
    def _intent_key(user_id: int | str, key: str) -> str:
        return f"idem:{user_id}:{key}:intent"

    def mark_execution_intent(self, user_id: int | str, key: str) -> None:
        """Best-effort durable marker: 'this key reached execution'."""
        if not self._ensure_available() or self._client is None:
            _mark_local_execution_intent(user_id, key)
            return
        self._run(
            self._client.set,
            self._intent_key(user_id, key),
            "1",
            ex=self._ttl,
        )
        # Mirror locally too: Redis degradation after marking must not turn a
        # later retry into a blind re-execution on THIS worker.
        _mark_local_execution_intent(user_id, key)

    def clear_execution_intent(self, user_id: int | str, key: str) -> None:
        """Outcome is KNOWN (response stored, or the endpoint returned a
        completed non-2xx without committing) — the marker is no longer
        needed and the retry contract returns to its previous shape."""
        if self._ensure_available() and self._client is not None:
            self._run(self._client.delete, self._intent_key(user_id, key))
        _clear_local_execution_intent(user_id, key)

    def execution_intent_exists(self, user_id: int | str, key: str) -> bool:
        if self._ensure_available() and self._client is not None:
            marked = bool(self._run(self._client.exists, self._intent_key(user_id, key)))
            if marked:
                return True
        return _local_execution_intent_exists(user_id, key)


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
        # Codex R11 #3092 (P1): the namespace comes from the CANONICALLY
        # RESOLVED user id (login token sub=username vs refresh token
        # sub=user.id must share ONE namespace — see _resolve_principal_id_sync).
        subject_user_id, subject_username = _user_id_from_principal(principal_payload)
        canonical_id = await asyncio.to_thread(
            _resolve_principal_id_sync, request, subject_user_id, subject_username
        )
        if canonical_id is None:
            # Unresolvable principal (missing row / DB outage): NO namespace —
            # fail CLOSED like every other principal refusal (Codex R8): the
            # endpoint is not executed (nothing commits), nothing is stored
            # or replayed under any namespace. A missing account cannot
            # commit: the endpoint's own get_current_user would 401 it.
            logger.warning(
                "Idempotency principal namespace unresolved; refusing (non-executing): path=%s",
                request.url.path,
            )
            return _principal_refusal_response()
        user_id = self._namespace(canonical_id)

        # Codex R4 #3092 (P1): resolve the distributed claim BEFORE the local
        # cache check — the role-mismatch fall-through needs it to drop a
        # stale snapshot and re-execute.
        claim = get_distributed_claim()
        claim_acquired = True
        claim_token: str | None = None

        # Check local (per-process) cache first — fastest path
        cached, local_mismatch, cached_role = _idempotency_cache.get(user_id, idempotency_key, incoming_hash)
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
            # Codex R4 #3092 (P1): the response is additionally bound to the
            # authorized ROLE at execution time.
            # Codex R6 #3092 (P1): a changed role is no longer refused by
            # label comparison alone — the ENDPOINT policy decides. Admin↔
            # Registrar both pass /registrar/cart, so a role change between
            # two authorized roles must REPLAY the committed snapshot, not
            # evict it and re-execute the write (duplicate visits/invoices).
            authorized, current_role, current_superuser = await self._principal_authorized(request, principal_payload)
            if not authorized:
                logger.warning(
                    "Idempotency replay refused (principal not authorized): user=%s key=%s path=%s",
                    user_id, idempotency_key, request.url.path,
                )
                # Codex R8 #3092 (P1): НЕИСПОЛНЯЮЩИЙ отказ — эндпоинт не
                # запускается, снапшот не эвиктится (восстановление после
                # реактивации по тому же ключу).
                return _principal_refusal_response()
            permitted = self._role_permitted_for_replay(request, cached_role, current_role, current_superuser)
            if permitted is True or (
                permitted is None and (cached_role is None or current_role == cached_role)
            ):
                logger.info(
                    "Idempotency hit: user=%s key=%s method=%s path=%s — returning cached response",
                    user_id, idempotency_key, request.method, request.url.path,
                )
                return cached
            if permitted is False:
                # Endpoint policy refuses the current role — the endpoint's
                # require_roles 403s + audits it exactly as for a fresh
                # request. The snapshot is KEPT: when the principal regains
                # an allowed role, the same-key retry replays again instead
                # of re-executing the write.
                logger.warning(
                    "Idempotency replay refused (endpoint policy): user=%s key=%s path=%s (stored=%s current=%s) — falling through",
                    user_id, idempotency_key, request.url.path, cached_role, current_role,
                )
                return await call_next(request)
            # permitted is None (policy unknown) AND the role label changed:
            # conservative R4 fallback — evict the stale binding so the
            # re-execution re-stores with the fresh role.
            logger.warning(
                "Idempotency replay refused (role changed since execution, policy unknown): user=%s key=%s path=%s (%s -> %s) — re-executing",
                user_id, idempotency_key, request.url.path, cached_role, current_role,
            )
            _idempotency_cache.invalidate(user_id, idempotency_key)
            if claim is not None and claim.try_available():
                claim.forget_response(user_id, idempotency_key)
            cached = None
            cached_role = None

        # Codex R1 #3092 (P1): distributed claim across workers. A retry may
        # land on a different worker (staging runs two) or overlap the first
        # request; the per-process cache alone cannot deduplicate either case.
        if claim is not None and claim.try_available():
            replayed, stored_hash, stored_role = claim.load_response(user_id, idempotency_key)
            if replayed is not None:
                if stored_hash and stored_hash != incoming_hash:
                    logger.warning(
                        "Idempotency payload mismatch (distributed): user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    return self._payload_mismatch_response()
                # Codex R3/R4 #3092: authorization + role binding before
                # cross-worker replay. Codex R6: the endpoint policy decides
                # on role change (same as the local-cache branch above).
                authorized, current_role, current_superuser = await self._principal_authorized(request, principal_payload)
                if not authorized:
                    logger.warning(
                        "Idempotency distributed replay refused (principal not authorized): user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    # Codex R8 #3092 (P1): неисполняющий отказ, снапшот хранится.
                    return _principal_refusal_response()
                permitted = self._role_permitted_for_replay(request, stored_role, current_role, current_superuser)
                if permitted is True or (
                    permitted is None and (stored_role is None or current_role == stored_role)
                ):
                    logger.info(
                        "Idempotency distributed replay: user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    return replayed
                if permitted is False:
                    # Endpoint policy refuses the current role — fall through
                    # to require_roles (403 + audit); snapshot KEPT (see the
                    # local-cache branch).
                    logger.warning(
                        "Idempotency distributed replay refused (endpoint policy): user=%s key=%s path=%s (stored=%s current=%s) — falling through",
                        user_id, idempotency_key, request.url.path, stored_role, current_role,
                    )
                    return await call_next(request)
                # permitted is None (policy unknown) AND role changed:
                # conservative R4 — drop the snapshot so this request
                # re-executes and re-stores with the fresh role.
                logger.warning(
                    "Idempotency distributed replay refused (role changed since execution, policy unknown): user=%s key=%s path=%s (%s -> %s) — re-executing",
                    user_id, idempotency_key, request.url.path, stored_role, current_role,
                )
                claim.forget_response(user_id, idempotency_key)
                _idempotency_cache.invalidate(user_id, idempotency_key)
                replayed = None
            claim_token = claim.acquire(user_id, idempotency_key)
            claim_acquired = claim_token is not None
            if not claim_acquired:
                # Another worker holds the claim. Its response may have
                # completed between our acquire attempt and now — re-check
                # before rejecting.
                replayed, stored_hash, stored_role = claim.load_response(user_id, idempotency_key)
                if replayed is not None:
                    if stored_hash and stored_hash != incoming_hash:
                        return self._payload_mismatch_response()
                    # Codex R4 #3092 (P1): the post-claim replay path runs the
                    # SAME authorization + role binding as the earlier branches —
                    # a revoked/deactivated principal must not receive
                    # the cached response here either. Codex R6: the endpoint
                    # policy decides on role change (snapshot KEPT on refusal).
                    # Codex R8 #3092 (P1): principal refusal is NON-EXECUTING.
                    authorized, current_role, current_superuser = await self._principal_authorized(request, principal_payload)
                    if not authorized:
                        logger.warning(
                            "Idempotency post-inflight replay refused (principal not authorized): user=%s key=%s path=%s",
                            user_id, idempotency_key, request.url.path,
                        )
                        return _principal_refusal_response()
                    permitted = self._role_permitted_for_replay(request, stored_role, current_role, current_superuser)
                    if permitted is False or (
                        permitted is None and stored_role is not None and current_role != stored_role
                    ):
                        logger.warning(
                            "Idempotency post-inflight replay refused (role not permitted): user=%s key=%s path=%s",
                            user_id, idempotency_key, request.url.path,
                        )
                        return await call_next(request)
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
                        '{"code": "idempotency_in_flight", "detail": "Request with this Idempotency-Key is '
                        'still being processed. Retry with the same key."}'
                    ),
                    media_type="application/json",
                )

        # Codex R6 #3092 (P1): establish the authorized role BEFORE execution —
        # the single DB authorization query of the execute path. Post-commit
        # the outcome is then retained UNCONDITIONALLY: the previous post-
        # commit re-check meant a transient DB failure after /registrar/cart
        # had already committed returned the 2xx WITHOUT any snapshot; the
        # claim expired after 90s and the lost-response retry re-executed the
        # cart, duplicating its billing and queue records.
        exec_authorized, exec_role, _exec_superuser = await self._principal_authorized(
            request, principal_payload
        )
        if not exec_authorized:
            # Fail-closed: nothing is stored or bound for an unauthorized
            # principal.
            # Codex R8 #3092 (P1): отказ принципала теперь НЕИСПОЛНЯЮЩИЙ —
            # прежний fall-through к эндпоинту исполнял команду для
            # деактивированного пользователя (require_roles не проверяет
            # is_active), коммитил корзину БЕЗ сохранения исхода — потерянный
            # ответ с тем же ключом дублировал визиты/счета/очередь.
            logger.warning(
                "Idempotency execute path refused pre-execution (principal not authorized): user=%s key=%s path=%s",
                user_id, idempotency_key, request.url.path,
            )
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                claim.release(user_id, idempotency_key, claim_token)
            return _principal_refusal_response()

        # Codex R9 #3092 (P1): reconcile-before-execute. The endpoint commits
        # the cart inside call_next while the idempotency OUTCOME is stored
        # only after the response materializes — a worker that dies in that
        # window loses its 90 s lease and the same-key retry re-executed the
        # write (duplicate visits/invoices/queue entries). A durable intent
        # marker is written BEFORE the handler runs: a retry that finds the
        # marker but NO stored response knows a previous attempt reached
        # execution with an UNKNOWN outcome and is refused (409) instead of
        # blindly re-executing. The registrar verifies the worklist and uses
        # a fresh key if nothing was applied — a safe no-op beats a duplicate.
        if claim is not None and claim.try_available():
            uncertain_outcome = claim.execution_intent_exists(user_id, idempotency_key)
        else:
            uncertain_outcome = _local_execution_intent_exists(user_id, idempotency_key)
        if uncertain_outcome:
            logger.warning(
                "Idempotency execution intent without a stored outcome (retry refused): user=%s key=%s path=%s",
                user_id, idempotency_key, request.url.path,
            )
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                claim.release(user_id, idempotency_key, claim_token)
            return self._uncertain_outcome_response()
        if claim is not None and claim.try_available():
            claim.mark_execution_intent(user_id, idempotency_key)
        else:
            _mark_local_execution_intent(user_id, idempotency_key)

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
            # Codex R9 #3092 (P1): the intent marker is KEPT — the crash may
            # have happened after the endpoint's commit, so the outcome stays
            # unknown and the retry must reconcile (409), not re-execute.
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
            # Codex R4 #3092 (P1): bind the stored response to the authorized
            # ROLE. Codex R6 #3092 (P1): the role was established BEFORE
            # execution — retain the committed outcome unconditionally (no
            # post-commit DB re-query to lose), the replay re-checks it.
            _idempotency_cache.set(user_id, idempotency_key, cached_response, incoming_hash, principal_role=exec_role)
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                # Codex R1 #3092 (P1): snapshot for CROSS-WORKER replay, then
                # drop the in-flight claim so later retries replay instead
                # of conflicting. Codex R2 #3092 (P1): the snapshot carries
                # the payload hash — changed data is never replayed as the
                # original success.
                claim.store_response(user_id, idempotency_key, cached_response, payload_hash=incoming_hash, principal_role=exec_role)
                claim.release(user_id, idempotency_key, claim_token)
            # Codex R9 #3092 (P1): outcome is now durable — drop the intent
            # marker so later same-key requests replay normally.
            if claim is not None and claim.try_available():
                claim.clear_execution_intent(user_id, idempotency_key)
            else:
                _clear_local_execution_intent(user_id, idempotency_key)
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
        # Codex R9 #3092 (P1): a RETURNED error response means the endpoint
        # completed its validation without a commit — the outcome is known
        # (nothing applied), so the intent marker is cleared and the
        # documented retry-after-fixing contract keeps working. (An exception
        # AFTER a commit surfaces as a crash above — there the marker is kept.)
        if claim is not None and claim.try_available():
            claim.clear_execution_intent(user_id, idempotency_key)
        else:
            _clear_local_execution_intent(user_id, idempotency_key)
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
                '{"code": "idempotency_payload_mismatch", "detail": "This Idempotency-Key was already used with a '
                'different request payload. The original data may already be '
                'saved — do not retry changed data with the same key; verify '
                'the record state first."}'
            ),
            media_type="application/json",
        )

    @staticmethod
    def _uncertain_outcome_response() -> Response:
        """409 for a retry whose previous attempt reached execution but left
        no known outcome (Codex R9 #3092 P1). Re-executing a cart write with
        an unknown outcome duplicates visits, invoices and queue entries; a
        conservative refusal turns the duplicate risk into a verifiable
        no-op: the registrar checks the worklist and retries with a NEW key
        only if nothing was applied."""
        return Response(
            status_code=409,
            headers={"Cache-Control": "no-store"},
            content=(
                '{"code": "idempotency_uncertain_outcome", "detail": "Предыдущая попытка с этим ключом Idempotency не '
                'завершилась корректно: результат неизвестен. Проверьте рабочий '
                'список — запись могла сохраниться. Если изменений нет, '
                'повторите операцию с НОВЫМ ключом Idempotency."}'
            ),
            media_type="application/json",
        )

    def _verified_principal(self, request: Request) -> dict[str, Any] | None:
        """Verify the bearer JWT and return its payload (Codex R3 #3092 P1).

        The payload's `sub` becomes the idempotency namespace. Returns None
        when the request carries no verifiable identity — such requests
        bypass idempotency entirely (nothing stored, nothing replayed).
        Codex R6 #3092 (P2): decoded with the SAME zero-leeway expiry policy
        as the canonical get_current_user dependency (deps.py) — the old 15s
        leeway let an already-expired bearer retrieve the PHI-bearing cached
        response before the endpoint dependency could reject it.
        """
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth_header:
            return None
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        try:
            from app.core.config import settings

            # No leeway — identical semantics to get_current_user's decode
            # (Codex R6 #3092 P2): an expired token is never a principal.
            return jwt.decode(
                token.strip(),
                settings.SECRET_KEY,
                algorithms=[getattr(settings, "ALGORITHM", "HS256")],
            )
        except Exception as exc:
            logger.debug("Idempotency: no verifiable principal (%s)", type(exc).__name__)
            return None

    @staticmethod
    def _namespace(canonical_user_id: int) -> str:
        """Stable per-principal cache namespace from the CANONICAL user id.

        Codex R11 #3092 (P1): the raw ``sub`` differs between token shapes
        (mobile login: sub=username; /mobile/auth/refresh: sub=user.id +
        username claim) — hashing it moved the same user's keys to another
        namespace after refresh. The namespace is derived from the DB-
        resolved user id, so every token shape of the same account maps to
        ONE namespace. Hashed: no usernames/ids in Redis keys.
        """
        subject = f"user:{int(canonical_user_id)}"
        return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:32]

    async def _principal_authorized(self, request: Request, principal_payload: dict[str, Any]) -> tuple[bool, str | None, bool]:
        """DB-backed authorization before any replay (Codex R3/R4/R6 #3092).

        Mirrors get_current_user's semantics: the user must exist, be active,
        and the token must not be blacklisted (jti or all-user sentinel).
        Returns (authorized, current_role, is_superuser) — the role lets the
        caller bind a stored response to the role it was authorized under,
        and both feed the endpoint-policy evaluation at replay (Codex R6:
        role changes do not revoke tokens; a role change between two roles
        the endpoint still authorizes must REPLAY, not re-execute).
        Runs the sync query in a worker thread; fails CLOSED — a broken DB
        check never results in a replay (the request falls through to the
        endpoint, which re-authenticates anyway).

        Codex R9 #3092 (P1): the SUBJECT SELECTION mirrors deps.py exactly —
        canonical 2FA tokens carry BOTH a numeric ``sub`` and a ``username``
        claim, and get_current_user resolves the account through
        _subject_from_payload, which PREFERS the username claim (numeric
        text subject → by id, else by username). Resolving only by the
        numeric sub authorized replays for a registrar the endpoint itself
        would refuse (e.g. after an admin rename the username no longer
        exists → endpoint 401) — a cached PHI-bearing cart response could be
        replayed under a token the canonical dependency rejects.
        """
        user_id, username = _user_id_from_principal(principal_payload)
        jti = principal_payload.get("jti")
        try:
            return await asyncio.to_thread(
                _check_principal_authorized_sync, request, user_id, username, jti
            )
        except Exception:  # pragma: no cover - to_thread failure is fail-closed
            logger.warning("Idempotency principal check crashed; refusing replay", exc_info=True)
            return False, None, False

    @staticmethod
    def _endpoint_allowed_roles(request: Any) -> frozenset[str] | None:
        """Resolve the endpoint's require_roles policy (Codex R6 #3092 P1).

        Returns the lowercase role labels the matched route accepts:
        - empty frozenset: the route carries no require_roles dependency —
          any authenticated principal is authorized (require_roles itself
          authorizes exactly these roles, superusers, and is silent for
          routes that never called it);
        - None: the policy could NOT be determined (no app in scope, no
          matching route) — callers fall back to the conservative R4
          role-label comparison.

        The roles come from the `required_roles` attribute that the SSOT
        require_roles factory publishes on its dependency callable — the
        middleware reads the policy, it never re-implements it.
        """
        try:
            scope = getattr(request, "scope", None) or {}
            app = scope.get("app")
            if app is None:
                return None
            from starlette.routing import Match

            for route in getattr(getattr(app, "router", None), "routes", None) or []:
                try:
                    result = route.matches(scope)
                    match = result[0] if isinstance(result, tuple) else result
                except Exception:  # pragma: no cover - exotic route objects
                    continue
                if match != Match.FULL:
                    continue
                dependant = getattr(route, "dependant", None)
                if dependant is None:
                    return None
                allowed: set[str] = set()
                for dep in getattr(dependant, "dependencies", []) or []:
                    roles = getattr(getattr(dep, "call", None), "required_roles", None)
                    if roles:
                        allowed.update(str(r).strip().lower() for r in roles)
                return frozenset(allowed)
        except Exception:  # pragma: no cover - never let policy lookup replay
            logger.warning("Idempotency endpoint policy lookup failed", exc_info=True)
            return None
        return None

    def _role_permitted_for_replay(
        self,
        request: Request,
        stored_role: str | None,
        current_role: str | None,
        is_superuser: bool,
    ) -> bool | None:
        """Codex R6 #3092 (P1): evaluate the ENDPOINT policy on role change.

        R4 refused every replay whose role label differed from the stored
        one. That over-blocks /registrar/cart, which accepts BOTH Admin and
        Registrar: an Admin→Registrar (or Registrar→Admin) change after a
        committed request whose response was lost evicted the snapshot and
        the authorized retry re-executed the cart — duplicate visits,
        invoices and queue entries.

        True  — the endpoint policy still authorizes the principal
                (superuser bypass, no require_roles dependency, or the
                current role in the endpoint's allowed set): keep the
                committed snapshot and replay.
        False — the policy refuses the current role: do NOT replay (the
                endpoint's require_roles will 403 + audit exactly as it
                would for a fresh request). The snapshot is KEPT — when the
                principal regains an allowed role, the retry replays again
                instead of re-executing the write.
        None  — policy unknown: fall back to the conservative R4 exact
                role-label comparison (caller decides).
        """
        if is_superuser:
            return True
        allowed = self._endpoint_allowed_roles(request)
        if allowed is None:
            return None
        if not allowed:
            return True
        if not current_role:
            return False
        return current_role.strip().lower() in allowed
