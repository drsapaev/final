"""
WebAuthn/Passkey Service — M4-P1-4 (Epic M4 — Backend Security & Compliance).

Provides passkey registration + verification for patients.

Uses the `webauthn` Python library when available. If the library is not
installed (cloud dev environment), endpoints return 503 Service Unavailable.
The DB schema (passkey_credentials table) is ready — activation requires
`pip install webauthn` in production.

Flow:
  Registration:
    1. POST /auth/webauthn/register/begin → challenge
    2. POST /auth/webauthn/register/finish → verify + store credential

  Authentication:
    1. POST /auth/webauthn/login/begin → challenge
    2. POST /auth/webauthn/login/finish → verify + issue JWT
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.passkey_credential import PasskeyCredential

logger = logging.getLogger(__name__)

# Check if webauthn library is available
try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
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
    from urllib.parse import urlparse

    from app.core.config import settings

    raw = (settings.FRONTEND_URL or "").strip()
    if not raw:
        raise RuntimeError(
            "FRONTEND_URL is not configured — cannot pin WebAuthn RP ID/origin"
        )
    parsed = urlparse(raw)
    rp_id = parsed.hostname or raw
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc or raw}"
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

    from app.core.cache import cache_manager
    challenge_b64 = options.challenge.decode() if isinstance(options.challenge, bytes) else options.challenge
    cache_manager.set(
        f"webauthn_auth_challenge:{patient_id}",
        challenge_b64,
        ttl=300,
    )

    return {
        "challenge": challenge_b64,
        "rpId": server_rp_id,
        "timeout": 60000,
        "userVerification": "preferred",
    }


def finish_passkey_authentication(
    db: Session,
    patient_id: int,
    *,
    assertion_response: dict[str, Any],
    rp_id: str | None = None,
    origin: str | None = None,
) -> dict[str, Any]:
    """Finish passkey authentication — verify assertion + issue JWT.

    M4-P1-4: Step 2 of 2-step authentication flow.
    Returns JWT tokens (same format as Telegram Mini App exchange).

    ``rp_id``/``origin`` are accepted for call-site compatibility but
    IGNORED — the expected verification values are server-pinned
    (WEBAUTHN-BE-001, #4063).
    """
    if not WEBAUTHN_AVAILABLE:
        raise RuntimeError("webauthn library not installed")

    server_rp_id, server_origin = _server_rp_origin()

    from app.core.cache import cache_manager

    challenge = cache_manager.get(f"webauthn_auth_challenge:{patient_id}")
    if not challenge:
        raise ValueError("Authentication challenge expired or not found")

    # Find the credential
    credential = (
        db.query(PasskeyCredential)
        .filter(
            PasskeyCredential.patient_id == patient_id,
            PasskeyCredential.active == True,
        )
        .first()
    )
    if not credential:
        raise ValueError("No active passkey found for patient")

    import base64
    credential_id_bytes = base64.urlsafe_b64decode(credential.credential_id)
    public_key_bytes = base64.urlsafe_b64decode(credential.public_key)

    # Verify authentication response
    verified = verify_authentication_response(
        credential=assertion_response,
        expected_challenge=challenge.encode() if isinstance(challenge, str) else challenge,
        expected_origin=server_origin,
        expected_rp_id=server_rp_id,
        credential_public_key=public_key_bytes,
        credential_current_sign_count=credential.sign_count,
    )

    # Update sign count
    credential.sign_count = verified.new_sign_count
    from datetime import UTC, datetime
    credential.last_used_at = datetime.now(UTC)
    db.commit()

    # Clean up challenge
    cache_manager.delete(f"webauthn_auth_challenge:{patient_id}")

    # Issue JWT (same as Telegram exchange)
    from app.services.telegram_mini_app_jwt import (
        PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES,
        PATIENT_JWT_ALGORITHM,
        PATIENT_REFRESH_TOKEN_EXPIRE_DAYS,
        _revoke_previous_patient_sessions,
    )
    from app.core.config import settings
    from app.models.authentication import UserSession
    import jwt as jwt_lib
    import uuid
    from datetime import timedelta

    _revoke_previous_patient_sessions(db, patient_id)

    now = datetime.now(UTC)
    access_jti = str(uuid.uuid4())
    access_token = jwt_lib.encode(
        {
            "sub": str(patient_id),
            "scope": "patient",
            "type": "access",
            "jti": access_jti,
            "iat": now,
            "exp": now + timedelta(minutes=PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "auth_method": "passkey",
        },
        settings.SECRET_KEY,
        algorithm=PATIENT_JWT_ALGORITHM,
    )

    refresh_jti = str(uuid.uuid4())
    refresh_token = jwt_lib.encode(
        {
            "sub": str(patient_id),
            "scope": "patient",
            "type": "refresh",
            "jti": refresh_jti,
            "iat": now,
            "exp": now + timedelta(days=PATIENT_REFRESH_TOKEN_EXPIRE_DAYS),
            "auth_method": "passkey",
        },
        settings.SECRET_KEY,
        algorithm=PATIENT_JWT_ALGORITHM,
    )

    session = UserSession(
        user_id=-int(patient_id),
        refresh_token=refresh_token,
        expires_at=now + timedelta(days=PATIENT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    db.commit()

    logger.info("Passkey authentication successful")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "patient_id": patient_id,
        "auth_method": "passkey",
    }


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
    from datetime import UTC, datetime
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
