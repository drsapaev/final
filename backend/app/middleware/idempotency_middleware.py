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
import heapq
import json
import logging
import re
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

# Round-5 (owner P1, PR #3340): tri-state outcome of a distributed scope
# binding read. RESOLVED means Redis ANSWERED — the returned scope is the
# key's effective binding (existing or freshly NX-written). UNAVAILABLE
# means the identity is UNKNOWN: Redis unreachable, an op failed, or the
# NX-then-re-read could not confirm a binding. The caller must treat these
# differently — an absent binding may be created, an UNRESOLVED one must
# never be invented locally.
_SCOPE_BINDING_RESOLVED = "resolved"
_SCOPE_BINDING_UNAVAILABLE = "unavailable"

# Round-8 (owner P1, PR #3340): sentinel for the local atomic-entry writer —
# "keep the snapshot the entry already holds". A plain ``None`` now EXPLICITLY
# removes a stored snapshot (role-changed re-execution); an OMITTED argument
# no longer silently wipes a live local outcome — the Redis→local binding
# mirror used to do exactly that with the old unconditional tuple replace.
_SNAPSHOT_UNCHANGED: Any = object()

# Max entries to prevent unbounded memory growth
_MAX_CACHE_ENTRIES = 10_000

# Round-6 (owner P1, PR #3340): the Idempotency-Key header is caller-owned
# and unbounded otherwise — a flood of unique 10k-char keys allocated memory
# in the middleware, Redis and the scope-binding mirror for every request
# BEFORE any endpoint validation could refuse it. 128 chars covers every
# real generator (uuid4 hex = 32, ULID = 26) while bounding key material.
_IDEMPOTENCY_KEY_MAX_LENGTH = 128

# Round-6 (owner P1, PR #3340): the in-process scope-binding mirror is
# attacker-reachable (every keyed request with a fresh key creates an entry
# BEFORE endpoint validation), so it is a bounded LRU — the response cache
# bound above, same budget.
_MAX_SCOPE_BINDING_ENTRIES = 10_000

# Codex R2 #3092 (P2): the in-flight claim is a SHORT renewable lease, not
# the response TTL. If a worker dies mid-request, same-key retries receive
# 409 only until the lease lapses (seconds), after which the operation may
# re-run — the response was never stored, so no cached success is lost.
_IN_FLIGHT_LEASE_SECONDS = 90

# Round-8 (owner P2, PR #3340): the user-only legacy bridge (migration fence,
# legacy replay and the every-success dual-write) is bounded by a rollout
# window. Left unbounded, a staff client reusing one key across TWO different
# POST operations collides in the user-only namespace forever (payload
# mismatch for another operation's body, or another operation's response
# replayed outright). The window covers the old workers' drain plus the
# legacy response TTL (24 h) they may have left behind; after it lapses the
# middleware consults ONLY the operation-scoped namespace.
# IDEMPOTENCY_LEGACY_BRIDGE_MAX_AGE_SECONDS overrides the window (0 disables
# the bridge immediately).
_LEGACY_BRIDGE_DEFAULT_MAX_AGE_SECONDS = (
    _CACHE_TTL_SECONDS + _IN_FLIGHT_LEASE_SECONDS + 3600
)
_LEGACY_BRIDGE_EPOCH = time.time()


def _legacy_bridge_active() -> bool:
    """True while the user-only legacy reconciliation may run (Round-8)."""
    try:
        from app.core.config import settings

        max_age = float(
            getattr(
                settings,
                "IDEMPOTENCY_LEGACY_BRIDGE_MAX_AGE_SECONDS",
                _LEGACY_BRIDGE_DEFAULT_MAX_AGE_SECONDS,
            )
        )
    except Exception:  # pragma: no cover - settings not initialized (tests)
        max_age = _LEGACY_BRIDGE_DEFAULT_MAX_AGE_SECONDS
    if max_age <= 0:
        return False
    return (time.time() - _LEGACY_BRIDGE_EPOCH) < max_age


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
# Махмудбек R18 #3277 (P2): compare-and-delete для intent-маркера. Значением
# маркера является токен попытки-владельца (mark_execution_intent), поэтому
# отказная попытка может убрать СОБСТВЕННЫЙ маркер и только его: маркер другой
# попытки с неизвестным исходом (защита R9) не задевается.
_INTENT_RELEASE_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


# Review #3283: checking the lease and recording intent must be ONE
# Redis operation. A paused worker must not overwrite another attempt's
# unknown outcome and subsequently delete it as its own failed write.
_INTENT_MARK_LUA = (
    "if redis.call('get', KEYS[1]) ~= ARGV[1] then return -1 end "
    "local existing = redis.call('get', KEYS[2]); "
    "if existing and existing ~= ARGV[1] then return -2 end "
    "redis.call('set', KEYS[2], ARGV[1], 'EX', ARGV[2]); return 1"
)

# PR 3319: the value written by the tokenless (optional-degrade) branch of
# mark_execution_intent. The known-outcome cleanup of a degraded attempt
# compares against this value, so it can only ever delete the anonymous
# marker its own SET NX inserted — never a foreign attempt's token-bound
# unknown-outcome marker (R9).
_TOKENLESS_INTENT_VALUE = "1"

# ── Round-8 (owner P1 #2 + P2, PR #3340): scope-binding value protocol ──────
#
# The distributed binding value is "<patient_scope>|<attempt-generation>".
# The generation binds DELETION rights to the attempt that wrote the value:
# a known non-2xx cleanup is an atomic compare-and-delete of the FULL value,
# so a successor attempt that re-asserted the binding under ITS generation
# (post-acquire) can never have its in-flight binding deleted by the stale
# attempt's cleanup (the round-7 GET+DELETE twin deleted by scope alone —
# and A/B share the same scope value, so the guard could not tell the
# generations apart).


def _scope_binding_value(patient_scope: str, generation: str) -> str:
    return f"{patient_scope}|{generation}"


def _scope_from_binding_value(value: str) -> str:
    """The patient scope component of a binding value (generation stripped).

    Values written before the generation protocol (no delimiter) degrade to
    the whole string — the scope is the identity, the generation only gates
    deletion rights."""
    scope, _sep, _generation = value.partition("|")
    return scope


# Restore-or-refresh, value-guarded: an ABSENT binding is re-created (the
# successor's post-acquire re-assert and the success-path extension must
# survive a stale attempt's in-between cleanup), a SAME-scope binding is
# refreshed with the caller's generation, a FOREIGN scope is never touched.
_SCOPE_UPSERT_LUA = (
    "-- scope-upsert\n"
    "local v = redis.call('get', KEYS[1]); "
    "if v and (string.sub(v, 1, string.len(ARGV[1])) ~= ARGV[1] "
    "or string.sub(v, string.len(ARGV[1]) + 1, string.len(ARGV[1]) + 1) ~= '|') "
    "then return 0 end "
    "redis.call('set', KEYS[1], ARGV[2], 'EX', ARGV[3]); return 1"
)

# Known non-2xx cleanup: delete ONLY the binding value THIS attempt wrote
# (full compare-and-delete on scope AND generation).
_SCOPE_CAS_DELETE_LUA = (
    "-- scope-cas-delete\n"
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

# Success path for patient operations: the response snapshot and the
# scope-binding extension are ONE script. The binding can then never expire
# before the outcome it guards (the owner's P2 relink window: response
# stored at T1, binding expiring at T0+24h < T1+24h). Return 1 = response
# stored AND binding extended/restored; 2 = response stored but the binding
# holds a FOREIGN scope (never overwritten — the outcome is not treated as
# durable); transport failure reports (False, False).
_STORE_RESPONSE_WITH_SCOPE_LUA = (
    "-- store+scope\n"
    "redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2]); "
    "local v = redis.call('get', KEYS[2]); "
    "if v and (string.sub(v, 1, string.len(ARGV[3])) ~= ARGV[3] "
    "or string.sub(v, string.len(ARGV[3]) + 1, string.len(ARGV[3]) + 1) ~= '|') "
    "then return 2 end "
    "redis.call('set', KEYS[2], ARGV[4], 'EX', ARGV[2]); return 1"
)


class _IntentClaimLost(RuntimeError):
    """Redis positively refused a stale owner or a foreign intent."""


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
    db: Any,
    user_id: int | None,
    username: str | None,
    jti: Any,
    require_active_doctor_profile: bool = False,
) -> tuple[bool, str | None, bool]:
    """Pure DB-backed authorization query — fails CLOSED (Codex R3/R4 #3092).

    Same semantics as app.api.deps._get_user_with_blacklist, plus the role:
    the user must exist, be active, and the token must not be blacklisted
    (jti match or the all_user_tokens sentinel). One SQL roundtrip.
    Returns (authorized, role, is_superuser) — the role binds stored
    responses to the RBAC policy they were produced under (Codex R4 #3092
    P1); is_superuser lets the replay evaluate require_roles' superuser
    bypass exactly as the endpoint would (Codex R6 #3092 P1).

    Codex R15 #3092 (P1): ``require_active_doctor_profile=True`` (REPLAY
    paths) additionally verifies an ACTIVE Doctor profile for the
    principal. Inline-auth routes (queue.py) re-run this resource
    authorization on every fresh request, but the replay path previously
    trusted the role label alone: a deactivated Doctor profile left the
    role label unchanged and the middleware replayed the PHI-bearing
    snapshot the endpoint would now refuse. The profile check mirrors
    queue.py:69-79 (Doctor.user_id + Doctor.active); per-entry queue
    ownership stays endpoint-level — the middleware cannot resolve the
    request's resource.
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
        subject_id, is_active, role, is_superuser, jti_hit, sentinel_hit = row
        role_label = str(role) if role is not None else None
        authorized = bool(is_active) and not (jti_hit or sentinel_hit)
        if authorized and require_active_doctor_profile and role_label == "Doctor":
            from app.models.clinic import Doctor

            has_active_profile = (
                db.query(Doctor.id)
                .filter(
                    Doctor.user_id == int(subject_id),
                    Doctor.active.is_(True),
                )
                .first()
            ) is not None
            if not has_active_profile:
                logger.warning(
                    "Idempotency replay refused (Doctor profile inactive): user=%s",
                    subject_id,
                )
                return False, role_label, bool(is_superuser)
        return authorized, role_label, bool(is_superuser)
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


def _normalize_idem_path(path: str) -> str:
    """Round-3 (owner P2): path normalization for the operation scope.

    Trailing slashes are collapsed ("/cart/" == "/cart"), everything else
    stays byte-exact — paths are routing-identity and must not alias.
    """
    return re.sub(r"/+$", "", path) or "/"


def _audit_keyed_patient_refusal(
    request: Any, subject_patient_id: int, canonical_user_id: int
) -> None:
    """Round-5 (owner P2): denied PHI-audit row for a middleware refusal.

    POST /patients/booking REQUIRES an Idempotency-Key, so a keyed request
    is decided by THIS middleware before any endpoint dependency runs —
    the round-4 audited principal factory never executes on a refusal
    path, and the linked card's PHI trail lost the attempt. This writes
    the SAME row contract the portal's audited dependency produces
    (``outcome="denied"``, machine ``reason`` + ``surface: jwt_portal``
    in extra_data, the linked card as subject and actor) directly through
    the shared audit SSOT. Non-blocking by contract: an audit failure
    never changes the refusal itself.

    Resource mapping: the only keyed patient surface in #3340 is the
    booking create (appointment/create, matching the endpoint's own
    factory); future keyed patient surfaces fall back to the honest
    generic (patient_portal/access) instead of a wrong resource label.
    """
    path = getattr(getattr(request, "url", None), "path", "") or ""
    if path.rstrip("/").endswith("booking"):
        resource_type, action = "appointment", "create"
    else:
        resource_type, action = "patient_portal", "access"
    try:
        generator = _resolve_request_db(request)
        try:
            db = next(generator)
            from app.services.patient_access_audit import log_patient_access
            from app.services.telegram_mini_app_init_data import (
                TelegramMiniAppSessionScope,
            )

            log_patient_access(
                db,
                scope=TelegramMiniAppSessionScope(
                    scope_type="patient",
                    telegram_user_id=None,
                    telegram_chat_id=None,
                    patient_id=int(subject_patient_id),
                ),
                resource_type=resource_type,
                action=action,
                outcome="denied",
                request=request,
                extra_data={"reason": "user_deactivated", "surface": "jwt_portal"},
            )
        finally:
            try:
                next(generator)
            except StopIteration:
                pass
            except Exception:  # pragma: no cover - generator teardown
                pass
    except Exception:
        logger.warning(
            "Idempotency denied-audit write failed for a deactivated patient "
            "(keyed request); refusing without an audit row",
            exc_info=True,
        )


def _patient_replay_policy_sync(
    request: Any, canonical_user_id: int
) -> tuple[str, bool, bool | None]:
    """Round-3 (owner P1): patient-aware replay policy, one DB roundtrip.

    Returns ``(patient_scope, fall_through, user_is_active)``:

    - non-Patient principal (or user row gone — later exec-auth refuses
      fail-closed): ``("", False, None)`` — namespace carries NO patient
      scope;
    - Patient with an ACTIVE card: ``("patient:{id}", False, is_active)``
      — the namespace (local cache, Redis claim, execution intents) is
      bound to the CURRENT card id, so a snapshot made under card A can
      never be served after the account is re-linked to card B;
    - Patient with a MISSING or SOFT-DELETED card: ``("", True, None)``
      — the caller falls through to the endpoint WITHOUT any idempotency
      machinery: no cached snapshot, no claim, no intent. The endpoint's
      own guards answer 404 patient_profile_required / 403
      patient_link_invalid (and write the denied audit row) exactly as
      they would for a first request. Replaying a committed booking to a
      revoked card is precisely the leak this policy closes.

    Round-5 (owner P2): ``User.is_active`` is now part of the SAME query.
    A DEACTIVATED account with a live card is refused HERE — the keyed
    request must never reach the binding/claim machinery (and through it
    the later non-auditing exec-auth refusal). The denied audit row is
    written in this same DB pass (see ``_audit_keyed_patient_refusal``);
    the dispatch then answers the non-executing 403.
    """
    generator = _resolve_request_db(request)
    try:
        db = next(generator)
        from sqlalchemy import select

        from app.models.patient import Patient
        from app.models.user import User

        row = db.execute(
            select(User.role, Patient.id, Patient.is_deleted, User.is_active)
            .outerjoin(Patient, Patient.user_id == User.id)
            .where(User.id == int(canonical_user_id))
        ).first()
        if row is None:
            return "", False, None
        role, patient_id, is_deleted, user_is_active = row
        if str(role or "").strip().casefold() != "patient":
            return "", False, None
        if patient_id is None or bool(is_deleted):
            return "", True, None
        user_is_active = bool(user_is_active)
        if not user_is_active:
            _audit_keyed_patient_refusal(request, int(patient_id), canonical_user_id)
        return f"patient:{int(patient_id)}", False, user_is_active
    finally:
        try:
            next(generator)
        except StopIteration:
            pass
        except Exception:  # pragma: no cover - generator teardown
            pass


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
    request: Any,
    user_id: int | None,
    username: str | None,
    jti: Any,
    require_active_doctor_profile: bool = False,
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
            return _user_authorized_in_db(
                db, user_id, username, jti,
                require_active_doctor_profile=require_active_doctor_profile,
            )
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


# ── Round-4 (owner P1, PR #3340): in-process mirror of the patient-scope ────
# binding. The idempotency key's ORIGINAL patient card is bound the first
# time the keyed operation runs and never follows a re-link. The durable
# binding lives in the distributed claim (Redis); this mirror follows the
# same pattern as the execution-intent markers for the Redis-degraded path.
#
# Round-7 (owner P1 #2, PR #3340): the binding and the LOCAL response
# snapshot are ONE entry — ``(expires_at, patient_scope, snapshot)`` keyed
# by the ORIGIN namespace (user + operation, no card scope) — so they share
# LRU fate by construction. The round-6 layout kept them in two independent
# caches (binding under the origin ns, response under the card-scoped ns):
# an LRU eviction of the binding left a live response invisible to the
# relink-refusal and let a re-linked card re-bind the key and execute a
# second write. The structure is exactly the owner-mandated one:
#
#     (origin user + operation + key)
#         → patient_scope
#         → payload_hash
#         → response snapshot
#
# Eviction can now only remove scope AND snapshot together — a live response
# is never re-executable under a different card. For patient-scope
# operations this entry REPLACES the per-process response cache as the
# local replay source; the distributed layer keeps its own (unchanged)
# Redis layout and remains the durable record.
_local_scope_bindings: OrderedDict[tuple[str, str], tuple[float, str, tuple[int, dict[str, str], bytes, str | None, str, str | None] | None]] = OrderedDict()

# Round-7 (owner P2, PR #3340): lazy expiry index for the bounded mirror —
# a min-heap of (expires_at, cache_key). The per-op cost is O(1) amortized:
# the purge peeks the nearest known expiry and stops immediately when it is
# still live; stale records (overwritten / LRU-evicted keys) are discarded
# on sight. Each pushed record is popped at most once, so a flood of unique
# keys pays O(log N) amortized instead of the round-6 full O(N) sweep per
# set() once the bound was reached.
_local_scope_bindings_expiry: list[tuple[float, tuple[str, str]]] = []


def _local_scope_binding_purge_expired(budget: int = 32) -> None:
    """Reclaim up to ``budget`` expired entries incrementally (O(1) peek in
    the common case). Never raises; never scans the whole store."""
    now = time.time()
    for _ in range(budget):
        if not _local_scope_bindings_expiry:
            return
        expires_at, cache_key = _local_scope_bindings_expiry[0]
        entry = _local_scope_bindings.get(cache_key)
        if entry is None or entry[0] != expires_at:
            # Stale heap record: the key was overwritten (fresh TTL) or
            # evicted by the LRU bound after this record was pushed.
            heapq.heappop(_local_scope_bindings_expiry)
            continue
        if expires_at > now:
            return  # nearest live expiry is in the future — done
        heapq.heappop(_local_scope_bindings_expiry)
        _local_scope_bindings.pop(cache_key, None)


def _local_scope_binding_get(origin_ns: str, key: str) -> str | None:
    """O(1): only THIS entry's TTL is examined (plus LRU re-ordering)."""
    cache_key = (str(origin_ns), key)
    entry = _local_scope_bindings.get(cache_key)
    if entry is None:
        return None
    if entry[0] <= time.time():
        _local_scope_bindings.pop(cache_key, None)
        return None
    _local_scope_bindings.move_to_end(cache_key)
    return entry[1]


