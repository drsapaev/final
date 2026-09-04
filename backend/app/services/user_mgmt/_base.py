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


# Codex #3031 round-3 P2: single remediation wording shared by the
# single-user (update_user) and bulk (bulk_action_users) catalog gates —
# the same configuration message the POST /users boundary documents.
MEDICAL_SPECIALTY_CATALOG_REMEDIATION = (
    "Каталог медицинских специальностей не настроен: "
    "выполните миграции БД (baseline seed 0051)."
)


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

    RAISES ``MedicalSpecialtyCatalogError`` when the catalog is UNUSABLE
    (missing table / empty seed) instead of swallowing it: on PostgreSQL a
    failed catalog SELECT has already aborted the transaction, so a
    swallowed fallback would only defer the failure to the next statement
    (InFailedSqlTransaction → generic 400). Propagating lets update_user
    answer with the configuration-remediation message. (The POST /users
    legacy auto-map keeps a different, owner-pinned trade-off — historical
    mapping on an unusable catalog — out of scope here.)
    """
    from app.services.medical_specialty_catalog import (
        MedicalSpecialtyCatalogService,
    )

    return MedicalSpecialtyCatalogService(db).is_selectable_for_onboarding(
        specialty
    )


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
        pending_role: str | None = None,
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
            # Codex #3031 round-7 P2: ``update_user`` assigns the pending
            # role BEFORE mirroring is_active, but SessionLocal runs with
            # autoflush=False (backend/app/db/session.py) — the scalar query
            # below still reads the STORED role. On a combined
            # {"role": "Registrar", "is_active": true} reactivation-plus-
            # demotion the stale read made the mirror treat the account as
            # an active doctor: it resurrected the profile and ran the
            # catalog guard against a state the request was about to
            # abandon — rejecting a SAFE recovery (the intended end state is
            # an active non-doctor with an INACTIVE profile) when the old
            # profile's specialty was unavailable or the catalog
            # unconfigured. ``pending_role`` carries the effective target
            # role so the gate reflects the REQUEST's outcome, not the
            # pre-flush snapshot; demotion-before-activation skips the
            # resurrection AND its catalog dependency entirely.
            owner_role = (
                pending_role
                if pending_role is not None
                else db.query(User.role).filter(User.id == user_id).scalar()
            )
            if owner_role not in DOCTOR_PROFILE_ROLES:
                logger.info(
                    "Doctor profiles NOT reactivated: owner role %r is not "
                    "doctor-family (user_id=%s reason=%s)",
                    owner_role,
                    user_id,
                    reason,
                )
                return 0
            # Codex #3031 round-3 P1: the shared mirror is ALSO the
            # activation-only path (update_user {"is_active": true} and bulk
            # activate) — enforce the same catalog contract the promotion
            # path enforces: a profile whose stored specialty is a
            # deactivated/unknown catalog code must not become ACTIVE
            # through a plain reactivation either. Validate every profile
            # ABOUT to flip inactive->active (the UPDATE below skips rows
            # already in the requested state). D-1: legacy dental-family
            # spellings normalize via canonical_specialty; the INCOMPLETE
            # sentinel stays allowed (not bookable, excluded from
            # active-only selectors — the mechanical promote->demote->promote
            # cycle stays green). The probe runs on a HEALTHY catalog (the
            # SELECT succeeds), so this error is pure Python and never
            # aborts the transaction; an UNUSABLE catalog raises
            # MedicalSpecialtyCatalogError from the probe itself —
            # update_user translates it into the remediation 400, and
            # bulk_action_users pre-flights it (round-3 P2) before any
            # per-user work.
            for row in (
                db.query(Doctor)
                .filter(Doctor.user_id == user_id, Doctor.active.is_(False))
                .all()
            ):
                stored_specialty = (row.specialty or "").strip()
                stored_canonical = canonical_specialty(stored_specialty)
                if (
                    stored_canonical
                    and stored_canonical != INCOMPLETE_DOCTOR_SPECIALTY
                    and not _mapped_specialty_selectable(db, stored_canonical)
                ):
                    raise DoctorSpecialtyNotSelectableError(stored_specialty)

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
            else:
                # Codex #3031 round-1: a promotion carries the stored
                # specialty into an ACTIVE profile whether activation
                # happens HERE or already happened earlier in the same
                # transaction — update_user mirrors is_active via
                # _sync_doctor_active BEFORE the role-change block, and on
                # a simultaneous {"role": "derma", "is_active": true} the
                # owner-role probe sees the NEW doctor-family role and
                # activates the row first. Validate whenever the user is
                # active. A non-selectable REAL code (deactivated row /
                # unknown value) must not reach an ACTIVE profile — reject
                # the role change with a descriptive error so the admin
                # assigns a valid specialty first. D-1: legacy dental-family
                # spellings are normalized before the check (pre-0049 rows
                # are the SAME specialty as the catalog's 'dentistry'). The
                # sentinel stays allowed: not bookable and excluded from
                # active-only selectors, so blocking it would break the
                # mechanical promote→demote→promote cycle.
                stored_specialty = (existing.specialty or "").strip()
                stored_canonical = canonical_specialty(stored_specialty)
                if (
                    user.is_active
                    and stored_canonical
                    and stored_canonical != INCOMPLETE_DOCTOR_SPECIALTY
                    and not _mapped_specialty_selectable(db, stored_canonical)
                ):
                    raise DoctorSpecialtyNotSelectableError(stored_specialty)
                if not existing.active and user.is_active:
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












































































































































