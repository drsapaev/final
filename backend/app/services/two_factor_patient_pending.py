"""Pending second-factor challenges preserving patient login provenance.

The kind and passkey patient id are server-side session data; the bearer
challenge itself remains an opaque random value. Callers hold the User lock.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.authentication import UserSession
from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User

SMS_KIND = "pending_patient_2fa"
PASSKEY_KIND_PREFIX = "p2fa_pk:"
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_MAX_ID = 2**63 - 1


def _base36(value: int) -> str:
    result = ""
    while value:
        value, digit = divmod(value, 36)
        result = _DIGITS[digit] + result
    return result


def patient_pending_kind(patient_id: int | None) -> str:
    if patient_id is None:
        return SMS_KIND
    if type(patient_id) is not int or not 0 < patient_id <= _MAX_ID:
        raise ValueError("Invalid patient identity")
    kind = PASSKEY_KIND_PREFIX + _base36(patient_id)
    if len(kind) > 32:
        raise ValueError("Patient identity exceeds session storage")
    return kind


def is_patient_pending_kind(kind: str | None) -> bool:
    return kind == SMS_KIND or bool(kind and kind.startswith(PASSKEY_KIND_PREFIX))


def parse_patient_pending_kind(kind: str) -> int | None:
    """Return the original passkey card id, or None for SMS; reject bad data."""
    if kind == SMS_KIND:
        return None
    if not isinstance(kind, str) or not re.fullmatch(
        r"p2fa_pk:[1-9a-z][0-9a-z]{0,12}", kind
    ):
        raise ValueError("Invalid patient pending session")
    value = int(kind[len(PASSKEY_KIND_PREFIX) :], 36)
    if not 0 < value <= _MAX_ID or patient_pending_kind(value) != kind:
        raise ValueError("Invalid patient pending session")
    return value


def pending_session_kind_filter(column):
    """Include legacy login challenges plus the two patient challenge kinds."""
    return or_(
        column.is_(None),
        column == "pending_2fa",
        column == SMS_KIND,
        column.startswith(PASSKEY_KIND_PREFIX, autoescape=True),
    )


def create_patient_pending_2fa_locked(
    db: Session, user: User, *, patient_id: int | None = None
) -> dict | None:
    """Create an uncommitted pending challenge when verified TOTP is enabled.

    Caller must hold the live User lock through its own commit or rollback.
    Passkey callers must already validate and lock the bound Patient card.
    """
    if not user.is_active or user.is_superuser or user.role != "Patient":
        raise ValueError("Patient identity unavailable")
    two_factor = (
        db.query(TwoFactorAuth)
        .filter(TwoFactorAuth.user_id == user.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if (
        two_factor is None
        or not two_factor.totp_enabled
        and not two_factor.totp_verified
    ):
        return None
    if not two_factor.totp_enabled or not two_factor.totp_verified:
        raise ValueError("Patient two-factor state unavailable")
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            refresh_token=token,
            session_kind=patient_pending_kind(patient_id),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    return {
        "requires_2fa": True,
        "two_factor_method": "totp",
        "pending_2fa_token": token,
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
