"""
WebAuthn/Passkey Service — M4-P1-4 (Epic M4 — Backend Security & Compliance).

Provides passkey registration + verification for patients.

Uses the pinned `webauthn` Python library. If the installation is broken or
missing, endpoints return 503 Service Unavailable instead of bypassing checks.

Flow:
  Registration:
    1. POST /auth/webauthn/register/begin → challenge
    2. POST /auth/webauthn/register/finish → verify + store credential

  Authentication:
    1. POST /auth/webauthn/login/begin → challenge
    2. POST /auth/webauthn/login/finish → verify + issue JWT
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models.passkey_credential import PasskeyCredential

logger = logging.getLogger(__name__)

_CEREMONY_TTL = 300
_CEREMONY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_test_ceremonies: dict[str, tuple[str, float]] = {}
_test_ceremonies_lock = threading.Lock()
_redis_ceremony_clients: dict[str, Any] = {}
_redis_ceremony_clients_lock = threading.Lock()


class WebAuthnStoreUnavailable(RuntimeError):
    """The shared one-time ceremony store is unavailable."""


class WebAuthnQuotaExceeded(RuntimeError):
    """A shared WebAuthn abuse limit was reached."""


_DISCOVERABLE_PREFIX = "webauthn:{discoverable}:"
_DISCOVERABLE_GLOBAL_LIMIT = 1000
_DISCOVERABLE_CLIENT_LIMIT = 10
_DISCOVERABLE_GLOBAL_RATE = 2000
_DISCOVERABLE_CLIENT_RATE = 30

# Redis server time and all counters are shared across workers. All keys use
# the same cluster hash tag. Quotas count live outstanding ceremonies, while
# fixed-window limits also bound begin/finish churn and the number of IP keys.
_DISCOVERABLE_BEGIN_LUA = r"""
local now = tonumber(redis.call('TIME')[1])
local global_rate = redis.call('INCR', KEYS[4])
if global_rate == 1 then redis.call('EXPIRE', KEYS[4], 60) end
if global_rate > tonumber(ARGV[5]) then return 0 end
local client_rate = redis.call('INCR', KEYS[5])
if client_rate == 1 then redis.call('EXPIRE', KEYS[5], 60) end
if client_rate > tonumber(ARGV[6]) then return 0 end
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now)
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[3]) or
   redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[4]) then return 0 end
