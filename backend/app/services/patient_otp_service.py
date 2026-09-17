"""Patient portal OTP foundation (Phase 0, PR-A1; extended by PR-A2).

Identity contract (plan v2/v3, owner-approved):
    Phone is a POSSESSION factor, not patient identity. This module
    deliberately performs NO patient linking — PR-A2 binds an
    activation token (exact Patient.id) + verified phone atomically.

Production-correct Redis-backed OTP (owner gate #1, v3):
    - code stored ONLY as sha256 hash, TTL 300s, max 3 attempts
    - per-phone resend cooldown (60s) + hourly cap (5/hour)
    - single-use opaque verification grant (Redis GETDEL semantics)
    - locale whitelist ru|uz, single-language SMS, no PHI in message
    - MockSMSProvider is forbidden outside TESTING (provider is env-driven;
      missing Eskiz/PlayMobile credentials blocks production enablement,
      NOT this PR)

Backend selection:
    TESTING=1  -> in-memory KV (owner-approved unit/dev fallback ONLY)
    otherwise  -> Redis (REDIS_URL env, falling back to ARQ_REDIS_URL);
                  Redis unavailability fails CLOSED with a generic 503
                  (never silently degrades to process-local storage).

Login resolver (owner correction #1, v3):
    UserProfile.phone is NOT unique and crud_user.get_user_by_phone()
    uses .limit(1) — forbidden here. The resolver fetches ALL active
    verified Patient-role users for the normalized phone and proceeds
    only on EXACTLY ONE candidate; 0 or >1 candidates fail closed with
    a generic 401. Never .first().
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.sms_providers import get_sms_manager

logger = logging.getLogger(__name__)

# --- Canonical phone normalization (single source for patient-access) ---
_PHONE_RE = re.compile(r"^\+998\d{9}$")

# --- OTP parameters (aligned with staff phone_verification_service) ---
CODE_TTL_SECONDS = 300
MAX_ATTEMPTS = 3
RESEND_COOLDOWN_SECONDS = 60
HOURLY_SEND_CAP = 5
GRANT_TTL_SECONDS = 600

LOCALES = ("ru", "uz")
_DEFAULT_LOCALE = "ru"

_OTP_MESSAGES = {
    "ru": "Код входа: {code}. Действителен 5 минут.",
    "uz": "Kod: {code}. Amal qilish muddati: 5 daqiqa.",
}

# --- Neutral, non-enumerable error texts (client-visible) ---
ERR_RATE_LIMITED = "Слишком много запросов. Повторите позже."
ERR_SMS_UNAVAILABLE = "Не удалось отправить SMS. Попробуйте позже."
ERR_OTP_INVALID = "Неверный код или срок его действия истёк."
ERR_LOGIN_GENERIC = "Не удалось выполнить вход. Проверьте номер и код."

# --- Redis key namespaces ---
# Login OTP keys (PR-A1): patotp:{cd,cap,code,meta,grant}:{...}
_PREFIX = "patotp"
_NS_LOGIN = _PREFIX
# Activation OTP keys (PR-A2): patact:{cd,cap,code,meta}:{...} — isolated
# from login limits/codes so neither flow can consume the other's state.
_NS_ACTIVATION = "patact"
_OTP_NAMESPACES = (_NS_LOGIN, _NS_ACTIVATION)


def normalize_phone(raw: str) -> str | None:
    """Canonical +998XXXXXXXXX normalization; None when not matchable."""
    cleaned = re.sub(r"[^\d+]", "", raw or "")
    return cleaned if _PHONE_RE.match(cleaned) else None


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclass
class PatientOtpError(Exception):
    status_code: int
    detail: str


def _testing_mode() -> bool:
    return os.getenv("TESTING", "").strip() == "1"


class _MemoryBackend:
    """Owner-approved TESTING-only fallback. NEVER selected in production."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}
        self._counters: dict[str, tuple[int, float]] = {}

    def _alive(self, expires_at: float) -> bool:
        return time.monotonic() < expires_at

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry and self._alive(entry[1]):
            return entry[0]
        self._store.pop(key, None)
        return None

    def set(self, key: str, value: str, ttl: int) -> None:
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def getdel(self, key: str) -> str | None:
        value = self.get(key)
        self._store.pop(key, None)
        return value

    def incr_with_ttl(self, key: str, ttl: int) -> int:
        count, expires_at = self._counters.get(key, (0, time.monotonic() + ttl))
        if not self._alive(expires_at):
            count, expires_at = 0, time.monotonic() + ttl
        count += 1
        self._counters[key] = (count, expires_at)
        return count

    # TEST HOOK: populated ONLY when TESTING=1 (never in production path).
    last_sent_code: dict[str, str] = {}


