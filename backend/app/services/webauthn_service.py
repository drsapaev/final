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
                    url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
                )
                _redis_ceremony_clients[url] = client
        client.ping()
        return client
    except Exception as exc:
        raise WebAuthnStoreUnavailable("WebAuthn ceremony store unavailable") from exc


def _store_ceremony(store, ceremony_id: str, patient_id: int, challenge: bytes) -> None:
    value = json.dumps({"patient_id": patient_id, "challenge": _b64url(challenge)})
    key = f"webauthn:login:{ceremony_id}"
    if store is None:
        with _test_ceremonies_lock:
            now = time.monotonic()
            expired = [key for key, (_, expiry) in _test_ceremonies.items() if expiry <= now]
            for expired_key in expired:
                del _test_ceremonies[expired_key]
            _test_ceremonies[key] = (value, now + _CEREMONY_TTL)
    else:
        try:
            if not store.set(key, value, ex=_CEREMONY_TTL, nx=True):
                raise WebAuthnStoreUnavailable("WebAuthn ceremony collision")
        except WebAuthnStoreUnavailable:
            raise
        except Exception as exc:
            raise WebAuthnStoreUnavailable("WebAuthn ceremony store unavailable") from exc


def _consume_ceremony(ceremony_id: str, patient_id: int) -> bytes:
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
            value = store.execute_command("GETDEL", key)
        except Exception as exc:
            raise WebAuthnStoreUnavailable("WebAuthn ceremony store unavailable") from exc
    if not value:
        raise ValueError("Authentication challenge expired or already used")
    try:
        record = json.loads(value)
        if record["patient_id"] != patient_id:
            raise ValueError("Authentication ceremony does not match")
        return _decode_b64url(record["challenge"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid authentication ceremony") from exc


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_b64url(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("Invalid base64url value")
    try:
        raw = value.encode("ascii")
        return base64.b64decode(raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True)
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

    # Generate registration options
    options = generate_registration_options(
        rp_id=server_rp_id,
        rp_name=rp_name,
        user_id=str(patient_id).encode(),
        user_name=f"patient_{patient_id}",
    )

    # Store challenge in cache for verification (TTL=5min)
    from app.core.cache import cache_manager

    challenge_b64 = options.challenge.decode() if isinstance(options.challenge, bytes) else options.challenge
    cache_manager.set(
        f"webauthn_reg_challenge:{patient_id}",
        challenge_b64,
        ttl=300,
    )

    # Return JSON-serializable options
    return {
        "challenge": challenge_b64,
        "rp": {"id": server_rp_id, "name": rp_name},
        "user": {
            "id": str(patient_id),
            "name": f"patient_{patient_id}",
            "displayName": f"Patient {patient_id}",
        },
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}],  # ES256
        "timeout": 60000,
        "attestation": "none",
    }


def finish_passkey_registration(
    db: Session,
    patient_id: int,
    *,
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

    from app.core.cache import cache_manager

    # Retrieve stored challenge
    challenge = cache_manager.get(f"webauthn_reg_challenge:{patient_id}")
    if not challenge:
        raise ValueError("Registration challenge expired or not found")

    # Verify registration response against the SERVER's RP ID/origin
    verified = verify_registration_response(
        credential=credential_response,
        expected_challenge=challenge.encode() if isinstance(challenge, str) else challenge,
        expected_origin=server_origin,
        expected_rp_id=server_rp_id,
    )

    # Store credential
    import base64
    credential_id_b64 = base64.urlsafe_b64encode(verified.credential_id).decode()
    public_key_b64 = base64.urlsafe_b64encode(verified.credential_public_key).decode()

    credential = PasskeyCredential(
        patient_id=patient_id,
        credential_id=credential_id_b64,
        public_key=public_key_b64,
        sign_count=verified.sign_count,
        transports=",".join(verified.credential_device_type) if hasattr(verified, "credential_device_type") else None,
        device_type=getattr(verified, "credential_device_type", None),
        name=credential_name,
        active=True,
    )
    db.add(credential)
    db.commit()

    # Clean up challenge
    cache_manager.delete(f"webauthn_reg_challenge:{patient_id}")

    logger.info("Passkey registered")
    return credential


def begin_passkey_authentication(
    db: Session,
    patient_id: int,
    *,
    rp_id: str | None = None,
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

    # WEBAUTHN-BE-002 (#4063): the begin endpoint is unauthenticated and
    # takes an arbitrary patient_id — cache a challenge ONLY when that
    # patient actually has an active credential. Unknown/gated patients get
    # a byte-identical dummy response, but nothing is stored: the shared
    # cache can no longer be grown by anonymous probing, and a dummy
    # challenge can never complete a ceremony (its verify finds no cache
    # entry and rejects).
    has_active_credential = (
        db.query(PasskeyCredential.id)
        .filter(
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.active == True,
        )
        .first()
        is not None
    )
    if has_active_credential:
        _store_ceremony(store, ceremony_id, patient_id, options.challenge)

    return {
        "challenge": challenge_b64,
        "ceremony_id": ceremony_id,
        "rpId": server_rp_id,
        "timeout": 60000,
        "userVerification": "required",
    }


def finish_passkey_authentication(
    db: Session,
    patient_id: int,
    *,
    assertion_response: dict[str, Any],
    ceremony_id: str,
    rp_id: str | None = None,
    origin: str | None = None,
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

    challenge = _consume_ceremony(ceremony_id, patient_id)

    if not isinstance(assertion_response, dict):
        raise ValueError("Invalid assertion")
    credential_id = _decode_b64url(assertion_response.get("id"))
    raw_id = assertion_response.get("rawId")
    if raw_id is not None and _decode_b64url(raw_id) != credential_id:
        raise ValueError("Credential IDs do not match")
    credential_id_b64 = base64.urlsafe_b64encode(credential_id).decode("ascii")

    # Find the credential
    credential = (
        db.query(PasskeyCredential)
        .filter(
            PasskeyCredential.patient_id == patient_id,
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
    from app.models.patient import Patient
    from app.models.user import User

    user = (
        db.query(User)
        .join(Patient, Patient.user_id == User.id)
        .filter(
            Patient.id == patient_id,
            Patient.is_deleted.is_(False),
            User.role == "Patient",
            User.is_active.is_(True),
            User.is_superuser.is_(False),
        )
        .first()
    )
    if user is None:
        raise ValueError("Patient portal identity unavailable")
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


def list_patient_passkeys(db: Session, patient_id: int) -> list[PasskeyCredential]:
    """List all active passkeys for a patient."""
    return (
        db.query(PasskeyCredential)
        .filter(
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.active == True,
        )
        .order_by(PasskeyCredential.created_at.desc())
        .all()
    )


def deactivate_passkey(db: Session, patient_id: int, credential_id: int) -> bool:
    """Deactivate a passkey (soft delete)."""
    credential = (
        db.query(PasskeyCredential)
        .filter(
            PasskeyCredential.id == credential_id,
            PasskeyCredential.patient_id == patient_id,
        )
        .first()
    )
    if not credential:
        return False
    credential.active = False
    db.commit()
    return True
