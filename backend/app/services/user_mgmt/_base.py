"""
Сервис для управления пользователями
"""

import csv  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
from datetime import UTC, datetime, timedelta  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401

from sqlalchemy import and_, or_  # noqa: F401
from sqlalchemy.exc import IntegrityError  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.core.security import get_password_hash  # noqa: F401
from app.core.specialties import (
    INCOMPLETE_DOCTOR_SPECIALTY,  # noqa: F401 — SSOT: core/specialties (D-1)
    canonical_specialty,
)
from app.models.clinic import Doctor  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_profile import (  # noqa: F401
    UserAuditLog,
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
    UserStatus,
)
from app.schemas.user_management import (  # noqa: F401
    UserBulkActionRequest,
    UserCreateRequest,
    UserExportRequest,
    UserNotificationSettingsUpdate,
    UserPreferencesUpdate,
    UserSearchRequest,
    UserUpdateRequest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifecycle invariant (1 User <-> 1 Doctor):
#     role=Doctor-family  <->  active linked Doctor profile
#
# DOCTOR_PROFILE_ROLES is the exact role set the auto-create contract in
# create_user() provisions a Doctor profile for. It intentionally matches
# core/roles.py DOCTOR_ROLES = {Doctor, cardio, derma, dentist} and adds the
# capitalized aliases also accepted by UserCreate.role — a role that gets a
# Doctor profile at user creation must behave identically at role promotion.
# ---------------------------------------------------------------------------
DOCTOR_PROFILE_ROLES: tuple[str, ...] = (
    "Doctor",
    "Cardiologist",
    "Dermatologist",
    "Dentist",
    "cardio",
    "derma",
    "dentist",
    # Codex round-9 P2: the specialty-route alias spellings (cardio.py
    # CARDIO_ROLES / derma.py DERMA_ROLES) are full doctor-family roles
    # for lifecycle purposes — without them a "cardiology"-role owner's
    # role change skipped demotion/reactivation entirely (lifecycle and
    # queue drift). Kept in lockstep with the canonical vocabulary below.
    "cardiology",
    "cardiologist",
    "dermatology",
    "dermatologist",
    "dentistry",
)


def _assert_profile_roles_cover_canonical_vocabulary() -> None:
    """Fail loudly at import if DOCTOR_PROFILE_ROLES drifts from the
    canonical doctor-role vocabulary (app/core/roles.py)."""
    from app.core.roles import DOCTOR_ROLE_SPELLINGS, normalize_role_value

    covered = {normalize_role_value(role) for role in DOCTOR_PROFILE_ROLES}
    missing = DOCTOR_ROLE_SPELLINGS - covered
    assert not missing, (
        "DOCTOR_PROFILE_ROLES is missing canonical doctor-role "
        f"spellings: {sorted(missing)}"
    )


_assert_profile_roles_cover_canonical_vocabulary()
# Default specialty written by the auto-create contract for each role.
# "Doctor" maps to the INCOMPLETE sentinel "general": the profile is created
# mechanically, but it is NOT a production specialty — admin must complete it
# (architecture decision #5). Legacy roles keep their specialty defaults.
DOCTOR_ROLE_DEFAULT_SPECIALTY: dict[str, str] = {
    "Doctor": "general",
    "Cardiologist": "cardiology",
    "Dermatologist": "dermatology",
    "Dentist": "dentistry",
    "cardio": "cardiology",
    "derma": "dermatology",
    "dentist": "dentistry",
}

# Sentinel specialty value marking an INCOMPLETE auto-created Doctor profile.
# Not a bookable production specialty: specialty-specific consumers (registrar
# exact-match, queue eligibility) must not treat it as a real specialty.
#
# SSOT moved to core/specialties (D-1) so CRUD, provisioning and Alembic
# migrations share one constant; re-exported above for backwards
# compatibility (all existing imports keep working).


def is_doctor_profile_incomplete(specialty: str | None) -> bool:
    """True when the Doctor profile still carries the auto-create placeholder
    specialty ("general") instead of a real canonical specialty.

    Uses the existing Doctor.specialty field as the marker — no extra state to
    keep in sync: completing the profile (admin sets a real specialty) atomically
    clears the flag, and nothing else can drift it.
    """
    cleaned = (specialty or "").strip()
    # Codex round-9 P2: a BLANK specialty ("" / whitespace, which
    # DoctorUpdate permits) is equally "not a real specialty" as the
    # sentinel — treat both as incomplete, otherwise a blank-specialty
    # doctor passes booking eligibility and the eligible_only selectors.
    return (not cleaned) or cleaned == INCOMPLETE_DOCTOR_SPECIALTY


class DoctorSpecialtyNotSelectableError(Exception):
    """Raised when a role promotion would (re)activate a Doctor profile
    whose specialty is not a selectable catalog code.

    Codex #3010 follow-up P1: the role-change lifecycle is the shared
    provisioning path — a deactivated catalog specialty must never be
    carried into an ACTIVE doctor profile (active-only queue/doctor
    selectors would return it). The account-level role change stays
    rejected (not silently degraded): the admin first assigns a valid
    specialty through the validated /admin/doctors boundary.
    """

    def __init__(self, specialty: str) -> None:
        self.specialty = specialty
        super().__init__(
            "Профиль врача хранит специальность, недоступную в каталоге "
            f"('{specialty}'): назначьте действующую специальность через "
            "административный контур врачей (PUT /admin/doctors/{id}) "
            "перед повторной активацией врачебной роли."
        )


def _mapped_specialty_selectable(db: Session, specialty: str) -> bool:
    """Catalog-guard helper shared by role-change provisioning paths.

    An UNUSABLE catalog (missing table / empty seed →
    ``MedicalSpecialtyCatalogError``) carries no deactivation information —
    keep the historical mapping rather than failing the operation (same
    trade-off as the provisioning auto-map in _core.py).
    """
    from app.services.medical_specialty_catalog import (
        MedicalSpecialtyCatalogError,
        MedicalSpecialtyCatalogService,
    )

    try:
        return MedicalSpecialtyCatalogService(db).is_selectable_for_onboarding(
            specialty
        )
    except MedicalSpecialtyCatalogError:
        return True


class UserManagementServiceMixinBase:
    """Type-hint anchor."""

    def _sync_doctor_active(
        self,
        db: Session,
        user_id: int,
        active: bool,
        *,
        reason: str = "owner_state_change",
        detach_owner: bool = False,
    ) -> int:
        """Mirror User.is_active onto the linked Doctor profile(s).

        Lifecycle contract (ghost-doctor prevention):
        - a deactivated User must not keep an ACTIVE clinical Doctor
          profile (it would stay visible in registrar selectors, queues
          and morning assignment while being unable to log in);
        - reactivating the User restores the Doctor profile;
        - when the owner User is deleted (detach_owner=True), the Doctor
          profile is deactivated and detached from the owner in the same
          transaction — never deleted. All historical visits/EMR/audit
          references to the Doctor row stay intact.

        detach_owner also makes the behavior deterministic on backends where
        the FK ``ON DELETE SET NULL`` action might not be enforced (e.g.
        SQLite connections without the foreign_keys pragma) — the ORM sets
        doctors.user_id to NULL explicitly instead of relying on the DDL.

        Returns the number of Doctor rows updated.
        """
        if active:
            # Lifecycle invariant: reactivating a User restores the linked
            # Doctor profile ONLY when the user's CURRENT role still belongs
            # to the doctor family. A demoted user (Registrar/Admin/other)
            # keeps the profile linked but INACTIVE — reactivation must never
            # resurrect it (non-doctor user != active Doctor profile).
            owner_role = db.query(User.role).filter(User.id == user_id).scalar()
            if owner_role not in DOCTOR_PROFILE_ROLES:
                logger.info(
                    "Doctor profiles NOT reactivated: owner role %r is not "
                    "doctor-family (user_id=%s reason=%s)",
                    owner_role,
                    user_id,
                    reason,
                )
                return 0

        values: dict[str, object] = {"active": active}
        if detach_owner:
            values["user_id"] = None
        filters = [Doctor.user_id == user_id]
        if not detach_owner:
            # No-op sync: skip rows already in the requested state.
            filters.append(Doctor.active != active)
        updated = (
            db.query(Doctor)
            .filter(*filters)
            .update(values, synchronize_session=False)
        )
        if updated:
            logger.info(
                "Doctor profiles synced to owner state: user_id=%s "
                "active=%s reason=%s rows=%s",
                user_id,
                active,
                reason,
                updated,
            )
        return updated

    def _apply_role_change_doctor_lifecycle(
        self,
        db: Session,
        user: User,
        old_role: str,
        new_role: str,
    ) -> None:
        """Enforce the lifecycle invariant across a role change:

            role=Doctor-family  <->  active linked Doctor profile

        Promotion (non-doctor -> doctor-family):
            ensure a linked Doctor profile exists. Reuses (reactivates) the
            user's own previous Doctor row when present — the same physical
            doctor keeps one clinical identity and all historical data. When
            absent, creates one in the controlled default (incomplete) state:
            specialty = DOCTOR_ROLE_DEFAULT_SPECIALTY[role] ("general" for the
            canonical Doctor role — admin must complete it, decision #5).

        Demotion (doctor-family -> non-doctor):
            deactivate the clinical Doctor profile so it disappears from
            registrar selectors / queues / schedules, while keeping the
            user_id link and ALL historical visits/EMR/audit rows intact
            (nothing is deleted or detached).

        Legacy-role compatibility: transitions inside the doctor-family
        (e.g. dentist -> Doctor) do not touch the existing profile — same
        clinical identity, specialty preserved. Runs inside the caller's
        transaction (no commit here).
        """
        old_is_doctor = old_role in DOCTOR_PROFILE_ROLES
        new_is_doctor = new_role in DOCTOR_PROFILE_ROLES
        if old_is_doctor == new_is_doctor:
            return  # transition inside or outside the doctor family

        if new_is_doctor:
            existing = (
                db.query(Doctor).filter(Doctor.user_id == user.id).first()
            )
            if existing is None:
                # Codex round-8 P2: a concurrent promotion of the same user
                # (or a parallel admin create) can insert the profile first;
                # UNIQUE(doctors.user_id) — model-enforced here, DB revision
                # ships in the sibling UNIQUE-constraint PR #2934 — rejects
                # the losing insert. INSERT ... ON CONFLICT DO NOTHING makes
                # the insert idempotent WITHOUT savepoints (session-level
                # savepoints conflict with the test-isolation recipe — see
                # the morning_assignment docstring): the loser simply adopts
                # whichever row is in the table after the statement, and the
                # caller's role-change transaction stays intact.
                specialty = DOCTOR_ROLE_DEFAULT_SPECIALTY.get(
                    new_role, INCOMPLETE_DOCTOR_SPECIALTY
                )
                # Codex #3010 follow-up P1: the role-change lifecycle is the
                # SHARED provisioning path (create and promotion must not
                # drift) — a role-mapped specialty that is no longer a
                # selectable catalog code (deactivated row) must not receive
                # a fresh ACTIVE doctor profile; provision the INCOMPLETE
                # sentinel instead (account still onboards, the profile
                # requires assignment through the validated boundary).
                if (
                    specialty != INCOMPLETE_DOCTOR_SPECIALTY
                    and not _mapped_specialty_selectable(db, specialty)
                ):
                    logger.warning(
                        "Role promotion downgraded mapped specialty: catalog "
                        "code %s is not selectable — incomplete profile "
                        "requires assignment via /admin/doctors",
                        specialty,
                    )
                    specialty = INCOMPLETE_DOCTOR_SPECIALTY
                values = {
                    "user_id": user.id,
                    "specialty": specialty,
                    "active": bool(user.is_active),
                }
                dialect_name = db.bind.dialect.name
                if dialect_name in ("postgresql", "sqlite"):
                    if dialect_name == "postgresql":
                        from sqlalchemy.dialects.postgresql import (
                            insert as dialect_insert,
                        )
                    else:
                        from sqlalchemy.dialects.sqlite import (
                            insert as dialect_insert,
                        )
                    db.execute(
                        dialect_insert(Doctor.__table__)
                        .values(**values)
                        .on_conflict_do_nothing()
                    )
                else:
                    # Legacy dialects: plain insert (the pre-check above
                    # remains the only guard, same as before this change).
                    db.add(Doctor(**values))
                    db.flush()
                doctor = (
                    db.query(Doctor)
                    .filter(Doctor.user_id == user.id)
                    .first()
                )
                if doctor is None:  # pragma: no cover — defensive
                    db.add(Doctor(**values))
                    db.flush()
                    doctor = (
                        db.query(Doctor)
                        .filter(Doctor.user_id == user.id)
                        .first()
                    )
                logger.info(
                    "Doctor profile ensured on role promotion: user_id=%s "
                    "role=%s doctor_id=%s specialty=%r (incomplete=%s)",
                    user.id,
                    new_role,
                    doctor.id,
                    doctor.specialty,
                    is_doctor_profile_incomplete(doctor.specialty),
                )
            elif not existing.active and user.is_active:
                # Codex #3010 follow-up P1: activation carries the STORED
                # specialty into a new active assignment. A non-selectable
                # REAL code (deactivated row / unknown value) must not be
                # reactivated — reject the role change with a descriptive
                # error so the admin assigns a valid specialty first. The
                # incomplete sentinel stays allowed: it is not bookable and
                # active-only selectors exclude it, and blocking it would
                # break the mechanical promote→demote→promote cycle.
                stored_specialty = (existing.specialty or "").strip()
                # D-1: legacy dental-family spellings (stomatology/dental/
                # dentist) are the SAME specialty as the catalog's canonical
                # 'dentistry' — check selectability of the CANONICAL form so
                # a pre-0049 legacy row is not falsely rejected.
                stored_canonical = canonical_specialty(stored_specialty)
                if (
                    stored_canonical
                    and stored_canonical != INCOMPLETE_DOCTOR_SPECIALTY
                    and not _mapped_specialty_selectable(db, stored_canonical)
                ):
                    raise DoctorSpecialtyNotSelectableError(stored_specialty)
                existing.active = True
                db.flush()
                logger.info(
                    "Doctor profile reactivated on role promotion: user_id=%s "
                    "role=%s doctor_id=%s",
                    user.id,
                    new_role,
                    existing.id,
                )
        else:
            self._sync_doctor_active(
                db,
                user.id,
                False,
                reason="role_demotion_from_doctor_role",
            )












































































































