class _RedisBackend:
    def __init__(self) -> None:
        import redis  # local import: keeps TESTING path dependency-free

        url = os.getenv("REDIS_URL", "").strip() or settings.ARQ_REDIS_URL
        self._client = redis.Redis.from_url(
            url, decode_responses=True, socket_connect_timeout=2
        )
        self._client.ping()

    def _run(self, operation, *args, **kwargs):
        """Normalize INFRASTRUCTURE failures into PatientOtpError(503).

        Codex P2 (PR #3320 round 2): a backend that was created SUCCESSFULLY
        can still DROP mid-session (connection reset / socket timeout).
        Callers contract on PatientOtpError — a raw redis.ConnectionError
        escaping from get/set/delete/getdel/pipeline surfaced as an
        undocumented 500 (including AFTER the activation DB commit).
        Only connection/timeout failures are translated; ResponseError
        (a programming bug) must stay loud, not masquerade as 503.
        Logged WITHOUT key material (keys embed normalized phones)."""
        import redis  # local import: keeps TESTING path dependency-free

        try:
            return operation(*args, **kwargs)
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.error("patient OTP KV backend failure: %s", type(exc).__name__)
            raise PatientOtpError(503, ERR_SMS_UNAVAILABLE) from exc

    def get(self, key: str) -> str | None:
        return self._run(self._client.get, key)

    def set(self, key: str, value: str, ttl: int) -> None:
        self._run(self._client.set, key, value, ex=ttl)

    def delete(self, key: str) -> None:
        self._run(self._client.delete, key)

    def getdel(self, key: str) -> str | None:
        return self._run(self._client.execute_command, "GETDEL", key)

    def incr_with_ttl(self, key: str, ttl: int) -> int:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl, nx=True)
        count, _ = self._run(pipe.execute)
        return int(count)


