"""Claims boundary for JWTs that identify an application User.

Call only after validating the JWT signature and expiration. Telegram Mini App
patient tokens use patient IDs as ``sub`` and share the signing key; that
subject is not a User ID even if their numeric values happen to coincide.
"""

from typing import Any


def is_user_access_claims(payload: dict[str, Any]) -> bool:
    """Accept canonical User access tokens, including untyped legacy tokens."""
    # Legacy Mini App scopes identify a patient card, not a User. The
    # patient_portal scope identifies a User and additionally binds the token
    # to a currently active, non-superuser Patient role after lookup.
    if "scope" in payload and payload["scope"] != "patient_portal":
        return False
    if payload.get("scope") == "patient_portal":
        patient_id = payload.get("patient_id")
        subject = payload.get("sub")
        if (
            type(patient_id) is not int
            or patient_id <= 0
            or not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isdigit()
            or len(subject) > 20
            or int(subject) <= 0
            or "username" in payload
        ):
            return False
    # Older User access issuers omit type. Explicitly typed credentials must
    # be access tokens; refresh, 2FA and scoped device tokens are not logins.
    for key in ("type", "typ", "token_type"):
        if key in payload and payload[key] != "access":
            return False
    return True


def patient_binding_statement(payload: dict[str, Any], user_id: int):
    """Query the current active card bound to a scoped User token."""
    from sqlalchemy import func, select

    from app.models.patient import Patient
    from app.models.user import User

    return (
        select(Patient.id)
        .join(User, Patient.user_id == User.id)
        .where(
            Patient.id == payload["patient_id"],
            User.id == user_id,
            Patient.is_deleted.is_not(True),
            User.is_active.is_(True),
            User.is_superuser.is_(False),
            func.lower(func.trim(User.role)) == "patient",
        )
    )


def has_patient_binding(db: Any, payload: dict[str, Any], user_id: int) -> bool:
    """Fail closed when a patient-scoped token loses its card binding."""
    if payload.get("scope") != "patient_portal":
        return True
    try:
        return (
            db.execute(patient_binding_statement(payload, user_id)).first() is not None
        )
    except Exception:
        return False


def is_user_allowed_for_claims(
    payload: dict[str, Any], *, role: object, is_active: object, is_superuser: object
) -> bool:
    """Enforce the role boundary for a patient-portal User access token."""
    if payload.get("scope") != "patient_portal":
        return True
    role_value = getattr(role, "value", role)
    return (
        isinstance(role_value, str)
        and role_value.strip().lower() == "patient"
        and is_active is True
        and is_superuser is False
    )