def _local_scope_binding_mirror(origin_ns: str, key: str, patient_scope: str) -> None:
    """Round-8 (owner P1, PR #3340): mirror a Redis-RESOLVED binding into the
    local store WITHOUT destroying a locally stored response snapshot.

    The dispatch mirrors the binding on EVERY same-key retry whose scope GET
    succeeds — including the retry that was about to replay the LOCAL
    snapshot because Redis died on the next response GET. The previous
    unconditional tuple replace wiped the snapshot to None at exactly that
    moment, the local replay source vanished, and the next degraded retry
    re-executed the handler. The sentinel-based set keeps the snapshot."""
    _local_scope_binding_set(origin_ns, key, patient_scope)


def _local_scope_binding_set(
    origin_ns: str,
    key: str,
    patient_scope: str,
    snapshot: (
        tuple[int, dict[str, str], bytes, str | None, str, str | None]
        | None
        | Any
    ) = _SNAPSHOT_UNCHANGED,
) -> None:
    """Round-7 (owner P1 #2 + P2, PR #3340): bounded O(1)-per-op store.

    Overflow is resolved by an immediate LRU popitem — no full sweep on the
    hot path. TTL hygiene is the lazy expiry heap above (incremental,
    bounded budget per op). ``snapshot`` attaches the outcome atomically:
    the binding and its response share one entry and one TTL.

    Round-8 (owner P1, PR #3340): the default is the ``_SNAPSHOT_UNCHANGED``
    sentinel — a call that only (re)binds the scope PRESERVES the snapshot
    the entry already holds (guarded by the scope: a foreign scope never
    inherits a foreign outcome). An explicit ``snapshot=None`` REMOVES a
    stored snapshot (role-changed re-execution path)."""
    cache_key = (str(origin_ns), key)
    expires_at = time.time() + _CACHE_TTL_SECONDS
    if snapshot is _SNAPSHOT_UNCHANGED:
        existing = _local_scope_bindings.get(cache_key)
        if existing is not None and existing[1] == patient_scope:
            snapshot = existing[2]
        else:
            snapshot = None
    _local_scope_bindings[cache_key] = (expires_at, patient_scope, snapshot)
    _local_scope_bindings.move_to_end(cache_key)
    heapq.heappush(_local_scope_bindings_expiry, (expires_at, cache_key))
    _local_scope_binding_purge_expired()
    while len(_local_scope_bindings) > _MAX_SCOPE_BINDING_ENTRIES:
        _local_scope_bindings.popitem(last=False)
    if len(_local_scope_bindings_expiry) > 2 * len(_local_scope_bindings) + 64:
        # Amortized compaction: LRU-evicted keys leave heap records behind
        # that would otherwise linger until their (future) expiry reaches
        # the top. Rebuilding from the live entries costs O(N) but only
        # fires after ~N/2 further inserts — O(1) amortized, and the heap
        # can never grow unboundedly past the bounded store.
        compact = [
            (entry[0], live_key)
            for live_key, entry in _local_scope_bindings.items()
        ]
        heapq.heapify(compact)
        _local_scope_bindings_expiry[:] = compact


def _local_patient_outcome_get(
    origin_ns: str, key: str, incoming_hash: str | None
) -> tuple[Response | None, bool, str | None]:
    """Local replay source for patient-scope operations (Round-7 owner P1 #2).

    Reads the ATOMIC binding entry: ``(response, payload_mismatch,
    bound_role)`` — the same contract as ``IdempotencyResponseCache.get``.
    A missing/absent snapshot degrades to a plain miss; the scope itself is
    consumed by the binding-resolution flow before any replay happens."""
    cache_key = (str(origin_ns), key)
    entry = _local_scope_bindings.get(cache_key)
    if entry is None:
        return None, False, None
    expires_at, _scope, snapshot = entry
    if expires_at <= time.time():
        _local_scope_bindings.pop(cache_key, None)
        return None, False, None
    _local_scope_bindings.move_to_end(cache_key)
    if snapshot is None:
        return None, False, None
    status, headers, body, media_type, stored_hash, stored_role = snapshot
    mismatch = bool(incoming_hash and stored_hash and incoming_hash != stored_hash)
    response = Response(
        content=body,
        status_code=status,
        headers=dict(headers),
        media_type=media_type,
    )
    return response, mismatch, stored_role


def _local_patient_outcome_store(
    origin_ns: str,
    key: str,
    patient_scope: str,
    response: Response,
    payload_hash: str,
    principal_role: str | None,
) -> None:
    """Store the committed patient outcome ATOMICALLY with its binding
    (Round-7 owner P1 #2, fix c).

    One upsert refreshes the TTL, records the scope and attaches the
    snapshot — restoring a binding that concurrent traffic evicted while
    the handler was running. After this call the key's card identity and
    its replayable outcome can no longer diverge in the local mirror."""
    body = getattr(response, "body", b"") or b""
    snapshot = (
        response.status_code,
        dict(response.headers),
        body,
        response.media_type,
        payload_hash,
        principal_role,
    )
    _local_scope_binding_set(origin_ns, key, patient_scope, snapshot)


def _local_patient_outcome_forget_snapshot(
    origin_ns: str, key: str, patient_scope: str
) -> None:
    """Drop ONLY the stored snapshot (role-changed re-execution path) while
    keeping the binding alive — the card identity is unchanged and must
    keep guarding the key. Value-guarded like every binding writer; the
    explicit ``snapshot=None`` is the Round-8 sentinel contract for an
    intentional removal."""
    cache_key = (str(origin_ns), key)
    entry = _local_scope_bindings.get(cache_key)
    if entry is not None and entry[1] == patient_scope:
        _local_scope_binding_set(origin_ns, key, patient_scope, snapshot=None)


def _local_scope_binding_drop(origin_ns: str, key: str, patient_scope: str) -> None:
    """Delete the binding of a KNOWN non-2xx outcome (Round-7 owner P1 #2,
    fix d). Value-guarded: a foreign binding is never touched. The lazy
    expiry heap discards the orphaned record on its next peek."""
    cache_key = (str(origin_ns), key)
    entry = _local_scope_bindings.get(cache_key)
    if entry is not None and entry[1] == patient_scope:
        _local_scope_bindings.pop(cache_key, None)


def get_idempotency_cache() -> IdempotencyResponseCache:
    return _idempotency_cache


