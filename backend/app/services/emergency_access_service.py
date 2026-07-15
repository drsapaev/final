"""
Emergency Access Service — M4-P2-1 (Epic M4).

Issue + consume one-time emergency tokens for patients who lost all
authentication factors (Telegram + passkey). Admin verifies identity
manually (passport, video call) and issues a 15-minute token.

Flow:
  1. Admin: POST /admin/emergency-access { patient_id, verification_method }
     → token returned (one-time, 15 min, specific resource or all)
  2. Patient: opens /emergency?token=...
     → backend verifies token hash, checks expiry + unused
     → marks token as used (one-time)
     → grants access to specified resource
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.emergency_access_token import EmergencyAccessToken

logger = logging.getLogger(__name__)

EMERGENCY_TOKEN_EXPIRE_MINUTES = 15


def issue_emergency_token(
    db: Session,
    *,
    patient_id: int,
    issued_by: int,
    verification_method: str,
    verification_notes: str | None = None,
    resource_type: str = "all",
    resource_id: str | None = None,
) -> dict[str, Any]:
    """Issue a one-time emergency access token (M4-P2-1).

    Admin calls this after manual identity verification.
    Returns the plaintext token (shown once to admin, then forgotten).

    Args:
        patient_id: Patient who needs emergency access
        issued_by: Admin user ID who verified identity
        verification_method: passport | video_call | in_person
        verification_notes: Admin's notes (court order ref, etc.)
        resource_type: all | lab_report | cabinet_summary
        resource_id: Specific resource ID if needed

    Returns:
        Dict with: token (plaintext), token_id, expires_at
    """
    # Generate cryptographically secure token
    plaintext_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()

    expires_at = datetime.now(UTC) + timedelta(minutes=EMERGENCY_TOKEN_EXPIRE_MINUTES)

    token = EmergencyAccessToken(
        patient_id=patient_id,
        token_hash=token_hash,
        resource_type=resource_type,
        resource_id=resource_id,
        expires_at=expires_at,
        used=False,
        issued_by=issued_by,
        verification_method=verification_method,
        verification_notes=verification_notes,
    )
    db.add(token)
    db.commit()

    logger.info("Emergency access token issued")

    return {
        "token": plaintext_token,
        "token_id": token.id,
        "expires_at": expires_at.isoformat(),
        "resource_type": resource_type,
        "resource_id": resource_id,
    }


def consume_emergency_token(
    db: Session,
    *,
    token: str,
) -> dict[str, Any] | None:
    """Consume a one-time emergency access token (M4-P2-1).

    Patient presents the token. Backend verifies:
    - Token hash matches
    - Token not expired
    - Token not already used

    If valid, marks as used and returns patient_id + scope.

    Returns None if token is invalid/expired/used.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    record = (
        db.query(EmergencyAccessToken)
        .filter(
            EmergencyAccessToken.token_hash == token_hash,
            EmergencyAccessToken.used == False,
        )
        .first()
    )

    if not record:
        logger.warning("Emergency token not found or already used")
        return None

    # Check expiry
    now = datetime.now(UTC)
    if now > record.expires_at:
        logger.warning("Emergency token expired")
        # Mark as used to prevent reuse attempts
        record.used = True
        record.used_at = now
        db.commit()
        return None

    # Mark as used (one-time)
    record.used = True
    record.used_at = now
    db.commit()

    logger.info("Emergency token consumed")

    return {
        "patient_id": record.patient_id,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "issued_by": record.issued_by,
        "verification_method": record.verification_method,
    }
