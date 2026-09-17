"""Systemic phone-scope invariant (Phase 0, PR #3320 review round 2).

Owner decision 2026-09-18 (variant A): a family phone may legally live on
many Patient CARDS, but Phase 0 never allows a SECOND active verified
Patient-user portal identity on the same normalized phone — the login
resolver (patient_otp_service.resolve_patient_user_by_phone) is
deliberately fail-closed at >1 candidates, so a second candidate would
permanently lock BOTH accounts out of OTP login.

The activation flow guards its own write path
(patient_activation_service). This module makes the invariant SYSTEMIC:
every mutation that can turn an existing record into a login-resolver
candidate (active + role=Patient + UserProfile.phone + phone_verified)
must pass the SAME phone-scope check under the SAME transaction-scoped
PostgreSQL advisory lock:

    - User Management ``update_user()``: reactivation of a Patient-user,
      role change -> Patient, and verified-phone changes;
    - staff-side profile updates that change ``UserProfile.phone``.

Verified-phone changes also reset ``phone_verified`` (possession is NOT
proven for an admin-entered number — same convention as the self-service
phone change in authentication_api_service), so an edited record leaves
the resolver predicate until a verified re-bind.

No UNIQUE is introduced on patients.phone / UserProfile.phone — the
restriction guards the portal identity only (owner decision; family
phones on cards remain legal).
"""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.roles import Roles
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import normalize_phone

logger = logging.getLogger(__name__)

# Admin-facing conflict message: the admin surface MAY name the conflict
# (the operator just attempted it — this is not an anti-enum surface).
ERR_PHONE_SCOPE_CONFLICT = (
    "Действие отклонено: этот номер телефона уже используется другим "
    "активным аккаунтом пациента портала. Второй активный аккаунт на тот "
    "же номер недоступен."
)


class PatientPhoneScopeConflict(Exception):
    """A mutation would create a SECOND active verified Patient-user on a
    phone that already has one. Maps to HTTP 409 at the API boundary."""

    status_code = 409

    def __init__(self, detail: str = ERR_PHONE_SCOPE_CONFLICT) -> None:
        super().__init__(detail)
        self.detail = detail


def phone_lock_key(normalized: str) -> int:
    """Stable signed-int64 advisory-lock key for a phone scope
    (domain-salted sha256 fingerprint — never the number itself).

    MUST stay byte-identical to the activation-flow key so both write
    paths serialize on the SAME lock."""
    digest = hashlib.sha256(b"patact:phone-lock:" + normalized.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def acquire_phone_scope_lock(db: Session, normalized: str) -> None:
    """Transaction-scoped PostgreSQL advisory lock on the phone scope.

    Serializes admin mutations against concurrent activations of OTHER
    cards sharing the phone (a single ``Patient ... FOR UPDATE`` cannot:
    family cards are different rows). Released automatically at
    commit/rollback. Non-PG dialects (SQLite unit tests) skip the lock;
    the candidate re-check still applies."""
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": phone_lock_key(normalized)},
    )


def count_active_verified_patient_users(
    db: Session, normalized: str, *, exclude_user_id: int | None = None
) -> int:
    """Mirror of the login-resolver candidate criteria as a COUNT.

    The resolver is fail-closed and returns None for BOTH 0 and >1
    candidates — ambiguous for a guard that must fire on >= 1. Counting
    the SAME WHERE-clause answers "would this mutation create candidate
    #2?". ``exclude_user_id`` removes the mutated record itself (an admin
    reactivating or re-pointing a user must not trip over their own row)."""
    stmt = (
        select(func.count())
        .select_from(User)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(
            UserProfile.phone == normalized,
            UserProfile.phone_verified.is_(True),
            User.role == Roles.PATIENT,
            User.is_active.is_(True),
        )
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return int(db.execute(stmt).scalar_one())


def ensure_phone_scope_free(
    db: Session, phone: str | None, *, exclude_user_id: int | None = None
) -> str:
    """Guard one mutation against the phone-scope invariant.

    Acquires the phone-scope advisory lock, then counts OTHER active
    verified Patient-users on the normalized phone. Raises
    :class:`PatientPhoneScopeConflict` when the mutation would create a
    second candidate; returns the normalized phone ("" for values that
    can never enter the resolver predicate — the caller proceeds).
    The lock lives until the caller's commit/rollback."""
    normalized = normalize_phone(phone or "")
    if not normalized:
        return ""
    acquire_phone_scope_lock(db, normalized)
    others = count_active_verified_patient_users(
        db, normalized, exclude_user_id=exclude_user_id
    )
    if others > 0:
        logger.warning(
            "phone-scope invariant: mutation rejected, phone already bound "
            "to another active patient portal account"
        )
        raise PatientPhoneScopeConflict()
    return normalized