def _decode_response_snapshot(raw: Any) -> tuple[Response | None, str | None, str | None]:
    """Decode a stored response snapshot (shared by load_response and the
    round-4 legacy probe). Never raises: a corrupt snapshot degrades to a
    miss instead of failing the request."""
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
      - Codex R7 #3092 (P1): best-effort degraded to FAIL-CLOSED for keyed
        writes. When the deployment explicitly requires coordination
        (IDEMPOTENCY_REDIS_URL) and Redis is unreachable, keyed writes are
        refused (503 idempotency_unavailable) instead of executing on the
        per-process cache — a duplicate visit/invoice is worse than a retry.
        Deployments WITHOUT an explicit idempotency URL keep the original
        in-memory degrade (dev, tests, single-worker installs).
    """

    # Class-level defaults keep object.__new__-built instances (tests) valid.
    _lease_seconds: int = _IN_FLIGHT_LEASE_SECONDS
    _failed_at: float = 0.0
    # Codex R7 #3092 (P1): True when the deployment EXPLICITLY configured
    # idempotency coordination (IDEMPOTENCY_REDIS_URL) — then a Redis outage
    # must fail closed (503) instead of silently degrading to per-process
    # memory, because two staging workers would execute the same keyed write
    # concurrently and duplicate visits/invoices/queue entries.
    _required: bool = False
    # Round-5 (owner P1, PR #3340): True once Redis has ANSWERED at least
    # once in this worker's lifetime. While it is False the process has
    # never seen a reachable Redis, so no binding can exist "only in Redis"
    # from THIS worker's point of view and the per-process mirror is the
    # legitimate coordination SSOT (the no-Redis / ARQ-fallback contract).
    # Once True, a degraded Redis hides bindings that may exist ONLY there
    # — an unknown-scope keyed request must then refuse conservatively.
    _ever_available: bool = False

    def __init__(self, redis_url: str, ttl: int = _CACHE_TTL_SECONDS, lease_seconds: int = _IN_FLIGHT_LEASE_SECONDS, required: bool = False) -> None:
        self._ttl = ttl
        self._lease_seconds = lease_seconds
        self._required = required
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
            self._ever_available = True
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

    @property
    def required(self) -> bool:
        """Codex R7 #3092 (P1): coordination is REQUIRED by deployment config."""
        return self._required

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
            self._ever_available = True
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
          - None: the claim is held elsewhere (409 to the client), the Redis
            op failed, or coordination is unavailable — every None outcome is
            FAIL-CLOSED (Codex R7 #3092 (P1): the previous synthetic
            "local-*" token let two workers execute the same keyed write
            concurrently during a Redis outage, duplicating visits/invoices;
            refusal is the safe answer — the client retries with the same
            key once coordination recovers).
        """
        if not self._ensure_available() or self._client is None:
            return None  # Codex R7 #3092 (P1): fail closed, never "proceed locally"
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
        return _decode_response_snapshot(raw)

    def store_response(self, user_id: int | str, key: str, response: Response, ttl: int | None = None, payload_hash: str = "", principal_role: str | None = None, operation_scope: str | None = None) -> bool:
        """Store the outcome snapshot and REPORT whether Redis confirmed it.

        Round-7 (owner P1, PR #3340): the previous contract returned ``None``
        for BOTH a confirmed write and a swallowed transport failure, so the
        caller could not tell whether the durable snapshot had actually
        replaced the pre-execution intent marker. A Redis death ON the
        ``store_response`` call then let the success path delete the intent
        markers while NO snapshot existed anywhere — after the legacy fence
        lease lapsed, an old-version worker saw an empty legacy namespace and
        re-executed the committed write.

        Round-8 (owner P2, PR #3340): ``operation_scope`` stamps the snapshot
        with the operation it was produced by (method + path). The user-only
        legacy namespace mixes operations under one key — the stamp is what
        lets the legacy replay skip another operation's snapshot instead of
        refusing it as a payload mismatch or replaying it outright.

        Returns True only when Redis ANSWERED the SET; False on a degraded
        transport. Callers gate their intent-marker cleanup on it."""
        if not self._ensure_available() or self._client is None:
            return False
        body = getattr(response, "body", b"") or b""
        snapshot_payload: dict[str, Any] = {
            "status": response.status_code,
            "headers": dict(response.headers),
            "media_type": response.media_type,
            "body_b64": base64.b64encode(body).decode("ascii"),
            "payload_hash": payload_hash,
            "principal_role": principal_role,
        }
        if operation_scope:
            snapshot_payload["operation_scope"] = operation_scope
        snapshot = json.dumps(snapshot_payload)
        stored = self._run(
            self._client.set,
            self._resp_key(user_id, key),
            snapshot,
            ex=ttl or self._ttl,
        )
        return bool(stored)

    def store_response_with_scope(
        self,
        user_id: int | str,
        key: str,
        response: Response,
        payload_hash: str = "",
        principal_role: str | None = None,
        operation_scope: str | None = None,
        origin_ns: str = "",
        patient_scope: str = "",
        generation: str = "",
        ttl: int | None = None,
    ) -> tuple[bool, bool]:
        """Store the outcome snapshot AND extend the scope binding ATOMICALLY
        (Round-8 owner P2, PR #3340 — patient operations only).

        The binding is written at T0 (before the handler) and the response
        at T1 (after it); with independent TTLs the binding always expired
        FIRST, and a Redis failure inside the separate extend left a response
        that outlived its guard by exactly the handler duration — the window
        in which a re-linked card could re-bind the key and execute a second
        write. One script now stores the snapshot and restores-or-refreshes
        the binding under THIS attempt's generation, or stores nothing:

        Returns ``(response_stored, scope_extended)`` — (True, True) when
        Redis confirmed both; (True, False) when the response landed but the
        binding holds a FOREIGN scope (never overwritten); (False, False)
        on a degraded transport. The caller counts the patient outcome
        durable only when BOTH are True."""
        if not self._ensure_available() or self._client is None:
            return False, False
        body = getattr(response, "body", b"") or b""
        snapshot_payload: dict[str, Any] = {
            "status": response.status_code,
            "headers": dict(response.headers),
            "media_type": response.media_type,
            "body_b64": base64.b64encode(body).decode("ascii"),
            "payload_hash": payload_hash,
            "principal_role": principal_role,
        }
        if operation_scope:
            snapshot_payload["operation_scope"] = operation_scope
        snapshot = json.dumps(snapshot_payload)
        result = self._run(
            self._client.eval,
            _STORE_RESPONSE_WITH_SCOPE_LUA,
            2,
            self._resp_key(user_id, key),
            self._scope_key(origin_ns, key),
            snapshot,
            str(ttl or self._ttl),
            patient_scope,
            _scope_binding_value(patient_scope, generation),
        )
        if result == 1:
            return True, True
        if result == 2:
            # The response is stored, but the binding was re-bound by a
            # foreign scope in the meantime — it is never overwritten, and
            # the outcome is NOT treated as durable (the mismatch refusal
            # guards the orphaned snapshot instead).
            return True, False
        return False, False

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

    # ── Round-4 (owner P1, PR #3340): stable patient-scope binding ─────────
    #
    # The binding lives under the ORIGIN namespace (canonical user +
    # operation, WITHOUT the patient scope) — the one identity that survives
    # re-linking the account to another card. The value records the patient
    # scope (``patient:{id}``) the key FIRST ran under; a retry whose CURRENT
    # card differs is refused (409 idempotency_scope_mismatch) instead of
    # executing the same booking attempt for a different patient.

    @staticmethod
    def _scope_key(user_id: int | str, key: str) -> str:
        return f"idem:{user_id}:{key}:pscope"

    def load_scope_binding(self, origin_ns: str, key: str) -> str | None:
        """The patient scope this key was first bound to (None if unbound).

        Round-8: the stored value carries the owning attempt's generation
        (``scope|generation``) — only the scope component is returned."""
        if not self._ensure_available() or self._client is None:
            return None
        stored = self._run(self._client.get, self._scope_key(origin_ns, key))
        return _scope_from_binding_value(str(stored)) if stored else None

    def bind_scope_if_absent(
        self, origin_ns: str, key: str, patient_scope: str, generation: str
    ) -> tuple[str, str | None]:
        """Bind the key's FIRST patient scope; report the EFFECTIVE binding.

        Round-5 (owner P1): the result is a TRI-STATE — ``absent`` and
        ``failed`` are different states and the caller must not conflate
        them. ``(SCOPE_BINDING_RESOLVED, scope)`` means Redis ANSWERED:
        either the existing binding (which always wins: GET before the SET
        NX) or our own NX write confirmed by the re-read.
        ``(SCOPE_BINDING_UNAVAILABLE, None)`` means the key's identity is
        UNKNOWN — Redis unreachable, an op failed, or the lost-SET race
        could not be re-read. The caller MUST NOT invent a binding from an
        UNAVAILABLE result: with required coordination that is a 503, and
        a local fallback would let two workers bind the same key to two
        different cards and execute the write twice.

        Round-8 (owner P1 #2): the NX write records THIS attempt's
        generation (``scope|generation``). The post-acquire re-assert and
        the known non-2xx compare-and-delete use the same generation, so a
        stale attempt's cleanup can never delete a successor's binding."""
        if not self._ensure_available() or self._client is None:
            return _SCOPE_BINDING_UNAVAILABLE, None
        stored = self._run(self._client.get, self._scope_key(origin_ns, key))
        if stored:
            return _SCOPE_BINDING_RESOLVED, _scope_from_binding_value(str(stored))
        self._run(
            self._client.set,
            self._scope_key(origin_ns, key),
            _scope_binding_value(patient_scope, generation),
            nx=True,
            ex=self._ttl,
        )
        stored = self._run(self._client.get, self._scope_key(origin_ns, key))
        if stored:
            return _SCOPE_BINDING_RESOLVED, _scope_from_binding_value(str(stored))
        # The SET NX reported nothing and the re-read saw nothing: a
        # concurrent worker may or may not have landed its NX between our
        # two reads. The binding state is UNRESOLVED — never invent one.
        return _SCOPE_BINDING_UNAVAILABLE, None

    def extend_scope_binding(
        self, origin_ns: str, key: str, patient_scope: str, generation: str
    ) -> bool:
        """Round-5 (owner P1): keep the binding alive as long as the snapshot
        it guards.

        The binding is written BEFORE the handler runs while the response
        snapshot is stored AFTER it completes; left alone, the binding can
        expire first and in that window the same key would be re-bindable
        to a DIFFERENT card (the snapshot it protected is still live).

        Round-8 (owner P1 #2 + P2, PR #3340): atomic restore-or-refresh
        with generation re-stamping, and the result is now REPORTED:
        - an ABSENT binding is RE-CREATED under the caller's generation —
          a stale attempt's in-between cleanup (compare-and-delete of ITS
          generation) can no longer leave a successor's live execution
          without a binding; the success-path extension restores it;
        - a SAME-scope binding is refreshed with the caller's generation;
        - a FOREIGN scope is never touched (False).
        True means Redis CONFIRMED the upsert; a transport failure reports
        False and the caller must not count the outcome durable."""
        if not self._ensure_available() or self._client is None:
            return False
        result = self._run(
            self._client.eval,
            _SCOPE_UPSERT_LUA,
            1,
            self._scope_key(origin_ns, key),
            patient_scope,
            _scope_binding_value(patient_scope, generation),
            str(self._ttl),
        )
        return result == 1

    def clear_scope_binding(
        self, origin_ns: str, key: str, patient_scope: str, generation: str
    ) -> bool:
        """Round-7 (owner P1 #2, PR #3340): drop the scope binding of a KNOWN
        non-2xx outcome.

        The binding is written BEFORE endpoint validation, so a flood of
        invalid keyed requests occupies binding slots for entries whose
        outcome is provably "nothing applied". Deleting those bindings on
        the known non-2xx path keeps the slots for DURABLE successful
        bindings (the ones that guard live response snapshots against a
        re-linked card).

        Round-8 (owner P1 #2): atomic compare-and-delete of the FULL value
        (scope AND generation) — the previous separate GET+DELETE could
        delete a SUCCESSOR attempt's binding mid-execution, because both
        attempts share the same scope value and the old guard could not
        tell the generations apart. True only when THIS attempt's own
        binding generation was deleted."""
        if not self._ensure_available() or self._client is None:
            return False
        result = self._run(
            self._client.eval,
            _SCOPE_CAS_DELETE_LUA,
            1,
            self._scope_key(origin_ns, key),
            _scope_binding_value(patient_scope, generation),
        )
        return result == 1

    def probe_legacy_artifacts(
        self, legacy_ns: str, key: str
    ) -> tuple[tuple[Response | None, str | None, str | None], bool, bool, str | None]:
        """Round-4 (owner P1): ONE read pass over the PRE-#3340 namespace.

        Returns ``((response, payload_hash, principal_role), has_intent,
        has_in_flight, legacy_operation_scope)`` for the artifacts the
        previous deployment wrote under the user-only hash. Read-only by
        contract — the legacy namespace belongs to the pre-deploy workers
        (only the explicit stale-role ``forget_response`` in the dispatch
        legacy branch ever clears anything there). Reads the raw keys
        directly: the production methods wrap the same state, but the probe
        must stay a single independent pass no other in-flight bookkeeping
        can re-order.

        Round-8 (owner P2, PR #3340): snapshots written by THIS deployment
        carry an ``operation_scope`` stamp — the caller refuses to replay a
        stamp belonging to a DIFFERENT operation (one user-only key reused
        across two POST operations must never alias). Old-worker snapshots
        carry no stamp (None) and keep the migration replay contract."""
        if not self._ensure_available() or self._client is None:
            return (None, None, None), False, False, None
        raw = self._run(self._client.get, self._resp_key(legacy_ns, key))
        legacy = _decode_response_snapshot(raw) if raw else (None, None, None)
        legacy_op_scope: str | None = None
        if raw:
            try:
                legacy_op_scope = json.loads(raw).get("operation_scope")
            except Exception:
                legacy_op_scope = None
        has_intent = bool(
            self._run(self._client.get, self._intent_key(legacy_ns, key))
        )
        has_claim = bool(
            self._run(self._client.get, self._claim_key(legacy_ns, key))
        )
        return legacy, has_intent, has_claim, legacy_op_scope

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

    def mark_execution_intent(
        self,
        user_id: int | str,
        key: str,
        owner_token: str | None = None,
        tokenless_marker: str | None = None,
    ) -> bool:
        """Confirm an intent without overwriting another attempt's outcome.

        Owner-bound calls atomically check the current lease AND the existing
        marker. A positive ownership refusal raises _IntentClaimLost, even
        for optional Redis: this is not a transport outage eligible for the
        local fallback. Transport errors retain the existing bool contract.

        Token-less callers may only INSERT an absent marker. The dispatch
        path supplies its acquired token whenever it owns a claim and a
        UNIQUE ``tokenless_marker`` otherwise (PR 3319, codex P1): a shared
        anonymous value would let one degraded attempt's cleanup delete
        another attempt's marker. Direct legacy callers without a marker
        keep the historical shared value.
        """
        confirmed = False
        if self._ensure_available() and self._client is not None:
            if owner_token:
                result = self._run(
                    self._client.eval,
                    _INTENT_MARK_LUA,
                    2,
                    self._claim_key(user_id, key),
                    self._intent_key(user_id, key),
                    owner_token,
                    str(self._ttl),
                )
                if result in (-1, -2):
                    # No marker was written. In particular, do not create or
                    # later clear a local mirror for somebody else's intent.
                    raise _IntentClaimLost("Idempotency intent ownership lost")
                confirmed = result == 1
            else:
                confirmed = bool(
                    self._run(
                        self._client.set,
                        self._intent_key(user_id, key),
                        tokenless_marker or _TOKENLESS_INTENT_VALUE,
                        nx=True,
                        ex=self._ttl,
                    )
                )
        # Preserve the local safety mirror on transport failures. A refused
        # required attempt clears only its own marker before returning 503.
        _mark_local_execution_intent(user_id, key)
        return confirmed

    def clear_execution_intent(self, user_id: int | str, key: str) -> None:
        """Outcome is KNOWN (response stored, or the endpoint returned a
        completed non-2xx without committing) — the marker is no longer
        needed and the retry contract returns to its previous shape."""
        if self._ensure_available() and self._client is not None:
            self._run(self._client.delete, self._intent_key(user_id, key))
        _clear_local_execution_intent(user_id, key)

    def clear_execution_intent_if_owner(self, user_id: int | str, key: str, owner_token: str) -> bool:
        """Махмудбек R18 #3277 (P2): delete the intent marker ONLY if it was
        written by the attempt owning ``owner_token`` (compare-and-delete).

        A refused (503) attempt whose marker SET reported failure must be
        able to purge a marker that may have LANDED despite the failure —
        otherwise a false ``idempotency_uncertain_outcome`` blocks the retry
        after Redis recovery for an operation that provably never executed.
        The owner binding guarantees a marker from ANOTHER attempt (the R9
        unknown-outcome protection) is never deleted. Best-effort by
        contract: the direct client call (bypassing the ``_run`` cooldown)
        gives the cleanup a chance right after the failed SET, while
        ``_ensure_available`` is still in its reconnect cooldown. A cleanup
        that loses the race against a late-landing SET degrades to the
        conservative 409 reconcile — never to a duplicate execution.
        """
        if self._client is None or not owner_token:
            return False
        try:
            return bool(
                self._client.eval(
                    _INTENT_RELEASE_LUA,
                    1,
                    self._intent_key(user_id, key),
                    owner_token,
                )
            )
        except Exception as exc:
            logger.warning("Idempotency intent owner-cleanup failed: %s", exc)
            return False

    def clear_execution_intent_owned(
        self, user_id: int | str, key: str, owner_token: str | None
    ) -> None:
        """PR 3319: known-outcome cleanup that deletes ONLY the marker this
        attempt wrote. An owning attempt compares against its claim token; a
        tokenless (optional-degrade) attempt compares against the unique
        tokenless marker its own SET NX inserted. A foreign marker — another
        attempt's unknown-outcome protection (R9), token-bound or anonymous
        — is never deleted, even when this attempt's Redis view recovered
        after a degrade. The local per-process mirror is cleared once the
        compare-and-delete went through; if the eval ITSELF fails (transport
        outage) the cleanup outcome is UNVERIFIED — the own marker may have
        landed despite a lost SET, or a foreign marker may guard the key —
        so the mirror is kept (re-armed) and the claim enters the reconnect
        cooldown, leaving the attempt fail-closed (codex #3319 post-merge
        P2)."""
        token = owner_token or _TOKENLESS_INTENT_VALUE
        if self._client is not None:
            try:
                # Direct client call — deliberately bypasses the reconnect
                # cooldown (_run/_ensure_available). The caller may arrive
                # RIGHT after a failed mark whose _run flipped the claim to
                # unavailable for the whole cooldown: the lost-response SET
                # may have LANDED, and this cleanup is the only chance to
                # remove the attempt's own marker within the same request
                # (codex PR 3319 P2). Same best-effort pattern as
                # clear_execution_intent_if_owner: a cleanup that fails here
                # degrades to the conservative 409 reconcile, never to a
                # duplicate execution.
                self._client.eval(
                    _INTENT_RELEASE_LUA,
                    1,
                    self._intent_key(user_id, key),
                    token,
                )
                # A successful direct eval PROVES Redis is reachable right
                # now (codex PR 3319 round 3): end the cooldown, otherwise
                # the 409's Retry-After retry on this worker would still see
                # the coordination as unavailable, skip the distributed
                # acquire through the optional local-degrade path, and race
                # another worker that acquires the now-unmarked key.
                self._available = True
                self._failed_at = 0.0
            except Exception as exc:
                logger.warning("Idempotency intent owned-cleanup failed: %s", exc)
                # codex #3319 post-merge P2: unlike the success branch, the
                # failed eval proves NOTHING about Redis reachability — the
                # attempt must stay fail-closed. Keep the local intent
                # mirror: it is the only known-outcome guard the optional
                # local-degrade path consults while the reconnect cooldown
                # holds, so a Retry-After retry that skips every distributed
                # check reconciles (409 uncertain) instead of re-executing
                # the handler over a foreign attempt's unknown outcome. Flip
                # the claim into the cooldown explicitly: the direct call
                # bypasses _run, so without this the stale 'available' view
                # (the mark's SET NX had just succeeded) would let the very
                # next request attempt a doomed distributed round-trip and
                # only then degrade — the deletion of the mirror is what
                # turned that degrade into a duplicate execution.
                _mark_local_execution_intent(user_id, key)
                self._available = False
                self._failed_at = time.time()
                return
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

    Codex R7 #3092 (P1): an EXPLICIT IDEMPOTENCY_REDIS_URL is the
    deployment's contract that keyed writes MUST be cross-worker
    coordinated — the claim is then marked REQUIRED and the middleware
    refuses keyed writes (503) while Redis is unreachable. The implicit
    ARQ fallback stays best-effort (in-memory degrade) so single-worker
    deployments and the test suite keep working without Redis.
    """
    global _distributed_claim
    if _distributed_claim is not None:
        return _distributed_claim
    try:
        from app.core.config import settings

        redis_url = settings.IDEMPOTENCY_REDIS_URL
        required = bool(redis_url)
        if not redis_url:
            redis_url = settings.ARQ_REDIS_URL
    except Exception:  # pragma: no cover - settings not initialized (tests)
        return None
    if not redis_url:
        return None
    _distributed_claim = DistributedIdempotencyClaim(redis_url, required=required)
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

        # Round-6 (owner P1, PR #3340): bound the caller-owned key BEFORE any
        # allocation (body read, principal resolution, Redis keys, mirror
        # entries). An oversized key is a non-executing 400: executing a
        # keyed write WITHOUT protection would defeat the middleware's whole
        # purpose, and silently truncating/normalizing would alias distinct
        # keys onto one identity.
        if len(idempotency_key) > _IDEMPOTENCY_KEY_MAX_LENGTH:
            logger.warning(
                "Idempotency key rejected (length %s > %s): path=%s",
                len(idempotency_key), _IDEMPOTENCY_KEY_MAX_LENGTH, request.url.path,
            )
            return Response(
                status_code=400,
                headers={"Cache-Control": "no-store"},
                content=(
                    '{"code": "idempotency_key_invalid", "detail": "The '
                    'Idempotency-Key header must be 1..128 characters. Send a '
                    'shorter key."}'
                ),
                media_type="application/json",
            )

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

        # Round-3 (owner P2): the idempotency identity is the OPERATION, not
        # just the principal — method + normalized path join the namespace,
        # so one key can never alias two different operations that share a
        # request DTO (POST /patients/booking/preview vs POST
        # /patients/booking) or two resources of a parameterized route.
        op_scope = (
            f"{request.method.upper()}:{_normalize_idem_path(request.url.path)}"
        )
        # Round-3 (owner P1): patient-aware replay policy. The live card
        # state decides whether idempotency machinery may run AT ALL for a
        # Patient principal: an active card scopes the namespace to the card
        # id; a missing/soft-deleted card bypasses replay entirely so the
        # endpoint's own guards (404/403 + denied audit) answer the retry.
        try:
            (
                patient_scope,
                patient_fall_through,
                patient_user_active,
            ) = await asyncio.to_thread(
                _patient_replay_policy_sync, request, canonical_id
            )
        except Exception:
            logger.warning(
                "Idempotency patient replay-policy check failed; refusing keyed write: path=%s",
                request.url.path,
                exc_info=True,
            )
            return _principal_refusal_response()
        if patient_fall_through:
            logger.warning(
                "Idempotency replay policy: no ACTIVE Patient card; bypassing replay, "
                "endpoint guards decide: user=%s key=%s path=%s",
                canonical_id, idempotency_key, request.url.path,
            )
            return await call_next(request)
        if patient_scope and patient_user_active is False:
            # Round-5 (owner P2): a DEACTIVATED patient account is refused
            # BEFORE any idempotency machinery runs. The keyed booking's
            # audited principal factory cannot see this request (the
            # middleware decides first), so the denied PHI-audit row was
            # already written inside the policy check (same DB pass) — the
            # refusal here is NON-EXECUTING: nothing is bound, claimed or
            # replayed, and the endpoint never starts.
            logger.warning(
                "Idempotency replay policy: DEACTIVATED patient account; refusing "
                "keyed write (non-executing, audited): user=%s key=%s path=%s",
                canonical_id, idempotency_key, request.url.path,
            )
            return _principal_refusal_response()

        user_id = self._namespace(canonical_id, op_scope, patient_scope)

        # Codex R4 #3092 (P1): resolve the distributed claim BEFORE the local
        # cache check — the role-mismatch fall-through needs it to drop a
        # stale snapshot and re-execute.
        claim = get_distributed_claim()
        claim_acquired = True
        claim_token: str | None = None
        # PR 3319 (codex P1): уникальное значение маркера tokenless-попытки.
        # Анонимный "1" не доказывает владение: cleanup деградировавшей
        # попытки мог удалить маркер другой tokenless-попытки. UUID делает
        # compare-and-delete точным для tokenless-пути.
        tokenless_marker: str | None = None
        # Round-8 (owner P1 #2, PR #3340): per-attempt GENERATION for the
        # scope-binding protocol. Every binding write of THIS attempt (NX
        # bind, post-acquire re-assert, success extension) carries it, and
        # the known non-2xx cleanup compare-and-deletes the FULL value — a
        # stale attempt can then never delete a successor's in-flight
        # binding (both attempts share the same patient scope, so the
        # round-7 scope-only guard could not tell the generations apart).
        attempt_generation = uuid.uuid4().hex

        # Round-6 (owner P1, PR #3340): LEGACY MIGRATION FENCE state. When
        # this worker owns the legacy in-flight claim (acquired BEFORE any
        # legacy read — see the reconciliation block below), the fence rides
        # along with the new-namespace claim until the operation completes:
        # an old-version worker can then never start or continue an
        # execution of this key in parallel. ``legacy_fence_keep_on_exit``
        # marks the one refusal path where the fence must OUTLIVE the
        # request (a new worker is executing; the held fence is what keeps
        # old workers off the key until the dual-written outcome lands).
        legacy_fence_ns: str | None = None
        legacy_fence_token: str | None = None
        legacy_fence_keep_on_exit = False

        def _release_legacy_fence() -> None:
            """Release the legacy fence we own (compare-and-delete).

            Non-mutating when this request never held the fence or already
            released it. Never touches a fence held by another worker."""
            nonlocal legacy_fence_token
            if legacy_fence_ns is not None and legacy_fence_token is not None:
                claim.release(legacy_fence_ns, idempotency_key, legacy_fence_token)
                legacy_fence_token = None

        # Codex R7 #3092 (P1): fail closed when coordination is REQUIRED
        # (explicit IDEMPOTENCY_REDIS_URL) but unavailable. Degrading to the
        # per-process cache here let two staging workers execute the same
        # keyed /registrar/cart request concurrently during a Redis
        # timeout/restart — exactly the window when the previous R2 cooldown
        # kept the layer disabled — and recreated duplicate visits, invoices
        # and queue positions. Refusal (503) is non-executing: the client
        # retries with the SAME key once coordination recovers, replays the
        # stored snapshot, or reconciles via the execution intent.
        if claim is not None and claim.required and not claim.try_available():
            logger.warning(
                "Idempotency coordination unavailable (required Redis down): "
                "user=%s key=%s path=%s — refusing keyed write",
                user_id, idempotency_key, request.url.path,
            )
            return Response(
                status_code=503,
                headers={"Retry-After": "2", "Cache-Control": "no-store"},
                content=(
                    '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                    'временно недоступна: распределённая координация не отвечает. '
                    'Повторите запрос с тем же Idempotency-Key."}'
                ),
                media_type="application/json",
            )

        # Round-4 (owner P1): bind the key to the patient card it FIRST ran
        # under — the binding lives in the ORIGIN namespace (user + operation,
        # no patient scope), the one identity that survives re-linking the
        # account to another card. A retry whose CURRENT card differs from
        # the bound one is refused WITHOUT executing: one logical booking
        # attempt must never materialize a second appointment for a different
        # patient (the round-3 namespace scoping alone made the retry look
        # like a FRESH key after a re-link — the cached snapshot became
        # invisible and the write re-ran for the new card). The re-linked
        # card books with a NEW key, per the endpoint contract.
        #
        # Round-5 (owner P1): the binding states are handled EXPLICITLY —
        #   * Redis RESOLVED the binding → mirrored into the per-process
        #     store, so a LATER outage in this worker still knows the key's
        #     card (the previous Redis-only binding was invisible to the
        #     mirror and a degraded retry after a re-link re-bound the key
        #     to the NEW card and executed for it);
        #   * required coordination that degraded AFTER the initial gate
        #     (Redis dies ON the scope GET/SET) → 503 fail-closed — the
        #     local fallback here is exactly the fail-open the required
        #     deployment forbids (two workers could both go local);
        #   * degraded OPTIONAL coordination with a KNOWN mirror binding →
        #     compare against it (a mismatch still refuses cross-card);
        #   * degraded OPTIONAL coordination with NO known binding →
        #     conservative 503: the key may be bound in Redis only, and
        #     binding it to the CURRENT card would execute a foreign
        #     attempt. The client retries the SAME key after recovery;
        #   * NO distributed layer at all → the per-process mirror IS the
        #     coordination store (same best-effort contract as the intent
        #     markers) and a first-seen key binds locally.
        origin_ns = ""
        if patient_scope:
            origin_ns = self._namespace(canonical_id, op_scope)
            bound_scope: str | None = None
            binding_resolved = False
            if claim is not None and claim.try_available():
                binding_outcome, redis_bound = claim.bind_scope_if_absent(
                    origin_ns, idempotency_key, patient_scope, attempt_generation
                )
                if binding_outcome == _SCOPE_BINDING_RESOLVED:
                    binding_resolved = True
                    bound_scope = redis_bound
                    # Round-5 (owner P1): mirror the Redis-resolved binding
                    # so the degraded path below can still see it.
                    # Round-8 (owner P1): the mirror PRESERVES a locally
                    # stored snapshot — the previous unconditional tuple
                    # replace wiped the local outcome on every same-key
                    # retry whose scope GET answered, exactly before the
                    # response GET whose failure made that local outcome
                    # the only replay source left.
                    _local_scope_binding_mirror(origin_ns, idempotency_key, bound_scope)
            if not binding_resolved:
                if claim is not None and claim.required:
                    logger.warning(
                        "Idempotency scope binding unresolved (required Redis degraded "
                        "after the initial gate): user=%s key=%s path=%s — refusing "
                        "keyed write",
                        canonical_id, idempotency_key, request.url.path,
                    )
                    return Response(
                        status_code=503,
                        headers={"Retry-After": "2", "Cache-Control": "no-store"},
                        content=(
                            '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                            'временно недоступна: распределённая координация не отвечает. '
                            'Повторите запрос с тем же Idempotency-Key."}'
                        ),
                        media_type="application/json",
                    )
                mirror_scope = _local_scope_binding_get(origin_ns, idempotency_key)
                if mirror_scope is not None:
                    bound_scope = mirror_scope
                elif claim is None or not claim._ever_available:
                    # No distributed layer at all, or Redis has NEVER answered
                    # in this worker's lifetime: no binding can exist "only in
                    # Redis" from this process's point of view — the mirror IS
                    # the coordination store (same best-effort contract as the
                    # execution-intent markers), a first-seen key binds here.
                    _local_scope_binding_set(origin_ns, idempotency_key, patient_scope)
                    bound_scope = patient_scope
                else:
                    logger.warning(
                        "Idempotency scope binding unknown while coordination is "
                        "degraded: user=%s key=%s path=%s — refusing conservatively "
                        "(the key may be bound in Redis only)",
                        canonical_id, idempotency_key, request.url.path,
                    )
                    return Response(
                        status_code=503,
                        headers={"Retry-After": "2", "Cache-Control": "no-store"},
                        content=(
                            '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                            'временно недоступна: принадлежность ключа не может быть '
                            'проверена. Повторите запрос с тем же Idempotency-Key, когда '
                            'координация восстановится."}'
                        ),
                        media_type="application/json",
                    )
            if bound_scope != patient_scope:
                logger.warning(
                    "Idempotency scope mismatch: key=%s bound to %s but current "
                    "card scope is %s — refusing: user=%s path=%s",
                    idempotency_key,
                    bound_scope,
                    patient_scope,
                    canonical_id,
                    request.url.path,
                )
                return self._scope_mismatch_response()

        # Check local (per-process) cache first — fastest path.
        # Round-7 (owner P1 #2, PR #3340): patient-scope operations replay
        # from the ATOMIC binding entry (scope + payload hash + snapshot,
        # one LRU entry, shared fate) instead of the separate response cache
        # — an evicted binding can no longer orphan a live response that a
        # re-linked card would re-execute under a fresh scope.
        if patient_scope and origin_ns:
            cached, local_mismatch, cached_role = _local_patient_outcome_get(
                origin_ns, idempotency_key, incoming_hash
            )
        else:
            cached, local_mismatch, cached_role = _idempotency_cache.get(
                user_id, idempotency_key, incoming_hash
            )
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
            # Codex R15 #3092 (P1): the replay re-runs the principal-level
            # RESOURCE authorization (active Doctor profile) even when the
            # role label is unchanged — an inline-auth route's policy can
            # start refusing while the label stays the same.
            authorized, current_role, current_superuser = await self._principal_authorized(
                request, principal_payload, require_active_doctor_profile=True
            )
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
            # re-execution re-stores with the fresh role. Round-7: patient
            # operations drop ONLY the snapshot from the atomic entry — the
            # card binding is unchanged and keeps guarding the key.
            logger.warning(
                "Idempotency replay refused (role changed since execution, policy unknown): user=%s key=%s path=%s (%s -> %s) — re-executing",
                user_id, idempotency_key, request.url.path, cached_role, current_role,
            )
            if patient_scope and origin_ns:
                _local_patient_outcome_forget_snapshot(origin_ns, idempotency_key, patient_scope)
            else:
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
                # Codex R15 #3092 (P1): active-Doctor-profile resource fact
                # re-checked on replays (same-role included).
                authorized, current_role, current_superuser = await self._principal_authorized(
                    request, principal_payload, require_active_doctor_profile=True
                )
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
                # re-executes and re-stores with the fresh role. Round-7:
                # patient operations drop ONLY the atomic entry's snapshot.
                logger.warning(
                    "Idempotency distributed replay refused (role changed since execution, policy unknown): user=%s key=%s path=%s (%s -> %s) — re-executing",
                    user_id, idempotency_key, request.url.path, stored_role, current_role,
                )
                claim.forget_response(user_id, idempotency_key)
                if patient_scope and origin_ns:
                    _local_patient_outcome_forget_snapshot(origin_ns, idempotency_key, patient_scope)
                else:
                    _idempotency_cache.invalidate(user_id, idempotency_key)
                replayed = None

            # Round-6 (owner P1): the reconciliation against the PRE-#3340
            # user-only namespace is a real MIGRATION FENCE, not a read.
            # Round-4/5 probed legacy artifacts read-only and THEN claimed
            # only the new operation-scoped namespace, which left two rolling
            # -deploy interleavings open:
            #   1. probe reports "empty" → the request reaches an OLD worker,
            #      which acquires the legacy claim and starts executing →
            #      this worker acquires the NEW claim and both versions run
            #      one logical write in parallel;
            #   2. the old worker COMPLETES between the three separate probe
            #      GETs — the first GET saw no response, by the claim/intent
            #      reads the response was stored and the markers dropped →
            #      three misses, the write re-executed.
            # The fence closes both:
            #   - THIS worker first SET-NX-acquires the LEGACY claim — the
            #     very marker old workers must hold to execute, so once the
            #     fence is owned, no old worker can start or continue this
            #     key (a live old-worker claim makes our acquire fail and is
            #     answered 409 in-flight after ONE re-read);
            #   - legacy artifacts are re-read only UNDER the fence, so the
            #     picture can no longer change behind the reads;
            #   - a stored legacy RESPONSE replays under the same replay
            #     contract (payload hash, principal authorization, endpoint
            #     role policy) and MIGRATES to the current namespace;
            #   - a legacy INTENT without a response is refused
            #     conservatively (409 idempotency_uncertain_outcome);
            #   - with the fence held and the legacy namespace empty, the
            #     fence is held TOGETHER with the new claim until completion
            #     (a dedicated lease-renewal loop keeps it alive for long
            #     handlers) and the outcome is DUAL-WRITTEN to BOTH
            #     namespaces, so old-version workers reconcile against the
            #     snapshot once the fence lease lapses.
            # Scoped to principals WITHOUT a patient scope: pre-#3340
            # endpoints carry no patient scoping, so a legacy snapshot cannot
            # be attributed to the CURRENT card — replaying it across a card
            # re-link would resurrect exactly the cross-card leak the
            # patient-aware policy closed. Every patient-facing keyed
            # endpoint is NEW in #3340 (no legacy keys exist for
            # patient-scope principals); staff endpoints — the legacy keyed
            # traffic — reconcile fully.
            #
            # Round-8 (owner P2, PR #3340): the bridge is bounded by a
            # rollout window (drain + legacy response TTL). After the cutoff
            # the user-only namespace is no longer read, written or fenced —
            # the operation-scoped namespace is the only truth, and one key
            # can no longer alias two different POST operations through the
            # user-only hash.

            async def _legacy_replay_decision(
                legacy_resp: Response | None,
                legacy_hash: str | None,
                legacy_role: str | None,
            ) -> str:
                """Shared replay contract for a legacy snapshot (both the
                fenced and the contended path): payload binding → principal
                authorization → endpoint role policy. Returns one of
                "mismatch" / "unauthorized" / "replay" / "endpoint_policy" /
                "role_changed" — the caller owns every side effect."""
                if legacy_hash and legacy_hash != incoming_hash:
                    logger.warning(
                        "Idempotency payload mismatch (legacy namespace): "
                        "user=%s key=%s path=%s",
                        canonical_id,
                        idempotency_key,
                        request.url.path,
                    )
                    return "mismatch"
                authorized, current_role, current_superuser = (
                    await self._principal_authorized(
                        request, principal_payload, require_active_doctor_profile=True
                    )
                )
                if not authorized:
                    logger.warning(
                        "Idempotency legacy replay refused (principal not authorized): "
                        "user=%s key=%s path=%s",
                        canonical_id,
                        idempotency_key,
                        request.url.path,
                    )
                    return "unauthorized"
                permitted = self._role_permitted_for_replay(
                    request,
                    legacy_role,
                    current_role,
                    current_superuser,
                )
                if permitted is True or (
                    permitted is None
                    and (legacy_role is None or current_role == legacy_role)
                ):
                    return "replay"
                if permitted is False:
                    # Endpoint policy refuses the current role — the
                    # endpoint's require_roles 403s exactly as for a
                    # fresh request; the legacy snapshot is KEPT.
                    logger.warning(
                        "Idempotency legacy replay refused (endpoint policy): "
                        "user=%s key=%s path=%s (stored=%s current=%s) — falling through",
                        canonical_id,
                        idempotency_key,
                        request.url.path,
                        legacy_role,
                        current_role,
                    )
                    return "endpoint_policy"
                # permitted is None AND role changed: conservative R4 analog.
                return "role_changed"

            if not patient_scope and claim.try_available() and _legacy_bridge_active():
                legacy_ns = self._namespace(canonical_id)
                legacy_token = claim.acquire(legacy_ns, idempotency_key)
                if legacy_token is not None:
                    # Own the fence state IMMEDIATELY: every branch below
                    # (replay, refusal, fall-through, execution) releases it
                    # through the shared compare-and-delete closure.
                    legacy_fence_ns = legacy_ns
                    legacy_fence_token = legacy_token
                    # FENCE HELD: no old worker can claim or execute this key
                    # while we own it. Re-read the artifacts NOW — an old
                    # worker that completed between the fence and this read
                    # is seen; nothing can start behind it any more.
                    (
                        (legacy_resp, legacy_hash, legacy_role),
                        legacy_intent,
                        _own_fence_marker,
                        legacy_op_scope,
                    ) = claim.probe_legacy_artifacts(legacy_ns, idempotency_key)
                    # Round-8 (owner P2): a snapshot stamped with a DIFFERENT
                    # operation belongs to another POST under the same
                    # user-only key. It is neither replayed nor refused as a
                    # payload mismatch — the operation-scoped namespace
                    # decides this request (release the fence and fall
                    # through to the new-namespace claim). Old-worker
                    # snapshots carry no stamp and keep the migration
                    # replay contract for the bounded bridge window.
                    legacy_foreign_op = (
                        legacy_resp is not None
                        and legacy_op_scope is not None
                        and legacy_op_scope != op_scope
                    )
                    if legacy_foreign_op:
                        logger.info(
                            "Idempotency legacy snapshot belongs to another operation; "
                            "skipping user-only replay: user=%s key=%s path=%s "
                            "(legacy op=%s)",
                            canonical_id,
                            idempotency_key,
                            request.url.path,
                            legacy_op_scope,
                        )
                        _release_legacy_fence()
                    # An EMPTY legacy namespace UNDER OUR FENCE is exactly the
                    # interleaving round-4/5 could not close: an old worker
                    # could claim and execute between the old read-only probe
                    # and the new-namespace acquire. With the fence held that
                    # is impossible — the request simply proceeds to the new
                    # claim keeping the fence. A stored RESPONSE replays
                    # below; an intent without a response refuses
                    # conservatively.
                    elif legacy_resp is not None:
                        decision = await _legacy_replay_decision(
                            legacy_resp, legacy_hash, legacy_role
                        )
                        if decision == "mismatch":
                            _release_legacy_fence()
                            return self._payload_mismatch_response()
                        if decision == "unauthorized":
                            # Non-executing refusal — the fence must not
                            # outlive the request that holds it.
                            _release_legacy_fence()
                            return _principal_refusal_response()
                        if decision == "replay":
                            # Migrate the committed outcome to the current
                            # namespace (bounded TTL extension) so subsequent
                            # replays resolve without the legacy read.
                            claim.store_response(
                                user_id,
                                idempotency_key,
                                legacy_resp,
                                payload_hash=legacy_hash or "",
                                principal_role=legacy_role,
                                operation_scope=op_scope,
                            )
                            _idempotency_cache.set(
                                user_id,
                                idempotency_key,
                                legacy_resp,
                                incoming_hash,
                                principal_role=legacy_role,
                            )
                            logger.info(
                                "Idempotency legacy replay migrated to current namespace: "
                                "user=%s key=%s path=%s",
                                canonical_id,
                                idempotency_key,
                                request.url.path,
                            )
                            _release_legacy_fence()
                            return legacy_resp
                        if decision == "endpoint_policy":
                            _release_legacy_fence()
                            return await call_next(request)
                        # decision == "role_changed": drop the stale legacy
                        # snapshot and re-execute UNDER THE FENCE — old
                        # workers stay blocked; the completion paths
                        # dual-write the fresh outcome to both namespaces and
                        # release the fence.
                        claim.forget_response(legacy_ns, idempotency_key)
                    elif legacy_intent:
                        # The pre-deploy attempt reached execution and died
                        # before its outcome landed (the intent survives its
                        # claim). We now HOLD the fence — release it and let
                        # the durable intent marker speak for itself (old
                        # workers refuse on it too).
                        _release_legacy_fence()
                        return self._uncertain_outcome_response()
                else:
                    # The fence is HELD ELSEWHERE — an old-version worker owns
                    # the legacy claim and is executing this key right now
                    # (or died within its lease window). Distinguish a live
                    # old worker from a transport failure.
                    if claim.required and not claim.try_available():
                        logger.warning(
                            "Idempotency coordination unavailable while fencing legacy "
                            "claim (required Redis degraded): user=%s key=%s path=%s — "
                            "refusing keyed write",
                            canonical_id, idempotency_key, request.url.path,
                        )
                        return Response(
                            status_code=503,
                            headers={"Retry-After": "2", "Cache-Control": "no-store"},
                            content=(
                                '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                                'временно недоступна: распределённая координация не отвечает. '
                                'Повторите запрос с тем же Idempotency-Key."}'
                            ),
                            media_type="application/json",
                        )
                    # One re-read under contention: the old worker may have
                    # completed between our failed fence and this read.
                    (
                        (legacy_resp, legacy_hash, legacy_role),
                        _contended_intent,
                        _contended_claim,
                        _contended_op_scope,
                    ) = claim.probe_legacy_artifacts(legacy_ns, idempotency_key)
                    # Round-8 (owner P2): another operation's stamped snapshot
                    # is neither replayed nor mismatch-refused — the
                    # operation-scoped namespace decides; the in-flight
                    # markers below still answer conservatively while an
                    # execution actually holds the legacy claim.
                    _contended_foreign_op = (
                        legacy_resp is not None
                        and _contended_op_scope is not None
                        and _contended_op_scope != op_scope
                    )
                    if legacy_resp is not None and not _contended_foreign_op:
                        decision = await _legacy_replay_decision(
                            legacy_resp, legacy_hash, legacy_role
                        )
                        if decision == "mismatch":
                            return self._payload_mismatch_response()
                        if decision == "unauthorized":
                            return _principal_refusal_response()
                        if decision == "replay":
                            claim.store_response(
                                user_id,
                                idempotency_key,
                                legacy_resp,
                                payload_hash=legacy_hash or "",
                                principal_role=legacy_role,
                                operation_scope=op_scope,
                            )
                            _idempotency_cache.set(
                                user_id,
                                idempotency_key,
                                legacy_resp,
                                incoming_hash,
                                principal_role=legacy_role,
                            )
                            logger.info(
                                "Idempotency legacy replay migrated to current namespace: "
                                "user=%s key=%s path=%s",
                                canonical_id,
                                idempotency_key,
                                request.url.path,
                            )
                            return legacy_resp
                        if decision == "endpoint_policy":
                            return await call_next(request)
                        # decision == "role_changed" WITHOUT the fence: the
                        # legacy claim is held by an old worker — re-executing
                        # here would run BOTH versions in parallel (the exact
                        # race the fence exists for). Refuse in-flight: the
                        # same-key retry after the old worker finishes either
                        # fences the legacy claim or replays the migrated
                        # outcome. The stale snapshot is KEPT.
                        logger.warning(
                            "Idempotency legacy snapshot role binding stale while an old "
                            "worker may still be executing: user=%s key=%s path=%s — "
                            "refusing in-flight",
                            canonical_id, idempotency_key, request.url.path,
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
                    if _contended_claim:
                        # Round-5 contract (still pinned): a LIVE legacy claim
                        # means an old worker is mid-execution RIGHT NOW — it
                        # holds BOTH markers (the short claim AND the long
                        # intent), so the answer is in-flight ("retry the
                        # same key"), never uncertain-outcome (whose body
                        # advises a NEW key and would stack a second commit
                        # on top of the running one).
                        logger.warning(
                            "Idempotency legacy claim still in flight (pre-deploy worker): "
                            "user=%s key=%s path=%s — refusing",
                            canonical_id,
                            idempotency_key,
                            request.url.path,
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
                    if _contended_intent:
                        # The claim is GONE but the intent survived: the
                        # pre-deploy attempt reached execution and died
                        # between our failed fence and this read — the
                        # outcome is unknown (R9 reconcile).
                        logger.warning(
                            "Idempotency legacy execution intent without outcome "
                            "(pre-deploy attempt): user=%s key=%s path=%s — refusing",
                            canonical_id,
                            idempotency_key,
                            request.url.path,
                        )
                        return self._uncertain_outcome_response()
                    logger.warning(
                        "Idempotency legacy claim still in flight (pre-deploy worker): "
                        "user=%s key=%s path=%s — refusing",
                        canonical_id,
                        idempotency_key,
                        request.url.path,
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

            claim_token = claim.acquire(user_id, idempotency_key)
            claim_acquired = claim_token is not None
            if not claim_acquired:
                # Another worker holds the claim. Its response may have
                # completed between our acquire attempt and now — re-check
                # before rejecting.
                replayed, stored_hash, stored_role = claim.load_response(user_id, idempotency_key)
                if replayed is not None:
                    if stored_hash and stored_hash != incoming_hash:
                        _release_legacy_fence()
                        return self._payload_mismatch_response()
                    # Codex R4 #3092 (P1): the post-claim replay path runs the
                    # SAME authorization + role binding as the earlier branches —
                    # a revoked/deactivated principal must not receive
                    # the cached response here either. Codex R6: the endpoint
                    # policy decides on role change (snapshot KEPT on refusal).
                    # Codex R8 #3092 (P1): principal refusal is NON-EXECUTING.
                    # Codex R15 #3092 (P1): active-Doctor-profile resource fact
                    # re-checked on replays (same-role included).
                    authorized, current_role, current_superuser = await self._principal_authorized(
                        request, principal_payload, require_active_doctor_profile=True
                    )
                    if not authorized:
                        logger.warning(
                            "Idempotency post-inflight replay refused (principal not authorized): user=%s key=%s path=%s",
                            user_id, idempotency_key, request.url.path,
                        )
                        _release_legacy_fence()
                        return _principal_refusal_response()
                    permitted = self._role_permitted_for_replay(request, stored_role, current_role, current_superuser)
                    if permitted is False or (
                        permitted is None and stored_role is not None and current_role != stored_role
                    ):
                        logger.warning(
                            "Idempotency post-inflight replay refused (role not permitted): user=%s key=%s path=%s",
                            user_id, idempotency_key, request.url.path,
                        )
                        _release_legacy_fence()
                        return await call_next(request)
                    logger.info(
                        "Idempotency distributed replay (post-inflight): user=%s key=%s",
                        user_id, idempotency_key,
                    )
                    # Round-6: the outcome that JUST completed is dual-written
                    # to the legacy namespace by its round-6 executor, so a
                    # released fence can never expose an empty legacy picture
                    # to an old worker.
                    _release_legacy_fence()
                    return replayed
                logger.warning(
                    "Idempotency conflict: key=%s user=%s is in flight on another worker",
                    idempotency_key, user_id,
                )
                # Round-6: the executing worker is a NEW worker (it holds the
                # new-namespace claim). KEEP our legacy fence — it is the only
                # thing keeping old-version workers off this key while that
                # execution runs; once it completes, its dual-written legacy
                # snapshot reconciles them after the fence lease lapses.
                legacy_fence_keep_on_exit = True
                return Response(
                    status_code=409,
                    headers={"Retry-After": "1", "Cache-Control": "no-store"},
                    content=(
                        '{"code": "idempotency_in_flight", "detail": "Request with this Idempotency-Key is '
                        'still being processed. Retry with the same key."}'
                    ),
                    media_type="application/json",
                )

            # Махмудбек R18 #3277 (P1): успешный захват claim НЕ гарантирует,
            # что операция ещё не исполнена. Между нашим ПЕРВЫМ load_response()
            # и этим acquire() другой воркер мог завершить тот же ключ:
            # записать response, ОСВОБОДИТЬ claim и очистить intent — наш
            # SET NX тогда успешно берёт ОСВОБОДИВШИЙСЯ ключ, intent-проверка
            # ниже ничего не находит, CAS-продление подтверждает владение
            # НОВЫМ claim — и хендлер исполняет запись ВТОРОЙ раз (дубликаты
            # визитов/счетов/очереди). Ветка post-inflight выше перепроверяет
            # исход только при ОТКАЗЕ acquire; ветка УСПЕХА обязана
            # перепроверить тоже. Здесь не нужно ни падение Redis, ни истечение
            # lease, ни отмена запроса — достаточно межпроцессного
            # чередования между отдельными командами чтения и захвата.
            # Сохранённый исход возвращается по тому же replay-контракту,
            # что и все остальные replay-ветки: привязка payload, АКТУАЛЬНАЯ
            # авторизация принципала с ресурсной проверкой активного профиля
            # Doctor (R15/R17), политика роли эндпоинта (R6). Только что
            # захваченный claim освобождается СВОИМ токеном
            # (compare-and-delete): claim, перезахваченный другим воркером
            # за время await, не задевается.
            replayed, stored_hash, stored_role = claim.load_response(user_id, idempotency_key)
            if replayed is not None:
                if stored_hash and stored_hash != incoming_hash:
                    claim.release(user_id, idempotency_key, claim_token)
                    _release_legacy_fence()
                    return self._payload_mismatch_response()
                authorized, current_role, current_superuser = await self._principal_authorized(
                    request, principal_payload, require_active_doctor_profile=True
                )
                if not authorized:
                    logger.warning(
                        "Idempotency post-acquire replay refused (principal not authorized): user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    # Codex R8 #3092 (P1): неисполняющий отказ, снапшот хранится.
                    claim.release(user_id, idempotency_key, claim_token)
                    _release_legacy_fence()
                    return _principal_refusal_response()
                permitted = self._role_permitted_for_replay(request, stored_role, current_role, current_superuser)
                if permitted is True or (
                    permitted is None and (stored_role is None or current_role == stored_role)
                ):
                    logger.info(
                        "Idempotency distributed replay (post-acquire): user=%s key=%s path=%s",
                        user_id, idempotency_key, request.url.path,
                    )
                    claim.release(user_id, idempotency_key, claim_token)
                    _release_legacy_fence()
                    return replayed
                if permitted is False:
                    # Политика эндпоинта отказывает текущей роли — require_roles
                    # внутри call_next даст штатный 403 + аудит, снапшот
                    # ХРАНИТСЯ (тот же контракт, что и в ветках выше).
                    logger.warning(
                        "Idempotency post-acquire replay refused (endpoint policy): user=%s key=%s path=%s (stored=%s current=%s)",
                        user_id, idempotency_key, request.url.path, stored_role, current_role,
                    )
                    claim.release(user_id, idempotency_key, claim_token)
                    _release_legacy_fence()
                    return await call_next(request)
                # permitted is None (политика неизвестна) И метка роли
                # сменилась: консервативный R4 — эвикт устаревшей привязки и
                # ИСПОЛНЕНИЕ под НАШИМ claim (владение уже захвачено), исход
                # перезапишется с актуальной ролью — далее штатный путь.
                logger.warning(
                    "Idempotency post-acquire replay refused (role changed since execution, policy unknown): user=%s key=%s path=%s (%s -> %s) — re-executing",
                    user_id, idempotency_key, request.url.path, stored_role, current_role,
                )
                claim.forget_response(user_id, idempotency_key)
                _idempotency_cache.invalidate(user_id, idempotency_key)

        # Round-8 (owner P1 #2, PR #3340): re-assert the scope binding UNDER
        # the just-acquired claim, re-stamped with THIS attempt's generation.
        # From this point the stale attempt's known non-2xx cleanup (a full
        # compare-and-delete of ITS OWN generation) can no longer delete the
        # binding while THIS attempt executes — and if the stale cleanup ran
        # between our bind read and this re-assert, the restore-or-refresh
        # upsert re-creates the binding before the handler starts. The
        # success path re-asserts again atomically with the response store.
        if patient_scope and origin_ns and claim is not None and claim.try_available():
            claim.extend_scope_binding(
                origin_ns, idempotency_key, patient_scope, attempt_generation
            )

        # Codex R16 #3092 (P1): lease renewal starts IMMEDIATELY after the
        # claim is acquired — not just before call_next. The pre-execution
        # phase below (DB authorization, intent checks, distributed SET) can
        # legally outlive the 90 s lease (connection-pool wait, Redis
        # latency, storage stall); a lapse in that window let another worker
        # acquire the key and execute the same cart while THIS worker
        # proceeded on stale pre-execution checks. The loop's renewals carry
        # the OWNER TOKEN (Codex R3), so once ownership is lost they are
        # harmless no-ops against the foreign claim.
        lease_task: asyncio.Task | None = None
        legacy_lease_task: asyncio.Task | None = None

        def _cancel_lease() -> None:
            if lease_task is not None:
                lease_task.cancel()
            if legacy_lease_task is not None:
                legacy_lease_task.cancel()

        if claim is not None and claim_acquired and claim_token is not None:
            lease_task = asyncio.create_task(
                _renew_lease_loop(claim, user_id, idempotency_key, claim_token)
            )
        if legacy_fence_ns is not None and legacy_fence_token is not None:
            # Round-6 (owner P1): the legacy fence needs the SAME lifetime as
            # the operation. Without its own renewal loop a handler longer
            # than the lease would let the fence lapse mid-execution and an
            # old worker could claim the legacy key and execute in parallel.
            legacy_lease_task = asyncio.create_task(
                _renew_lease_loop(claim, legacy_fence_ns, idempotency_key, legacy_fence_token)
            )

        # Codex R17 #3267 (P2): the try/finally covers the WHOLE lifetime
        # of the eager lease task — from its creation, through the
        # pre-execution authorization (an await point where the request
        # coroutine can be CANCELLED), every early refusal, execution and
        # outcome storing. The previous cleanup started only around
        # call_next: a cancellation delivered while awaiting the
        # pre-execution authorization never reached it, and the orphaned
        # _renew_lease_loop task kept renewing the claim FOREVER —
        # asyncio.CancelledError is a BaseException, so the existing
        # except Exception handlers cannot intercept it; only a finally
        # runs on the unwind. The cleanup cancels the task AND awaits it
        # (suppressing the child's CancelledError) — a cancelled-but-
        # pending task would otherwise linger and keep the loop alive.
        # Before execution starts the owned claim is also RELEASED: the
        # handler never ran and no intent marker exists, so a same-key
        # retry must acquire immediately instead of receiving 409 for up
        # to a full lease TTL for a request that no longer exists.
        # After execution starts the claim/intent are left untouched by
        # the cleanup: the outcome may already be committed, and the R9
        # reconcile contract (intent without response -> 409) must keep
        # working. Releasing here is always owner-token compare-and-
        # delete: a claim re-acquired by another worker (lapse path) is
        # never deleted by the stale token (Codex R3).
        execution_started = False
        try:
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
                _release_legacy_fence()
                _cancel_lease()
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
                _release_legacy_fence()
                _cancel_lease()
                return self._uncertain_outcome_response()
            # Codex R16 #3092 (P1): атомарная перепроверка владения ПЕРЕД
            # исполнением — CAS-продление lease тем же токеном. False означает,
            # что lease истёк (pre-execution фаза пережила его, несмотря на
            # eager-цикл, либо Redis мигнул) и ключ мог быть перезахвачен другим
            # воркером: исполнение здесь продублировало бы корзину. Сначала
            # перепроверяем сохранённый исход (второй владелец мог уже
            # закоммитить и записать его), иначе отказываем 409 in-flight —
            # повтор с тем же ключом разрешается штатным replay-путём.
            # Проверка выполняется ДО mark_execution_intent: если владение
            # потеряно, маркер «дошли до исполнения» не остаётся висеть без
            # исхода и не заставляет клиента применять reconcile-сценарий для
            # никогда не исполнявшегося запроса.
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                if not claim.renew(user_id, idempotency_key, claim_token):
                    _cancel_lease()
                    # Round-6: every outcome below is NON-EXECUTING — the
                    # legacy fence must not outlive this request.
                    _release_legacy_fence()
                    if claim.try_available():
                        replayed, stored_hash, stored_role = claim.load_response(user_id, idempotency_key)
                        if replayed is not None:
                            if stored_hash and stored_hash != incoming_hash:
                                return self._payload_mismatch_response()
                            # Codex R17 #3267 (P1): ветка replay после потери
                            # lease проходит ту же АКТУАЛЬНУЮ replay-авторизацию,
                            # что и все остальные replay-ветки — с флагом
                            # require_active_doctor_profile=True. Раньше здесь
                            # использовался exec_role/_exec_superuser из
                            # pre-execution проверки БЕЗ этого флага: активный
                            # User с ролью Doctor, но НЕАКТИВНЫМ профилем Doctor
                            # проходил её, сравнение ролей метку не меняет — и
                            # сохранённый ответ (с данными пациента) возвращался
                            # в обход ресурсной авторизации, которую эндпоинт
                            # (например, вызов пациента в legacy queue API)
                            # сейчас дал бы отказом 403. Отказ — НЕИСПОЛНЯЮЩИЙ
                            # (403, снапшот хранится, тело не выдаётся, хэндлер
                            # не запускается) — тот же контракт R8/R15, что и на
                            # обычных replay-путях.
                            replay_authorized, replay_role, _replay_superuser = (
                                await self._principal_authorized(
                                    request,
                                    principal_payload,
                                    require_active_doctor_profile=True,
                                )
                            )
                            if not replay_authorized:
                                logger.warning(
                                    "Idempotency lease-lapse replay refused (principal not authorized): user=%s key=%s path=%s",
                                    user_id, idempotency_key, request.url.path,
                                )
                                return _principal_refusal_response()
                            # Привязка роли — тот же контракт R4/R6, что и на
                            # обычных replay-путях. Отказ политики (permitted
                            # False / смена роли) здесь НЕ уходит в call_next —
                            # исполнение без владения ключом запрещено: 409, и
                            # повтор с тем же ключом разрешит роль штатным
                            # replay-путём.
                            permitted = self._role_permitted_for_replay(request, stored_role, replay_role, _replay_superuser)
                            if permitted is True or (
                                permitted is None and (stored_role is None or replay_role == stored_role)
                            ):
                                logger.info(
                                    "Idempotency replay after lease lapse (outcome stored by the new owner): user=%s key=%s path=%s",
                                    user_id, idempotency_key, request.url.path,
                                )
                                return replayed
                        logger.warning(
                            "Idempotency lease lapsed before execution (ownership lost): user=%s key=%s path=%s",
                            user_id, idempotency_key, request.url.path,
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
                    if claim.required:
                        # Redis умер между захватом и перепроверкой — fail-closed
                        # для required-координации (контракт R7/R15).
                        return Response(
                            status_code=503,
                            headers={"Retry-After": "2", "Cache-Control": "no-store"},
                            content=(
                                '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                                'временно недоступна: распределённая координация не отвечает. '
                                'Повторите запрос с тем же Idempotency-Key."}'
                            ),
                            media_type="application/json",
                        )
                    # Implicit ARQ-fallback без Redis: in-memory degrade —
                    # исполняем, как и прежде по контракту деградации.

            if claim is not None and claim.try_available():
                # Codex R15 #3092 (P1): для required-координации маркер обязан быть
                # ПОДТВЕРЖДЁННО распределённым непосредственно перед call_next.
                # Прежний best-effort SET допускал окно: Redis падает после
                # предыдущих проверок (или SET не удался) — маркер существует
                # только локально, второй воркер его не видит, и потерянный ответ
                # после истечения lease приводил к повторному исполнению записи
                # (дубликаты визитов/счетов/очереди).
                try:
                    if not (claim_acquired and claim_token is not None):
                        # PR 3319 (codex P1): unique anonymous marker — the
                        # cleanup of THIS attempt can then only delete a
                        # marker this attempt wrote.
                        tokenless_marker = uuid.uuid4().hex
                    intent_confirmed = claim.mark_execution_intent(
                        user_id,
                        idempotency_key,
                        owner_token=(
                            claim_token
                            if (claim_acquired and claim_token is not None)
                            else None
                        ),
                        tokenless_marker=tokenless_marker,
                    )
                except _IntentClaimLost:
                    # Keep the same key: another attempt may still be running
                    # or may already have committed. Never run this handler or
                    # invoke failed-write intent cleanup after an owner refusal.
                    # Round-6: a still-owned legacy fence is released; if the
                    # fence already lapsed (the new owner fenced it), this is
                    # a compare-and-delete no-op.
                    _release_legacy_fence()
                    return Response(
                        status_code=409,
                        headers={"Retry-After": "1", "Cache-Control": "no-store"},
                        content=(
                            '{"code": "idempotency_in_flight", "detail": '
                            '"Request ownership changed. Retry with the same key."}'
                        ),
                        media_type="application/json",
                    )
                if claim.required and not intent_confirmed:
                    logger.warning(
                        "Idempotency execution intent NOT confirmed in distributed store: "
                        "user=%s key=%s path=%s — refusing keyed write",
                        user_id, idempotency_key, request.url.path,
                    )
                    if claim_acquired and claim_token is not None:
                        claim.release(user_id, idempotency_key, claim_token)
                    # Махмудбек R18 #3277 (P2): intent НЕ подтверждён, хендлер
                    # не запускался — попытка обязана убрать СОБСТВЕННЫЕ
                    # маркеры. Безусловно записанный mark_execution_intent
                    # локальный mirror переживал отказ: восстановление Redis
                    # и истечение lease давали повтору ложный 409
                    # idempotency_uncertain_outcome для операции, которая
                    # заведомо НЕ дошла до исполнения — recovery-тупик,
                    # требующий ручной сверки/смены ключа. Очистка
                    # распределённого маркера привязана к токену попытки:
                    # confirmed=False не отличает «не записан» от «записан,
                    # но ответ потерян», поэтому ключ, дозаписавшийся despite
                    # отказа, удаляется только если в нём токен ЭТОЙ попытки.
                    # Чужой маркер (предыдущая попытка с неизвестным исходом)
                    # не задевается — до его защиты попытка не доходит:
                    # uncertain-проверка выше отсеивает. Остаточный риск —
                    # маркер, дозаписавшийся ПОСЛЕ очистки: повтор получит
                    # консервативный 409 reconcile, никогда не дубль.
                    if claim_acquired and claim_token is not None:
                        claim.clear_execution_intent_if_owner(user_id, idempotency_key, claim_token)
                    # Локальный mirror можно снять безусловно: reaching mark
                    # означает, что uncertain-проверка выше НЕ нашла ни
                    # распределённого, ни локального маркера — значит
                    # локальная запись создана именно ЭТОЙ попыткой.
                    _clear_local_execution_intent(user_id, idempotency_key)
                    _release_legacy_fence()
                    _cancel_lease()
                    return Response(
                        status_code=503,
                        headers={"Retry-After": "2", "Cache-Control": "no-store"},
                        content=(
                            '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                            'временно недоступна: распределённая координация не отвечает. '
                            'Повторите запрос с тем же Idempotency-Key."}'
                        ),
                        media_type="application/json",
                    )
                if not intent_confirmed and not (claim_acquired and claim_token is not None):
                    # PR 3319 (owner P2, main 1033c3c7b3): Redis восстановился
                    # МЕЖДУ uncertain-проверкой (пока падал — локальная ветка)
                    # и этим гейтом. Попытка без claim-токена не имеет права
                    # исполнять поверх чужого intent-маркера: SET NX сообщил,
                    # что ключ уже охраняется другой попыткой (исполняющейся
                    # или с неизвестным исходом — защита R9). Отказ
                    # НЕИСПОЛНЯЮЩИЙ 409; ниже убирается маркер ЭТОЙ попытки
                    # (уникальный tokenless_marker — чужой не задевается).
                    logger.warning(
                        "Idempotency tokenless attempt refused over a foreign intent marker: "
                        "user=%s key=%s path=%s",
                        user_id,
                        idempotency_key,
                        request.url.path,
                    )
                    # PR 3319 (codex P2): False означает и NX-конфликт, и
                    # потерянный транспортный ответ SET (маркер мог ДОЗЕМЛИТЬСЯ).
                    # Убираем маркер ЭТОЙ попытки (уникальное значение — чужой
                    # маркер не задевается) и локальный mirror: повтор после
                    # восстановления не получает ложный uncertain-outcome для
                    # никогда не исполнявшейся операции.
                    claim.clear_execution_intent_owned(
                        user_id, idempotency_key, tokenless_marker
                    )
                    _release_legacy_fence()
                    _cancel_lease()
                    return Response(
                        status_code=409,
                        headers={"Retry-After": "1", "Cache-Control": "no-store"},
                        content=(
                            '{"code": "idempotency_in_flight", "detail": '
                            '"Request ownership changed. Retry with the same key."}'
                        ),
                        media_type="application/json",
                    )
                if legacy_fence_ns is not None and legacy_fence_token is not None:
                    # Round-7 (owner P1, PR #3340): pre-handler LEGACY
                    # execution intent, bound to the fence owner. The old
                    # version's only unknown-outcome guard is the intent
                    # marker in ITS namespace — the round-6 flow wrote one
                    # there only on the crash path, so a Redis death ON the
                    # post-commit store_response() left old workers an EMPTY
                    # legacy namespace once the fence lease lapsed: no
                    # response, no intent, no claim — they re-executed the
                    # committed write. With the intent pre-written under the
                    # still-held fence, the same failure now leaves old
                    # workers their own R9 reconcile (409 uncertain) instead
                    # of a blank slate. Best-effort on transport: a degraded
                    # Redis cannot record the marker anywhere, and the
                    # required gate below refuses to execute without it.
                    try:
                        legacy_intent_confirmed = claim.mark_execution_intent(
                            legacy_fence_ns,
                            idempotency_key,
                            owner_token=legacy_fence_token,
                        )
                    except _IntentClaimLost:
                        # The fence lease lapsed mid-flight and another
                        # (old-version) worker now owns the legacy claim —
                        # executing beside it would run two versions of the
                        # write in parallel. Refuse non-executing: clear THIS
                        # attempt's own new-namespace marker (the uncertain
                        # check above proved it was ours), release the claim.
                        logger.warning(
                            "Idempotency legacy fence lost before execution: "
                            "user=%s key=%s path=%s — refusing in-flight",
                            user_id, idempotency_key, request.url.path,
                        )
                        if claim_acquired and claim_token is not None:
                            claim.clear_execution_intent_if_owner(
                                user_id, idempotency_key, claim_token
                            )
                            _clear_local_execution_intent(user_id, idempotency_key)
                            if claim.try_available():
                                claim.release(user_id, idempotency_key, claim_token)
                        _release_legacy_fence()
                        _cancel_lease()
                        return Response(
                            status_code=409,
                            headers={"Retry-After": "1", "Cache-Control": "no-store"},
                            content=(
                                '{"code": "idempotency_in_flight", "detail": '
                                '"Request ownership changed. Retry with the same key."}'
                            ),
                            media_type="application/json",
                        )
                    if claim.required and not legacy_intent_confirmed:
                        # Transport died BETWEEN the two intent marks: the
                        # legacy guard could not be recorded and the fence
                        # can no longer be renewed. A required write must not
                        # run with its migration guard gone — the success
                        # path would have nothing durable to leave old
                        # workers. Fail closed BEFORE the handler; the
                        # client retries the same key after recovery.
                        logger.warning(
                            "Idempotency legacy intent NOT confirmed (required Redis "
                            "degraded between intent marks): user=%s key=%s path=%s — "
                            "refusing keyed write",
                            user_id, idempotency_key, request.url.path,
                        )
                        if claim_acquired and claim_token is not None:
                            claim.clear_execution_intent_if_owner(
                                user_id, idempotency_key, claim_token
                            )
                            _clear_local_execution_intent(user_id, idempotency_key)
                            claim.release(user_id, idempotency_key, claim_token)
                        _clear_local_execution_intent(legacy_fence_ns, idempotency_key)
                        # Round-8 (owner P2, PR #3340): lost-ack cleanup — the
                        # mark EVAL may have LANDED server-side while the
                        # client lost the reply (confirmed=False covers both
                        # "not written" and "written, response lost"). Without
                        # this owner-guarded delete the orphaned legacy intent
                        # holds a FALSE 24 h idempotency_uncertain_outcome
                        # over a request that provably never reached the
                        # handler. The fence token binds the delete to THIS
                        # attempt's marker — a foreign attempt's unknown-
                        # outcome protection is never touched.
                        claim.clear_execution_intent_if_owner(
                            legacy_fence_ns, idempotency_key, legacy_fence_token
                        )
                        _release_legacy_fence()
                        _cancel_lease()
                        return Response(
                            status_code=503,
                            headers={"Retry-After": "2", "Cache-Control": "no-store"},
                            content=(
                                '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                                'временно недоступна: распределённая координация не отвечает. '
                                'Повторите запрос с тем же Idempotency-Key."}'
                            ),
                            media_type="application/json",
                        )
            elif claim is not None and claim.required:
                # Codex R15 #3092 (P1): Redis упал между ранним гейтом и точкой
                # исполнения — координация не может быть подтверждена прямо перед
                # call_next: fail closed, ничего не исполняем.
                logger.warning(
                    "Idempotency coordination lost before execution: "
                    "user=%s key=%s path=%s — refusing keyed write",
                    user_id, idempotency_key, request.url.path,
                )
                if claim_acquired and claim_token is not None:
                    claim.release(user_id, idempotency_key, claim_token)
                _release_legacy_fence()
                _cancel_lease()
                return Response(
                    status_code=503,
                    headers={"Retry-After": "2", "Cache-Control": "no-store"},
                    content=(
                        '{"code": "idempotency_unavailable", "detail": "Идемпотентность '
                        'временно недоступна: распределённая координация не отвечает. '
                        'Повторите запрос с тем же Idempotency-Key."}'
                    ),
                    media_type="application/json",
                )
            else:
                _mark_local_execution_intent(user_id, idempotency_key)

            # Codex R17 #3267 (P2): граница R9 — начиная с этой точки гибель
            # запроса оставляет исход НЕИЗВЕСТНЫМ (маркер intent уже стоит,
            # либо хэндлер вот-вот начнёт исполняться). Cleanup в finally
            # больше не трогает claim/intent — истечение lease и
            # reconcile-контракт R9 остаются единственным безопасным путём.
            execution_started = True

            # Execute handler under the lease-renewal loop (Codex R2 #3092 P2).
            # Codex R16 #3092 (P1): the loop is started EAGERLY right after
            # acquisition and ownership is re-verified atomically above — by
            # this point the lease is freshly extended and owned by THIS worker.
            # If the worker dies, the loop dies with it and the short lease
            # expires on its own (no 24h 409 lockout).
            # Codex R17 #3267 (P2): отмена/исключение здесь больше не требует
            # ручного _cancel_lease — внешний finally охватывает весь срок
            # жизни lease-задачи. except Exception сохраняет только
            # семантику R9: release claim, intent НЕ стирать.
            try:
                response = await call_next(request)
            except Exception:
                # Handler crashed — release the claim so the client can retry.
                # Codex R9 #3092 (P1): the intent marker is KEPT — the crash may
                # have happened after the endpoint's commit, so the outcome stays
                # unknown and the retry must reconcile (409), not re-execute.
                if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                    claim.release(user_id, idempotency_key, claim_token)
                # Round-6 (owner P1): the legacy fence stays HELD (its lease
                # expires on its own) and the unknown-outcome intent is
                # DUAL-WRITTEN into the legacy namespace so OLD-version
                # workers reconcile (their own R9 contract) instead of
                # re-executing a possibly-committed write once the fence
                # lease lapses. Best-effort: a degraded transport simply
                # leaves the fence to lapse.
                if legacy_fence_ns is not None and legacy_fence_token is not None:
                    try:
                        # Round-7 (owner P1): owner-bound re-mark. The
                        # pre-handler legacy intent is already in place; this
                        # only covers the sliver where its write hit a
                        # transport failure and Redis recovered DURING the
                        # handler. _IntentClaimLost (the fence lapsed
                        # mid-handler) is deliberately swallowed — an
                        # old-version worker owns the legacy claim then, and
                        # its own markers govern the key.
                        claim.mark_execution_intent(
                            legacy_fence_ns,
                            idempotency_key,
                            owner_token=legacy_fence_token,
                        )
                    except Exception:  # pragma: no cover - best-effort marker
                        pass
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
                # Codex R4 #3092 (P1): bind the stored response to the authorized
                # ROLE. Codex R6 #3092 (P1): the role was established BEFORE
                # execution — retain the committed outcome unconditionally (no
                # post-commit DB re-query to lose), the replay re-checks it.
                # Round-7 (owner P1 #2): patient outcomes live in the ATOMIC
                # local entry (binding + payload hash + snapshot, one LRU
                # fate); staff outcomes keep the separate response cache.
                if patient_scope and origin_ns:
                    _local_patient_outcome_store(
                        origin_ns,
                        idempotency_key,
                        patient_scope,
                        cached_response,
                        incoming_hash,
                        exec_role,
                    )
                else:
                    _idempotency_cache.set(user_id, idempotency_key, cached_response, incoming_hash, principal_role=exec_role)
                # Round-7 (owner P1, PR #3340): the distributed stores are
                # CONFIRMED writes. A transport failure swallowed inside
                # store_response() previously looked identical to success —
                # the flow then deleted the intent markers while NO snapshot
                # had landed anywhere, and after the fence lease lapsed an
                # old-version worker found an empty legacy namespace and
                # re-executed the committed write. Now both stores report
                # their outcome and the intent cleanup is gated on it.
                outcome_durable = True
                if claim is not None and claim_acquired and claim_token is not None:
                    stored_current = False
                    stored_legacy = True
                    scope_extended = True
                    if claim.try_available():
                        if patient_scope and origin_ns:
                            # Round-8 (owner P2, PR #3340): the response
                            # snapshot and the scope-binding extension are
                            # ONE atomic script for patient operations — the
                            # binding can never expire before the outcome it
                            # guards, and a Redis failure on the extension
                            # now also means the response did not land (no
                            # window where a live snapshot outlives its card
                            # guard and a re-linked card could re-bind the
                            # key). The extension RESTORES an absent binding
                            # under this attempt's generation (a stale
                            # attempt's in-between cleanup cannot orphan the
                            # execution).
                            stored_current, scope_extended = (
                                claim.store_response_with_scope(
                                    user_id,
                                    idempotency_key,
                                    cached_response,
                                    payload_hash=incoming_hash,
                                    principal_role=exec_role,
                                    operation_scope=op_scope,
                                    origin_ns=origin_ns,
                                    patient_scope=patient_scope,
                                    generation=attempt_generation,
                                )
                            )
                        else:
                            # Codex R1 #3092 (P1): snapshot for CROSS-WORKER replay.
                            # Codex R2 #3092 (P1): the snapshot carries the payload
                            # hash — changed data is never replayed as the
                            # original success.
                            stored_current = claim.store_response(user_id, idempotency_key, cached_response, payload_hash=incoming_hash, principal_role=exec_role, operation_scope=op_scope)
                        # Round-6 (owner P1): DUAL-WRITE the committed outcome to
                        # the LEGACY namespace WHILE the fence is still held — an
                        # old-version worker that acquires the legacy claim after
                        # the fence lease lapses must find this snapshot and
                        # replay it, never an empty namespace it would re-execute.
                        # (Patient operations never hold the fence.) Round-8:
                        # the legacy snapshot carries the operation_scope stamp.
                        if (
                            legacy_fence_ns is not None
                            and legacy_fence_token is not None
                        ):
                            stored_legacy = claim.store_response(
                                legacy_fence_ns,
                                idempotency_key,
                                cached_response,
                                payload_hash=incoming_hash,
                                principal_role=exec_role,
                                operation_scope=op_scope,
                            )
                    claim.release(user_id, idempotency_key, claim_token)
                    # Round-8 (owner P2, PR #3340): the PATIENT outcome is
                    # durable only when the scope binding extension was
                    # CONFIRMED too — a binding that expired (or was never
                    # confirmed) reopens the re-link window even though the
                    # snapshot itself is stored.
                    outcome_durable = bool(
                        stored_current and stored_legacy and scope_extended
                    )
                if not outcome_durable:
                    # Round-7 (owner P1): Redis died AFTER the DB commit and
                    # BEFORE the snapshots were confirmed. The write IS
                    # committed and the client still receives its 2xx, but
                    # every unknown-outcome guard stays up: the
                    # new-namespace intent (Redis marker + local mirror),
                    # the pre-handler LEGACY intent and the fence (its
                    # renewal task is cancelled in finally — the lease
                    # lapses within 90 s and old-version workers reconcile
                    # against the legacy intent instead of finding an empty
                    # namespace and re-executing the committed write). A
                    # same-key retry reconciles (409 uncertain_outcome).
                    logger.warning(
                        "Idempotency outcome NOT durably stored (Redis degraded after "
                        "commit): user=%s key=%s path=%s — keeping unknown-outcome "
                        "guards (intents + legacy fence)",
                        user_id, idempotency_key, request.url.path,
                    )
                    return Response(
                        content=body_bytes,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                # Round-7 (owner P1): the pre-handler LEGACY intent is cleared
                # FIRST — bound to the fence token that wrote it. The clear
                # MUST run before _release_legacy_fence(), which nulls the
                # fence token: a compare-and-delete against None would
                # silently skip the marker.
                if legacy_fence_ns is not None and legacy_fence_token is not None:
                    claim.clear_execution_intent_owned(
                        legacy_fence_ns,
                        idempotency_key,
                        legacy_fence_token,
                    )
                _release_legacy_fence()
                # Codex R9 #3092 (P1): outcome is now durable — drop the intent
                # marker so later same-key requests replay normally.
                # PR 3319: удаление привязано к маркеру ЭТОЙ попытки —
                # владеющая попытка сравнивает свой claim-токен, деградировшая
                # без токена — анонимное значение своего SET NX. Чужой маркер
                # (неизвестный исход другой попытки, R9) не удаляется даже
                # когда Redis-вид этой попытки восстановился после деградации.
                if claim is not None and claim.try_available():
                    claim.clear_execution_intent_owned(
                        user_id,
                        idempotency_key,
                        (
                            claim_token
                            if (claim_acquired and claim_token is not None)
                            else tokenless_marker
                        ),
                    )
                else:
                    _clear_local_execution_intent(user_id, idempotency_key)
                    if legacy_fence_ns is not None:
                        _clear_local_execution_intent(legacy_fence_ns, idempotency_key)
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
                # PR 3319: ownership-guarded known-outcome cleanup — see the
                # success path above; a degraded attempt removes only its own
                # unique marker, never a foreign attempt's intent.
                claim.clear_execution_intent_owned(
                    user_id,
                    idempotency_key,
                    (
                        claim_token
                        if (claim_acquired and claim_token is not None)
                        else tokenless_marker
                    ),
                )
                if legacy_fence_ns is not None and legacy_fence_token is not None:
                    # Round-7 (owner P1): the pre-handler LEGACY intent is a
                    # known-outcome cleanup too — the endpoint returned
                    # without committing, so old workers must be allowed to
                    # re-run this request after the fence is released.
                    claim.clear_execution_intent_owned(
                        legacy_fence_ns,
                        idempotency_key,
                        legacy_fence_token,
                    )
            else:
                _clear_local_execution_intent(user_id, idempotency_key)
                if legacy_fence_ns is not None:
                    _clear_local_execution_intent(legacy_fence_ns, idempotency_key)
            if claim is not None and claim.try_available() and claim_acquired and claim_token is not None:
                # Round-8 (owner P1 #2, PR #3340): the scope binding of a
                # KNOWN non-2xx is dropped BEFORE the claim release — the
                # old order (release first, delete last) opened a race in
                # which a successor attempt with a corrected body acquired
                # the freed claim and started executing while THIS attempt
                # was still deleting "its" binding: A and B share the same
                # patient scope, so the old scope-only guard could not tell
                # the generations apart, B's in-flight binding was deleted
                # and its completed outcome was left WITHOUT a binding (a
                # later re-link could re-bind the key and execute a second
                # write). The full-value compare-and-delete (scope AND this
                # attempt's generation) is the second half of the guard.
                if patient_scope and origin_ns:
                    _local_scope_binding_drop(origin_ns, idempotency_key, patient_scope)
                    claim.clear_scope_binding(
                        origin_ns, idempotency_key, patient_scope, attempt_generation
                    )
                claim.release(user_id, idempotency_key, claim_token)
            else:
                # Degraded transport: the local twin is still dropped before
                # the (skipped) release; the Redis compare-and-delete is
                # retried by the same-key retry's own lifecycle.
                if patient_scope and origin_ns:
                    _local_scope_binding_drop(origin_ns, idempotency_key, patient_scope)
            # Round-6: a returned non-2xx is a KNOWN outcome (validation
            # refused, nothing committed) — the fence is released; an old
            # worker retry would re-run a request that provably did nothing.
            _release_legacy_fence()
            return response
        finally:
            if lease_task is not None:
                lease_task.cancel()
                try:
                    await lease_task
                except asyncio.CancelledError:
                    pass
            if legacy_lease_task is not None:
                legacy_lease_task.cancel()
                try:
                    await legacy_lease_task
                except asyncio.CancelledError:
                    pass
            if (
                not execution_started
                and claim is not None
                and claim_acquired
                and claim_token is not None
            ):
                # Nothing was executed (no intent marker, handler never
                # ran): free the claim now instead of letting the retry
                # see a stale 409 until the lease TTL lapses.
                if claim.try_available():
                    claim.release(user_id, idempotency_key, claim_token)
            if not execution_started and not legacy_fence_keep_on_exit:
                # Round-6: nothing executed and the fence is not deliberately
                # kept (the in-flight refusal that shields a NEW worker's
                # execution) — free it; a held-but-dead request must not
                # block old-version workers longer than its lease anyway.
                _release_legacy_fence()

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

    @staticmethod
    def _scope_mismatch_response() -> Response:
        """409 for a key replayed under a DIFFERENT patient card (round-4
        owner P1). One Idempotency-Key means one booking attempt: the key is
        bound to the card it first ran under and never follows a re-link, so
        a retry after the account was re-linked cannot create a second
        appointment for another patient. The re-linked card books with a NEW
        key; the same-key retry is a non-executing refusal (the bound
        snapshot, if any, is kept)."""
        return Response(
            status_code=409,
            headers={"Cache-Control": "no-store"},
            content=(
                '{"code": "idempotency_scope_mismatch", "detail": "This Idempotency-Key belongs to a different '
                'patient card. The original attempt may already be saved — do '
                'not retry it for another card; verify the record state and '
                'use a NEW key for a new booking."}'
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
    def _namespace(
        canonical_user_id: int,
        operation_scope: str = "",
        patient_scope: str = "",
    ) -> str:
        """Stable per-principal cache namespace from the CANONICAL user id.

        Codex R11 #3092 (P1): the raw ``sub`` differs between token shapes
        (mobile login: sub=username; /mobile/auth/refresh: sub=user.id +
        username claim) — hashing it moved the same user's keys to another
        namespace after refresh. The namespace is derived from the DB-
        resolved user id, so every token shape of the same account maps to
        ONE namespace. Hashed: no usernames/ids in Redis keys.

        Round-3 (owner P1/P2): the namespace additionally binds the
        OPERATION (method + normalized path) and, for Patient principals,
        the CURRENT active card id. One key therefore cannot alias two
        operations sharing a request DTO, and a snapshot committed under
        card A can never be replayed after the account is re-linked to
        card B (the re-linked account resolves a different patient scope,
        i.e. a different namespace, and executes fresh).
        """
        subject = f"user:{int(canonical_user_id)}"
        if operation_scope:
            subject = f"{subject}|op:{operation_scope}"
        if patient_scope:
            subject = f"{subject}|{patient_scope}"
        return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:32]

    async def _principal_authorized(
        self,
        request: Request,
        principal_payload: dict[str, Any],
        require_active_doctor_profile: bool = False,
    ) -> tuple[bool, str | None, bool]:
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
                _check_principal_authorized_sync,
                request,
                user_id,
                username,
                jti,
                require_active_doctor_profile,
            )
        except Exception:  # pragma: no cover - to_thread failure is fail-closed
            logger.warning("Idempotency principal check crashed; refusing replay", exc_info=True)
            return False, None, False

    @staticmethod
    def _endpoint_allowed_roles(request: Any) -> frozenset[str] | None:
        """Resolve the endpoint's require_roles policy (Codex R6 #3092 P1).

        Returns the lowercase role labels the matched route accepts:
        - empty frozenset: the route carries no require_roles dependency —
          the resolver could not find a published policy. This does NOT
          mean unrestricted access: the endpoint may enforce authorization
          INLINE (e.g. queue.py combines get_current_user +
          staff_authorization_service.can_read_queue() + a doctor-ownership
          check). The replay policy treats it as unknown — see
          _role_permitted_for_replay.
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
            # Codex R12 #3092 (P1): NO require_roles dependency on the matched
            # route means the middleware cannot statically evaluate the
            # endpoint's authorization — the handler may enforce it INLINE
            # (e.g. queue.py: get_current_user + can_read_queue +
            # doctor-ownership). An empty allowed set is INSUFFICIENT policy
            # information, not unrestricted access: fall back to the
            # conservative R4 comparison — same role replays, a changed role
            # falls through so the inline authorization re-runs for real.
            return None
        if not current_role:
            return False
        return current_role.strip().lower() in allowed