class PatientOtpService:
    """Redis-backed patient OTP + fail-closed login resolver."""

    def __init__(self) -> None:
        self._backend: _MemoryBackend | _RedisBackend | None = None

    # -- backend ---------------------------------------------------------
    def _get_backend(self) -> _MemoryBackend | _RedisBackend:
        if self._backend is None:
            if _testing_mode():
                self._backend = _MemoryBackend()
            else:
                try:
                    self._backend = _RedisBackend()
                except Exception as exc:  # noqa: BLE001 - fail closed
                    logger.error("patient OTP: Redis unavailable: %s", exc)
                    raise PatientOtpError(503, ERR_SMS_UNAVAILABLE) from exc
        return self._backend

    def get_backend(self) -> _MemoryBackend | _RedisBackend:
        """Public KV access for the patient-access domain (PR-A2 activation
        service reuses the SAME backend selection: TESTING in-memory /
        production Redis with fail-closed 503)."""
        return self._get_backend()

    def _reset_backend_for_tests(self) -> None:
        self._backend = None

    # -- request OTP -----------------------------------------------------
    async def send_login_otp(
        self, phone: str, locale: str | None = None
    ) -> dict[str, Any]:
        """Send a login OTP. Raises PatientOtpError only for number-neutral
        failures (rate limits / infrastructure); response body is identical
        regardless of any patient state."""
        return await self._send_otp(_NS_LOGIN, phone, locale)

    async def send_activation_otp(
        self, phone: str, locale: str | None = None
    ) -> dict[str, Any]:
        """Send an ACTIVATION OTP (PR-A2). Same guarantees as login OTP,
        but fully isolated namespace: activation codes/limits never
        interact with login OTP state."""
        return await self._send_otp(_NS_ACTIVATION, phone, locale)

    async def _send_otp(
        self, namespace: str, phone: str, locale: str | None = None
    ) -> dict[str, Any]:
        if namespace not in _OTP_NAMESPACES:
            raise ValueError(f"unknown OTP namespace: {namespace}")
        normalized = normalize_phone(phone)
        if not normalized:
            raise PatientOtpError(400, ERR_OTP_INVALID)
        lang = locale if locale in LOCALES else _DEFAULT_LOCALE

        backend = self._get_backend()
        cooldown_key = f"{namespace}:cd:{normalized}"
        if backend.get(cooldown_key) is not None:
            raise PatientOtpError(429, ERR_RATE_LIMITED)

        cap_key = f"{namespace}:cap:{normalized}"
        if backend.incr_with_ttl(cap_key, 3600) > HOURLY_SEND_CAP:
            raise PatientOtpError(429, ERR_RATE_LIMITED)

        provider = (settings.SMS_DEFAULT_PROVIDER or "").strip().lower()
        if provider == "mock" and not _testing_mode():
            # Owner gate #6: Mock SMS is dev/test-only for patient access.
            logger.error("patient OTP: MockSMSProvider refused outside TESTING")
            raise PatientOtpError(503, ERR_SMS_UNAVAILABLE)

        code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        message = _OTP_MESSAGES[lang].format(code=code)

        try:
            sms_manager = get_sms_manager()
            result = await sms_manager.send_sms(phone=normalized, text=message)
        except Exception as exc:  # noqa: BLE001
            logger.error("patient OTP: send_sms error: %s", exc)
            raise PatientOtpError(503, ERR_SMS_UNAVAILABLE) from exc
        if not getattr(result, "success", False):
            logger.error(
                "patient OTP: send_sms failed: %s", getattr(result, "error", "")
            )
            raise PatientOtpError(503, ERR_SMS_UNAVAILABLE)

        backend.set(
            f"{namespace}:code:{normalized}", _hash_code(code), CODE_TTL_SECONDS
        )
        backend.set(cooldown_key, "1", RESEND_COOLDOWN_SECONDS)

        if _testing_mode():
            # Backward-compat: login-OTP hook keeps bare-phone keys (PR-A1
            # tests); namespaced keys avoid cross-flow test ambiguity.
            hook_key = (
                normalized if namespace == _NS_LOGIN else f"{namespace}:{normalized}"
            )
            backend.last_sent_code[hook_key] = code  # type: ignore[attr-defined]

        logger.info(
            "patient OTP sent: flow=%s phone_fingerprint=%s provider=%s",
            namespace,
            hashlib.sha256(normalized.encode()).hexdigest()[:12],
            getattr(result, "provider", "unknown"),
        )
        return {"phone": normalized, "locale": lang}

    # -- verify OTP ------------------------------------------------------
    def verify_login_otp(self, phone: str, code: str) -> dict[str, Any]:
        """Verify code, return single-use verification grant.

        All failure modes share ONE generic 400 response (anti-enum)."""
        normalized = self._verify_otp_code(_NS_LOGIN, phone, code)
        grant = secrets.token_urlsafe(32)
        self._get_backend().set(
            f"{_NS_LOGIN}:grant:{grant}", normalized, GRANT_TTL_SECONDS
        )
        return {"verification_grant": grant, "expires_in": GRANT_TTL_SECONDS}

    def verify_activation_otp(self, phone: str, code: str) -> str:
        """Verify an ACTIVATION OTP (PR-A2); returns the normalized phone.
        No grant is issued — activation proceeds directly in one service
        call (OTP single-use, same generic 400 on every failure)."""
        return self._verify_otp_code(_NS_ACTIVATION, phone, code)

    def _verify_otp_code(self, namespace: str, phone: str, code: str) -> str:
        if namespace not in _OTP_NAMESPACES:
            raise ValueError(f"unknown OTP namespace: {namespace}")
        normalized = normalize_phone(phone)
        if not normalized or not re.fullmatch(r"\d{6}", code or ""):
            raise PatientOtpError(400, ERR_OTP_INVALID)

        backend = self._get_backend()
        code_key = f"{namespace}:code:{normalized}"
        raw = backend.get(code_key)
        if raw is None:
            raise PatientOtpError(400, ERR_OTP_INVALID)

        if not hmac.compare_digest(raw, _hash_code(code)):
            attempts = self._bump_attempts(backend, code_key)
            if attempts >= MAX_ATTEMPTS:
                backend.delete(code_key)
            logger.info("patient OTP mismatch: phone_fingerprint=%s", normalized[:7])
            raise PatientOtpError(400, ERR_OTP_INVALID)

        backend.delete(code_key)  # single-use code
        return normalized

    def _bump_attempts(self, backend: Any, code_key: str) -> int:
        """Best-effort attempt counter; corrupt/missing entries stay generic."""
        try:
            record = backend.get(f"meta:{code_key}")
            attempts = (int(record) if record else 0) + 1
            backend.set(f"meta:{code_key}", str(attempts), CODE_TTL_SECONDS)
            return attempts
        except Exception:  # noqa: BLE001
            return 0

    # -- grant -----------------------------------------------------------
    def consume_grant(self, grant: str) -> str | None:
        """Single-use: second consume returns None (GETDEL semantics)."""
        if not grant or len(grant) < 16 or len(grant) > 128:
            return None
        return self._get_backend().getdel(f"{_PREFIX}:grant:{grant}")

    # -- login resolver (fail-closed, owner correction #1) ---------------
    def resolve_patient_user_by_phone(self, db: Session, phone: str) -> User | None:
        """Return the User ONLY when EXACTLY ONE active verified Patient-role
        user matches the normalized phone. 0 or >1 candidates -> None."""
        normalized = normalize_phone(phone)
        if not normalized:
            return None
        stmt = (
            select(User)
            .join(UserProfile, UserProfile.user_id == User.id)
            .where(
                UserProfile.phone == normalized,
                UserProfile.phone_verified.is_(True),
                User.role == "Patient",
                User.is_active.is_(True),
            )
        )
        candidates = db.execute(stmt).scalars().all()
        if len(candidates) != 1:
            logger.info(
                "patient login resolver: %d candidate(s) for phone_fingerprint=%s",
                len(candidates),
                hashlib.sha256(normalized.encode()).hexdigest()[:12],
            )
            return None
        return candidates[0]

    def login_with_grant(self, db: Session, phone: str, grant: str) -> dict[str, Any]:
        """phone + verification_grant -> canonical patient session payload.

        Identity comes from the ALREADY-LINKED Patient.user_id (PR-A2);
        this resolver never searches patients by phone."""
        normalized = normalize_phone(phone)
        granted_phone = self.consume_grant(grant)
        if not normalized or granted_phone is None or granted_phone != normalized:
            raise PatientOtpError(401, ERR_LOGIN_GENERIC)

        user = self.resolve_patient_user_by_phone(db, normalized)
        if user is None:
            raise PatientOtpError(401, ERR_LOGIN_GENERIC)

        from app.api.deps import create_access_token

        access_token = create_access_token(data={"sub": str(user.id)})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            },
        }


# Module-level singleton (mirrors phone_verification_service convention)
patient_otp_service = PatientOtpService()


def get_patient_otp_service() -> PatientOtpService:
    return patient_otp_service