if not redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[7], 'NX') then return -1 end
local expiry = now + tonumber(ARGV[7])
redis.call('ZADD', KEYS[2], expiry, ARGV[1])
redis.call('ZADD', KEYS[3], expiry, ARGV[1])
redis.call('EXPIRE', KEYS[2], ARGV[7])
redis.call('EXPIRE', KEYS[3], ARGV[7])
return 1
"""

_DISCOVERABLE_FINISH_LUA = r"""
local global_rate = redis.call('INCR', KEYS[2])
if global_rate == 1 then redis.call('EXPIRE', KEYS[2], 60) end
if global_rate > tonumber(ARGV[2]) then return {0} end
local client_rate = redis.call('INCR', KEYS[3])
if client_rate == 1 then redis.call('EXPIRE', KEYS[3], 60) end
if client_rate > tonumber(ARGV[3]) then return {0} end
local value = redis.call('GETDEL', KEYS[1])
if not value then return {1} end
local record = cjson.decode(value)
redis.call('ZREM', KEYS[4], ARGV[1])
if record.client and record.client == ARGV[4] then redis.call('ZREM', KEYS[5], ARGV[1]) end
return {1, value}
"""


def _discoverable_store():
    store = _ceremony_store()
    if store is None:
        raise WebAuthnStoreUnavailable("WebAuthn shared store required")
    return store


def _discoverable_client_key(client_ip: str) -> str:
    from app.core.config import settings

    if not isinstance(client_ip, str) or not client_ip or len(client_ip) > 128:
        raise ValueError("Invalid client address")
    return hmac.new(
        settings.SECRET_KEY.encode(), client_ip.encode(), hashlib.sha256
    ).hexdigest()


def _store_discoverable_ceremony(ceremony_id, client_ip, challenge):
    _store_bounded_ceremony(
        _discoverable_store(),
        "discoverable",
        ceremony_id,
        client_ip,
        {"purpose": "discoverable_login", "challenge": _b64url(challenge)},
    )


def _store_bounded_ceremony(store, purpose, ceremony_id, client_ip, record):
    client = _discoverable_client_key(client_ip)
    prefix = _DISCOVERABLE_PREFIX
    limits = prefix + purpose + ":"
    member = purpose + ":" + ceremony_id
    value = json.dumps({**record, "client": client})
    try:
        result = store.eval(
            _DISCOVERABLE_BEGIN_LUA,
            5,
            prefix + purpose + ":" + ceremony_id,
            limits + "outstanding",
            limits + "client:" + client,
            limits + "begin_rate",
            limits + "begin_rate:" + client,
            member,
            value,
            _DISCOVERABLE_GLOBAL_LIMIT,
            _DISCOVERABLE_CLIENT_LIMIT,
            _DISCOVERABLE_GLOBAL_RATE,
            _DISCOVERABLE_CLIENT_RATE,
            _CEREMONY_TTL,
        )
    except WebAuthnStoreUnavailable:
        raise
    except Exception as exc:
        raise WebAuthnStoreUnavailable("WebAuthn ceremony store unavailable") from exc
    if result == 0:
        raise WebAuthnQuotaExceeded("WebAuthn rate limit exceeded")
    if result != 1:
        raise WebAuthnStoreUnavailable("WebAuthn ceremony collision")


def _consume_discoverable_ceremony(ceremony_id, client_ip):
    value = _consume_bounded_ceremony(
        _discoverable_store(), "discoverable", ceremony_id, client_ip
    )
    try:
        record = json.loads(value)
        if record["purpose"] != "discoverable_login":
            raise ValueError("Invalid authentication ceremony")
        return _decode_b64url(record["challenge"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid authentication ceremony") from exc


def _consume_bounded_ceremony(store, purpose, ceremony_id, client_ip):
    valid_id = isinstance(ceremony_id, str) and bool(
        _CEREMONY_ID_RE.fullmatch(ceremony_id)
    )
    if not valid_id:
        ceremony_id = "invalid"
    client = _discoverable_client_key(client_ip)
    prefix = _DISCOVERABLE_PREFIX
    limits = prefix + purpose + ":"
    try:
        # Read the bounded record only to choose an explicit Redis Cluster
        # key. The script atomically consumes and rechecks the client value;
        # a concurrent consumer can only make the record disappear.
        key = prefix + purpose + ":" + ceremony_id
        raw = store.get(key)
        stored_client = "missing"
        if raw:
            record = json.loads(raw)
            value = record.get("client")
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                stored_client = value
        result = store.eval(
            _DISCOVERABLE_FINISH_LUA,
            5,
            key,
            limits + "finish_rate",
            limits + "finish_rate:" + client,
            limits + "outstanding",
            limits + "client:" + stored_client,
            purpose + ":" + ceremony_id,
            _DISCOVERABLE_GLOBAL_RATE,
            _DISCOVERABLE_CLIENT_RATE,
            stored_client,
        )
    except WebAuthnStoreUnavailable:
        raise
    except Exception as exc:
        raise WebAuthnStoreUnavailable("WebAuthn ceremony store unavailable") from exc
    if not result or result[0] == 0:
        raise WebAuthnQuotaExceeded("WebAuthn rate limit exceeded")
    if not valid_id or len(result) != 2:
        raise ValueError("Authentication challenge expired or already used")
    return result[1]


def _ceremony_store():
    """Use Redis outside tests; never silently fall back to local state."""
    from app.core.config import settings

    if settings.TESTING:
        return None
    try:
        import redis

        url = os.getenv("REDIS_URL", "").strip() or settings.ARQ_REDIS_URL
        with _redis_ceremony_clients_lock:
            client = _redis_ceremony_clients.get(url)
            if client is None:
                client = redis.Redis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                _redis_ceremony_clients[url] = client
        client.ping()
        return client
    except Exception as exc:
        raise WebAuthnStoreUnavailable("WebAuthn ceremony store unavailable") from exc


def _store_ceremony(
    store,
    ceremony_id: str,
    patient_id: int,
    challenge: bytes,
    client_ip: str = "unknown",
) -> None:
    value = json.dumps({"patient_id": patient_id, "challenge": _b64url(challenge)})
    key = f"webauthn:login:{ceremony_id}"
    if store is None:
        with _test_ceremonies_lock:
            now = time.monotonic()
            expired = [
                key for key, (_, expiry) in _test_ceremonies.items() if expiry <= now
            ]
            for expired_key in expired:
                del _test_ceremonies[expired_key]
            _test_ceremonies[key] = (value, now + _CEREMONY_TTL)
    else:
        _store_bounded_ceremony(
            store,
            "login",
            ceremony_id,
            client_ip,
            {"patient_id": patient_id, "challenge": _b64url(challenge)},
        )


def _consume_ceremony(
    ceremony_id: str, patient_id: int, client_ip: str = "unknown"
) -> bytes:
    if not isinstance(ceremony_id, str) or not _CEREMONY_ID_RE.fullmatch(ceremony_id):
        raise ValueError("Invalid authentication ceremony")
    store = _ceremony_store()
    key = f"webauthn:login:{ceremony_id}"
    if store is None:
        with _test_ceremonies_lock:
            record = _test_ceremonies.pop(key, None)
            value = record[0] if record and record[1] > time.monotonic() else None
    else:
        try:
            try:
                value = _consume_bounded_ceremony(
                    store, "login", ceremony_id, client_ip
                )
            except ValueError:
                # During rollout, preserve one-use challenges issued before
                # the hash-tagged quota namespace existed (at most 5 minutes).
                value = store.execute_command("GETDEL", key)
        except WebAuthnQuotaExceeded:
            raise
        except Exception as exc:
            raise WebAuthnStoreUnavailable(
                "WebAuthn ceremony store unavailable"
            ) from exc
    if not value:
        raise ValueError("Authentication challenge expired or already used")
    try:
        record = json.loads(value)
        if record["patient_id"] != patient_id:
            raise ValueError("Authentication ceremony does not match")
        return _decode_b64url(record["challenge"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid authentication ceremony") from exc


def _store_registration_ceremony(
    store, ceremony_id, patient_id, user_id, session_jti, challenge
):
    key = f"webauthn:registration:{ceremony_id}"
    value = json.dumps(
        {
            "purpose": "register",
            "patient_id": patient_id,
            "user_id": user_id,
            "session_jti": session_jti,
            "challenge": _b64url(challenge),
        }
    )
    if store is None:
        with _test_ceremonies_lock:
            now = time.monotonic()
            for expired in [
                k for k, (_, expiry) in _test_ceremonies.items() if expiry <= now
            ]:
                del _test_ceremonies[expired]
            if key in _test_ceremonies:
                raise WebAuthnStoreUnavailable("WebAuthn ceremony collision")
            _test_ceremonies[key] = (value, now + _CEREMONY_TTL)
    else:
        try:
            if not store.set(key, value, ex=_CEREMONY_TTL, nx=True):
                raise WebAuthnStoreUnavailable("WebAuthn ceremony collision")
        except WebAuthnStoreUnavailable:
            raise
        except Exception as exc:
            raise WebAuthnStoreUnavailable(
                "WebAuthn ceremony store unavailable"
            ) from exc


def _consume_registration_ceremony(ceremony_id, patient_id, user_id, session_jti):
    if not isinstance(ceremony_id, str) or not _CEREMONY_ID_RE.fullmatch(ceremony_id):
        raise ValueError("Invalid registration ceremony")
    store = _ceremony_store()
    key = f"webauthn:registration:{ceremony_id}"
    if store is None:
        with _test_ceremonies_lock:
            record = _test_ceremonies.pop(key, None)
            value = record[0] if record and record[1] > time.monotonic() else None
    else:
        try:
            value = store.execute_command("GETDEL", key)
        except Exception as exc:
            raise WebAuthnStoreUnavailable(
                "WebAuthn ceremony store unavailable"
            ) from exc
    if not value:
        raise ValueError("Registration challenge expired or already used")
    try:
        record = json.loads(value)
        if (
            record["purpose"] != "register"
            or record["patient_id"] != patient_id
            or record["user_id"] != user_id
            or record["session_jti"] != session_jti
        ):
            raise ValueError("Registration ceremony does not match")
        return _decode_b64url(record["challenge"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid registration ceremony") from exc


def _lock_current_patient_identity(db: Session, patient_id: int):
    """Lock the patient and linked user in a consistent order for all mutations."""
    from app.models.patient import Patient
    from app.models.user import User

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if patient is None or patient.is_deleted is not False or patient.user_id is None:
        return None
    user = (
        db.query(User)
        .filter(User.id == patient.user_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not user or user.role != "Patient" or not user.is_active or user.is_superuser:
        return None
    return user


def _lock_patient_identity(db: Session, patient_id: int, user_id: int) -> bool:
    user = _lock_current_patient_identity(db, patient_id)
    return user is not None and user.id == user_id


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_b64url(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("Invalid base64url value")
    try:
        raw = value.encode("ascii")
        return base64.b64decode(
            raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True
        )
    except (UnicodeError, binascii.Error) as exc:
        raise ValueError("Invalid base64url value") from exc


# Check if webauthn library is available
try:
    from webauthn import (
        generate_authentication_options,
        generate_registration_options,
        verify_authentication_response,
        verify_registration_response,
    )
    from webauthn.helpers import options_to_json_dict
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False
    logger.warning("webauthn library not installed — passkey endpoints return 503")


def is_webauthn_available() -> bool:
    """Check if WebAuthn library is available."""
    return WEBAUTHN_AVAILABLE


def _server_rp_origin() -> tuple[str, str]:
    """WEBAUTHN-BE-001 (#4063): server-side trust anchors for WebAuthn.

    The RP ID and expected origin MUST come from server configuration
    (``settings.FRONTEND_URL``), never from the request body: passing
    client-supplied values as the *expected* verification inputs verifies
    attacker input against attacker input and neutralizes WebAuthn's
    origin-binding (anti-phishing) guarantee. RP ID is the bare hostname
    (WebAuthn forbids scheme/port in rpId); the origin keeps scheme and
    port.
    """
    from urllib.parse import urlsplit

    from app.core.config import settings

    raw = (settings.FRONTEND_URL or "").strip()
    if not raw:
        raise RuntimeError(
            "FRONTEND_URL is not configured — cannot pin WebAuthn RP ID/origin"
        )
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        port = parsed.port
        if (
            any(ord(char) < 32 or ord(char) == 127 for char in raw)
            or "\\" in raw
            or parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("invalid origin")
        rp_id = host.encode("idna").decode("ascii").lower()
        if parsed.scheme == "http" and rp_id != "localhost":
            raise ValueError("WebAuthn requires HTTPS outside localhost")
        # Origin serialization omits the default port, as browsers do.
        default_port = 443 if parsed.scheme == "https" else 80
        authority = f"[{rp_id}]" if ":" in rp_id else rp_id
        if port is not None and port != default_port:
            authority += f":{port}"
        origin = f"{parsed.scheme}://{authority}"
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("FRONTEND_URL is not a valid WebAuthn origin") from exc
    return rp_id, origin


def begin_passkey_registration(
    db: Session,
    patient_id: int,
    user_id: int,
    session_jti: str,
    *,
    rp_id: str | None = None,
    rp_name: str,
    credential_name: str | None = None,
) -> dict[str, Any]:
    """Begin passkey registration — returns challenge for browser.

    M4-P1-4: Step 1 of 2-step registration flow.
    Browser calls navigator.credentials.create() with this challenge.

    ``rp_id`` is accepted for call-site compatibility but IGNORED — the RP
    is server-pinned (WEBAUTHN-BE-001, #4063).
    """
    if not WEBAUTHN_AVAILABLE:
        raise RuntimeError("webauthn library not installed")

    server_rp_id, _ = _server_rp_origin()

    if not isinstance(session_jti, str) or not session_jti:
        raise ValueError("Invalid patient session")

    try:
        user = _lock_current_patient_identity(db, patient_id)
        if user is None or user.id != user_id:
            raise ValueError("Patient portal identity unavailable")
        if not user.passkey_user_handle:
            user.passkey_user_handle = secrets.token_urlsafe(32)
        handle = _decode_b64url(user.passkey_user_handle)
        existing = (
            db.query(PasskeyCredential.credential_id)
            .filter(
                PasskeyCredential.patient_id == patient_id,
                PasskeyCredential.owner_user_id == user_id,
                PasskeyCredential.active.is_(True),
            )
            .all()
        )
        options = generate_registration_options(
            rp_id=server_rp_id,
            rp_name=rp_name,
            user_id=handle,
            user_name="patient",
            user_display_name="Patient",
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=_decode_b64url(row[0]))
                for row in existing
            ],
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        if not isinstance(options.challenge, bytes) or not options.challenge:
            raise ValueError("Invalid WebAuthn challenge")
        result = options_to_json_dict(options)
        ceremony_id = secrets.token_urlsafe(32)
        _store_registration_ceremony(
            _ceremony_store(),
            ceremony_id,
            patient_id,
            user_id,
            session_jti,
            options.challenge,
        )
        db.commit()
        result["ceremony_id"] = ceremony_id
        return result
    except Exception:
        db.rollback()
        raise


def finish_passkey_registration(
    db: Session,
    patient_id: int,
    user_id: int,
    session_jti: str,
    *,
    ceremony_id: str,
    credential_response: dict[str, Any],
    rp_id: str | None = None,
    origin: str | None = None,
    credential_name: str | None = None,
) -> PasskeyCredential:
    """Finish passkey registration — verify browser response + store credential.

    M4-P1-4: Step 2 of 2-step registration flow.

    ``rp_id``/``origin`` are accepted for call-site compatibility but
    IGNORED — the expected verification values are server-pinned
    (WEBAUTHN-BE-001, #4063): client-supplied origin/RP would verify
    attacker input against attacker input.
    """
    if not WEBAUTHN_AVAILABLE:
        raise RuntimeError("webauthn library not installed")

    server_rp_id, server_origin = _server_rp_origin()

    if not isinstance(session_jti, str) or not session_jti:
        raise ValueError("Invalid patient session")
    try:
        challenge = _consume_registration_ceremony(
            ceremony_id, patient_id, user_id, session_jti
        )
        verified = verify_registration_response(
            credential=credential_response,
            expected_challenge=challenge,
            expected_origin=server_origin,
            expected_rp_id=server_rp_id,
            require_user_verification=True,
        )
        if not _lock_patient_identity(db, patient_id, user_id):
            raise ValueError("Patient portal identity unavailable")
        device_type = getattr(verified, "credential_device_type", None)
        device_type = getattr(device_type, "value", device_type)
        credential = PasskeyCredential(
            patient_id=patient_id,
            owner_user_id=user_id,
            credential_id=base64.urlsafe_b64encode(verified.credential_id).decode(
                "ascii"
            ),
            public_key=base64.urlsafe_b64encode(verified.credential_public_key).decode(
                "ascii"
            ),
            sign_count=verified.sign_count,
            device_type=device_type,
            name=credential_name,
            active=True,
        )
        db.add(credential)
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info("Passkey registered")
    return credential


def begin_passkey_authentication(
    db: Session,
    patient_id: int,
    *,
    rp_id: str | None = None,
    client_ip: str = "unknown",
) -> dict[str, Any]:
    """Begin passkey authentication — returns challenge for browser.

    M4-P1-4: Step 1 of 2-step authentication flow.
    Browser calls navigator.credentials.get() with this challenge.

    ``rp_id`` is accepted for call-site compatibility but IGNORED — the RP
    is server-pinned (WEBAUTHN-BE-001, #4063).
    """
    if not WEBAUTHN_AVAILABLE:
        raise RuntimeError("webauthn library not installed")

    server_rp_id, _ = _server_rp_origin()

    options = generate_authentication_options(
        rp_id=server_rp_id,
    )

    store = _ceremony_store()
    if not isinstance(options.challenge, bytes) or not options.challenge:
        raise ValueError("Invalid WebAuthn challenge")
    challenge_b64 = _b64url(options.challenge)
    ceremony_id = secrets.token_urlsafe(32)

    # Issue the same bounded Redis operation for every patient ID. This keeps
    # quota exhaustion and Redis failures independent of identity existence.
    # Unknown patients cannot complete the owner-checked authentication.
    try:
        _store_ceremony(store, ceremony_id, patient_id, options.challenge, client_ip)
    except WebAuthnQuotaExceeded:
        # A saturated legacy plane returns an unusable dummy for every caller.
        pass

    return {
        "challenge": challenge_b64,
        "ceremony_id": ceremony_id,
        "rpId": server_rp_id,
        "timeout": 60000,
        "userVerification": "required",
    }


def begin_discoverable_authentication(client_ip: str) -> dict[str, Any]:
    """Start a quota-bounded anonymous discoverable credential ceremony."""
    if not WEBAUTHN_AVAILABLE:
        raise RuntimeError("webauthn library not installed")
    rp_id, _ = _server_rp_origin()
    options = generate_authentication_options(rp_id=rp_id)
    if not isinstance(options.challenge, bytes) or not options.challenge:
        raise ValueError("Invalid WebAuthn challenge")
    ceremony_id = secrets.token_urlsafe(32)
    _store_discoverable_ceremony(ceremony_id, client_ip, options.challenge)
    return {
        "challenge": _b64url(options.challenge),
        "ceremony_id": ceremony_id,
        "rpId": rp_id,
        "timeout": 60000,
        "userVerification": "required",
    }


def finish_discoverable_authentication(
    db: Session, *, client_ip: str, ceremony_id: str, assertion_response: dict[str, Any]
) -> dict[str, Any]:
    """Authenticate a discoverable credential after atomic challenge consumption."""
    try:
        if not WEBAUTHN_AVAILABLE:
            raise RuntimeError("webauthn library not installed")
        challenge = _consume_discoverable_ceremony(ceremony_id, client_ip)
        if not isinstance(assertion_response, dict):
            raise ValueError("Invalid assertion")
        credential_id = _decode_b64url(assertion_response.get("id"))
        encoded = base64.urlsafe_b64encode(credential_id).decode("ascii")
        candidate = (
            db.query(PasskeyCredential.patient_id)
            .filter(
                PasskeyCredential.credential_id == encoded,
                PasskeyCredential.active.is_(True),
                PasskeyCredential.owner_user_id.is_not(None),
            )
            .first()
        )
        if candidate is None:
            raise ValueError("Invalid assertion")
        patient_id = candidate[0]
        rp_id, origin = _server_rp_origin()
        return _complete_patient_authentication(
            db,
            patient_id,
            assertion_response,
            challenge,
            rp_id,
            origin,
            check_user_handle=True,
        )
    except Exception:
        db.rollback()
        raise


def finish_passkey_authentication(
    db: Session,
    patient_id: int,
    *,
    assertion_response: dict[str, Any],
    ceremony_id: str,
    rp_id: str | None = None,
    origin: str | None = None,
    client_ip: str = "unknown",
) -> dict[str, Any]:
    """Complete one ceremony; roll back all pending changes on failure."""
    try:
        return _finish_passkey_authentication(
            db,
            patient_id,
            assertion_response=assertion_response,
            ceremony_id=ceremony_id,
            rp_id=rp_id,
            origin=origin,
            client_ip=client_ip,
        )
    except Exception:
        db.rollback()
        raise


def _finish_passkey_authentication(
    db: Session,
    patient_id: int,
    *,
    assertion_response: dict[str, Any],
    ceremony_id: str,
    rp_id: str | None = None,
    origin: str | None = None,
    client_ip: str = "unknown",
) -> dict[str, Any]:
    """Finish passkey authentication and issue an access-only patient session.

    M4-P1-4: Step 2 of 2-step authentication flow.
    Returns the canonical linked Patient User profile and access token.

    ``rp_id``/``origin`` are accepted for call-site compatibility but
    IGNORED — the expected verification values are server-pinned
    (WEBAUTHN-BE-001, #4063).
    """
    if not WEBAUTHN_AVAILABLE:
        raise RuntimeError("webauthn library not installed")

    server_rp_id, server_origin = _server_rp_origin()

    challenge = _consume_ceremony(ceremony_id, patient_id, client_ip)

    return _complete_patient_authentication(
        db, patient_id, assertion_response, challenge, server_rp_id, server_origin
    )


def _complete_patient_authentication(
    db,
    patient_id,
    assertion_response,
    challenge,
    server_rp_id,
    server_origin,
    *,
    check_user_handle=False,
):
    if not isinstance(assertion_response, dict):
        raise ValueError("Invalid assertion")
    credential_id = _decode_b64url(assertion_response.get("id"))
    raw_id = assertion_response.get("rawId")
    if raw_id is not None and _decode_b64url(raw_id) != credential_id:
        raise ValueError("Credential IDs do not match")
    credential_id_b64 = base64.urlsafe_b64encode(credential_id).decode("ascii")

    # Lock the live identity before the credential, matching management's lock
    # order and preventing relinking/deactivation from changing token ownership.
    user = _lock_current_patient_identity(db, patient_id)
    if user is None:
        raise ValueError("Patient portal identity unavailable")
    if check_user_handle:
        response = assertion_response.get("response")
        if isinstance(response, dict) and response.get("userHandle") is not None:
            if not user.passkey_user_handle or _decode_b64url(
                response["userHandle"]
            ) != _decode_b64url(user.passkey_user_handle):
                raise ValueError("Invalid assertion")

    credential = (
        db.query(PasskeyCredential)
        .filter(
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.owner_user_id == user.id,
            PasskeyCredential.active == True,
            PasskeyCredential.credential_id == credential_id_b64,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not credential:
        raise ValueError("No active passkey found for patient")

    public_key_bytes = base64.urlsafe_b64decode(credential.public_key)

    # Verify authentication response
    verified = verify_authentication_response(
        credential=assertion_response,
        expected_challenge=challenge,
        expected_origin=server_origin,
        expected_rp_id=server_rp_id,
        credential_public_key=public_key_bytes,
        credential_current_sign_count=credential.sign_count,
        require_user_verification=True,
    )

    # Update sign count
    credential.sign_count = verified.new_sign_count
    from datetime import UTC, datetime

    credential.last_used_at = datetime.now(UTC)
    # The canonical patient-portal identity is the linked, active Patient
    # user. Patient IDs and User IDs are different namespaces; signing a
    # patient ID as a generic JWT subject can impersonate an unrelated user.
    from app.api.deps import create_access_token

    access_token = create_access_token(
        data={"sub": str(user.id), "scope": "patient_portal", "patient_id": patient_id}
    )
    result = {
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
    db.commit()
    logger.info("Passkey authentication successful")
    return result


def list_patient_passkeys(
    db: Session, patient_id: int, *, user_id: int
) -> list[PasskeyCredential]:
    """List all active passkeys for a patient."""
    from app.models.patient import Patient
    from app.models.user import User

    return (
        db.query(PasskeyCredential)
        .join(Patient, Patient.id == PasskeyCredential.patient_id)
        .join(User, User.id == Patient.user_id)
        .filter(
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.owner_user_id == user_id,
            PasskeyCredential.active == True,
            Patient.is_deleted.is_(False),
            User.id == user_id,
            User.role == "Patient",
            User.is_active.is_(True),
            User.is_superuser.is_(False),
        )
        .order_by(PasskeyCredential.created_at.desc())
        .all()
    )


def deactivate_passkey(
    db: Session, patient_id: int, credential_id: int, *, user_id: int
) -> bool:
    """Deactivate a passkey (soft delete).

    WEBAUTHN-BE-003 (#4063): unknown AND already-inactive credentials both
    return False (one opaque 404 at the endpoint — no state disclosure),
    and deactivating the patient's LAST active passkey raises
    ValueError("last_active_credential") — the endpoint maps it to 409 so a
    phished initData session cannot lock the patient out of passkey login.
    """
    if not _lock_patient_identity(db, patient_id, user_id):
        db.rollback()
        return False
    credential = (
        db.query(PasskeyCredential)
        .filter(
            PasskeyCredential.id == credential_id,
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.owner_user_id == user_id,
        )
        .first()
    )
    if not credential or not credential.active:
        db.rollback()
        return False

    active_count = (
        db.query(PasskeyCredential.id)
        .filter(
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.owner_user_id == user_id,
            PasskeyCredential.active == True,
        )
        .count()
    )
    if active_count <= 1:
        db.rollback()
        raise ValueError("last_active_credential")

    credential.active = False
    db.commit()
    logger.warning("Passkey deactivated")
    return True
