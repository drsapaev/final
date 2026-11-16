"""Transaction-bound identity and contact guards for profile writers."""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import Roles
from app.core.user_token_claims import (
    is_user_access_claims,
    is_user_allowed_for_claims,
    parse_user_auth_epoch,
)
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import normalize_phone
from app.services.patient_phone_scope import (
    acquire_phone_scope_lock,
    ensure_phone_scope_free,
)
from app.services.token_blacklist_service import token_blacklist_service


class ProfileBearerInvalid(ValueError):
    """The caller's session is invalid, expired or revoked."""


@dataclass(frozen=True)
class ProfileBearerContext:
    user_id: int
    auth_epoch: int
    jti: str | None
    expires_at: int | None
    patient_id: int | None


def capture_profile_bearer(request: Request, user: User) -> ProfileBearerContext:
    """Capture signed claims after the canonical dependency validates access."""
    scheme, token = get_authorization_scheme_param(request.headers.get("Authorization"))
    if scheme.lower() != "bearer" or not token:
        raise ProfileBearerInvalid("Bearer session unavailable")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        epoch = parse_user_auth_epoch(payload)
        if (
            not is_user_access_claims(payload)
            or payload.get("sub") != str(user.id)
            or epoch is None
            or epoch != user.auth_epoch
        ):
            raise ValueError("Invalid bearer claims")
        jti = payload.get("jti")
        if jti is not None and not isinstance(jti, str):
            raise ValueError("Invalid bearer identifier")
        raw_exp = payload.get("exp")
        if isinstance(raw_exp, bool):
            raise ValueError("Invalid bearer expiration")
        expires_at = int(raw_exp) if raw_exp is not None else None
        patient_id = payload.get("patient_id") if payload.get("scope") == "patient_portal" else None
        return ProfileBearerContext(user.id, epoch, jti, expires_at, patient_id)
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError) as exc:
        raise ProfileBearerInvalid("Bearer session unavailable") from exc


def lock_profile_users(db: Session, actor_id: int, target_id: int) -> tuple[User, User | None]:
    """Lock both users in stable ID order to avoid cross-admin deadlocks."""
    users = (
        db.query(User)
        .filter(User.id.in_(sorted({actor_id, target_id})))
        .order_by(User.id)
        .with_for_update(key_share=True)
        .populate_existing()
        .all()
    )
    by_id = {user.id: user for user in users}
    actor = by_id.get(actor_id)
    if actor is None or not actor.is_active:
        raise ProfileBearerInvalid("Bearer session unavailable")
    return actor, by_id.get(target_id)


def check_profile_bearer(db: Session, actor: User, context: ProfileBearerContext) -> None:
    """Recheck epoch, exact JTI and expiry under the caller's User lock."""
    if (
        actor.id != context.user_id
        or not actor.is_active
        or actor.auth_epoch != context.auth_epoch
        or (context.expires_at is not None and time.time() >= context.expires_at)
        or token_blacklist_service.is_token_blacklisted(
            db, context.jti or "", user_id=actor.id, auth_epoch=context.auth_epoch
        )
    ):
        raise ProfileBearerInvalid("Bearer session unavailable")


def check_bearer_expiry(context: ProfileBearerContext) -> None:
    """The User lock prevents revocation races; time may still advance."""
    if context.expires_at is not None and time.time() >= context.expires_at:
        raise ProfileBearerInvalid("Bearer session unavailable")


def lock_profile(db: Session, user_id: int) -> UserProfile | None:
    return (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .with_for_update()
        .populate_existing()
        .first()
    )


def check_patient_scope(db: Session, actor: User, context: ProfileBearerContext) -> None:
    """Honor a patient-scoped bearer after locking User and profile rows."""
    if context.patient_id is None:
        return
    if not is_user_allowed_for_claims(
        {"scope": "patient_portal"}, role=actor.role,
        is_active=actor.is_active, is_superuser=actor.is_superuser,
    ):
        raise ProfileBearerInvalid("Bearer session unavailable")
    patient = (
        db.query(Patient.id)
        .filter(
            Patient.id == context.patient_id,
            Patient.user_id == actor.id,
            Patient.is_deleted.is_not(True),
        )
        .with_for_update()
        .first()
    )
    if patient is None:
        raise ProfileBearerInvalid("Bearer session unavailable")


def prepare_phone_change(db: Session, profile: UserProfile, update_data: dict) -> bool:
    """Canonicalize a phone update, lock both scopes, and report real change."""
    if "phone" not in update_data:
        return False
    old_value, new_value = profile.phone, update_data["phone"]
    old_normalized = normalize_phone(old_value or "")
    new_normalized = normalize_phone(new_value or "")
    old_key = old_normalized if old_normalized else old_value
    new_key = new_normalized if new_normalized else new_value
    if new_normalized:
        update_data["phone"] = new_normalized
    if old_key == new_key:
        return False
    for phone in sorted({value for value in (old_normalized, new_normalized) if value}):
        acquire_phone_scope_lock(db, phone)
    return True


def enforce_phone_scope(db: Session, target: User, update_data: dict) -> None:
    """Check uniqueness after the actor's scoped identity is revalidated."""
    phone = normalize_phone(update_data.get("phone") or "")
    if phone and target.role == Roles.PATIENT:
        ensure_phone_scope_free(db, phone, exclude_user_id=target.id)
