"""Patient activation service (Phase 0, PR-A2).

Owner-approved identity contract v3 (plan v2/v3 + 6 final corrections):
    Phone is a POSSESSION factor, not patient identity. Activation binds
    an EXACT Patient.id + the normalized Patient.phone captured AT TOKEN
    ISSUANCE — never a phone-derived patient lookup.

Flow (owner-approved):
    1. Registrar (Admin|Registrar role) issues an activation token for a
       specific patient card: POST /patients/{id}/activation-token.
       Token is bound to (Patient.id, normalized Patient.phone) and lives
       72h in Redis, stored HASH-ONLY (sha256).
    2. Patient submits the token -> activation OTP is sent ONLY to the
       phone number captured at issuance. Client-supplied phone numbers
       are never accepted (owner correction #2).
    3. Patient confirms the OTP -> ONE atomic transaction creates
       User(role=Patient) + UserProfile(phone, phone_verified=True) and
       links Patient.user_id. Owner correction #3: crud_user.create_user()
       is FORBIDDEN here (it commits internally) — staged ORM flushes with
       a single final commit after all guards, SELECT ... FOR UPDATE on the
       patient row, UNIQUE(patients.user_id) as a race backstop.
    4. Passwordless patient (owner correction #4): hashed_password holds a
       normal argon2 hash of a random unknown secret — NO sentinel values.
    5. Canonical session only (owner correction #5): the returned JWT is
       the standard User access token via create_access_token({"sub": id});
       no Telegram-style patient JWT / negative-user-session paths.
    6. Token lifecycle: single-use (GETDEL on success), revocable (reissue
       invalidates the previous token), unusable if the patient is deleted,
       already linked, or the card phone changed after issuance (then a
       registrar reissue is required) — owner correction #2.

KV layout (Redis prod / in-memory TESTING, shared with patient_otp_service):
    patact:token:{sha256(token)}  -> JSON {patient_id, phone}   TTL 72h
    patact:idx:{patient_id}       -> sha256(token) (revocation
                                     index — SOURCE OF TRUTH for
                                     token lookups)             TTL 72h
Activation OTP keys live in the isolated patact:* namespace of
patient_otp_service (cooldown/cap/attempts never touch login OTP state).
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import log_critical_change
from app.core.pii_masker import mask_phone as _canonical_mask_phone
from app.core.roles import Roles
from app.core.security import get_password_hash
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import (
    PatientOtpError,
    get_patient_otp_service,
    normalize_phone,
)
from app.services.patient_phone_scope import (
    acquire_phone_scope_lock as _acquire_phone_scope_lock_impl,
)
from app.services.patient_phone_scope import (
    count_active_verified_patient_users as _portal_user_count_impl,
)
from app.services.patient_phone_scope import phone_lock_key as _phone_lock_key_impl

logger = logging.getLogger(__name__)

# --- Parameters -----------------------------------------------------------
ACTIVATION_TOKEN_TTL_SECONDS = 72 * 3600  # owner-approved 72h window

# --- KV namespaces (token itself, not the OTP) ----------------------------
_TOKEN_NS = "patact:token"  # patact:token:{sha256(token)} -> entry JSON
_PATIENT_IDX_NS = "patact:idx"  # patact:idx:{patient_id} -> token hash

# --- Client-visible neutral errors ----------------------------------------
ERR_TOKEN_INVALID = (
    "Токен активации недействителен или истёк. Запросите новый в регистратуре."
)
ERR_ACTIVATION_GENERIC = (
    "Не удалось активировать доступ. Попробуйте позже или обратитесь в регистратуру."
)
ERR_PATIENT_NOT_FOUND = "Пациент не найден."
ERR_PATIENT_ALREADY_LINKED = "Доступ для этого пациента уже активирован."
ERR_PATIENT_NO_PHONE = (
    "У пациента нет корректного номера телефона (+998XXXXXXXXX) для активации."
)
# Owner GO 2026-09-18 (variant A): a family phone may legally live on many
# cards, but Phase 0 never creates a SECOND active verified Patient-user on
# the same normalized phone (the login resolver is deliberately fail-closed
# at >1 candidates). No UNIQUE on patients.phone / UserProfile.phone is
# introduced — the restriction guards the portal identity only.
ERR_ISSUANCE_PHONE_BOUND = (
    "Портал-доступ с этим номером телефона уже активирован для другой карты. "
    "Активация второго аккаунта на тот же номер недоступна."
)
ERR_PHONE_ALREADY_BOUND = (
    "Этот номер телефона уже привязан к активному аккаунту портала. "
    "Обратитесь в регистратуру."
)


@dataclass
class ActivationError(Exception):
    status_code: int
    detail: str


def mask_phone(phone: str) -> str:
    """Canonical repo-wide PII mask (AGENTS.md / app.core.pii_masker):
    +998901112233 -> +998900•••001 — only the LAST THREE digits survive.

    Codex P1 (PR #3320 round 1): the previous local 4-digit mask emitted
    more of the number than the repository policy allows. Non-maskable
    input degrades to full redaction instead of leaking."""
    masked = _canonical_mask_phone(phone)
    if not masked or masked == phone or "•" not in masked:
        return "***"
    return masked


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Review round 2 (P1): the phone-scope primitives moved to the systemic
# guard module app.services.patient_phone_scope so User Management and
# profile mutations serialize on the SAME advisory lock and count with the
# SAME resolver-predicate mirror. These module-level wrappers keep the
# historical monkeypatch hooks (tests patch these names) as single-source
# delegations.
def _phone_lock_key(normalized: str) -> int:
    """Stable signed-int64 advisory-lock key (delegates to the systemic
    patient_phone_scope module — identical salt, identical lock)."""
    return _phone_lock_key_impl(normalized)


def _acquire_phone_scope_lock(db: Session, normalized: str) -> None:
    """Serialize mutations across DIFFERENT patient rows sharing a phone.

    A single `Patient ... FOR UPDATE` locks ONE row — two family cards are
    different rows and would not block each other (owner GO point 3). The
    transaction-scoped PostgreSQL advisory lock keyed by the hashed phone
    serializes the whole phone scope and is released automatically at
    commit/rollback. Non-PG dialects (SQLite unit tests) skip the lock;
    the pre/under-lock re-checks and the UNIQUE backstops still apply."""
    _acquire_phone_scope_lock_impl(db, normalized)


def _portal_user_count_for_phone(db: Session, normalized: str) -> int:
    """Mirror of the login-resolver candidate criteria
    (patient_otp_service.resolve_patient_user_by_phone) as a COUNT.

    The resolver itself is fail-closed and returns None for BOTH 0 and >1
    candidates — ambiguous for a guard that must fire on >= 1. Counting the
    SAME WHERE-clause answers exactly "would this activation create
    candidate #2?"."""
    return _portal_user_count_impl(db, normalized)


class PatientActivationService:
    """Registrar-issued activation tokens + atomic patient linking."""

    # -- token issuance (staff) ------------------------------------------
    def issue_activation_token(self, db: Session, patient_id: int) -> dict[str, Any]:
        """Bind a fresh single-use token to (Patient.id, normalized phone).

        Staff-only (caller enforces RBAC). Reissue revokes the previous
        token for the patient. The plaintext token is returned ONCE."""
        patient = db.execute(
            select(Patient).where(Patient.id == patient_id)
        ).scalar_one_or_none()
        if patient is None or patient.is_deleted:
            raise ActivationError(404, ERR_PATIENT_NOT_FOUND)
        if patient.user_id is not None:
            raise ActivationError(409, ERR_PATIENT_ALREADY_LINKED)
        normalized = normalize_phone(patient.phone or "")
        if not normalized:
            raise ActivationError(400, ERR_PATIENT_NO_PHONE)

        # Owner GO (variant A, point 1): early staff-side guard — the
        # registrar learns about a family-phone conflict BEFORE any token
        # exists (fail fast; no doomed SMS round-trip later).
        if _portal_user_count_for_phone(db, normalized) > 0:
            raise ActivationError(409, ERR_ISSUANCE_PHONE_BOUND)

        try:
            backend = get_patient_otp_service().get_backend()
        except PatientOtpError as err:
            # Codex P2: KV outage surfaces as the documented generic
            # ActivationError, not an unhandled PatientOtpError/500.
            raise ActivationError(err.status_code, err.detail) from err
        token = secrets.token_urlsafe(32)
        t_hash = _token_hash(token)

        # Codex P2 (round 2): the backend may be CREATED successfully and
        # STILL drop mid-operation (connection reset/timeout after init).
        # _RedisBackend now normalizes infra failures into PatientOtpError,
        # so every KV door here surfaces as the documented 503 instead of
        # an undocumented 500.
        try:
            # Reissue revokes any outstanding token for this patient.
            old_hash = backend.get(f"{_PATIENT_IDX_NS}:{patient.id}")
            if old_hash:
                backend.delete(f"{_TOKEN_NS}:{old_hash}")

            entry = json.dumps({"patient_id": patient.id, "phone": normalized})
            backend.set(f"{_TOKEN_NS}:{t_hash}", entry, ACTIVATION_TOKEN_TTL_SECONDS)
            backend.set(
                f"{_PATIENT_IDX_NS}:{patient.id}", t_hash, ACTIVATION_TOKEN_TTL_SECONDS
            )
        except PatientOtpError as err:
            raise ActivationError(err.status_code, err.detail) from err

        logger.info(
            "activation token issued: patient_id=%s phone=%s",
            patient.id,
            mask_phone(normalized),
        )
        return {
            "activation_token": token,
            "expires_in_hours": ACTIVATION_TOKEN_TTL_SECONDS // 3600,
            "phone_masked": mask_phone(normalized),
        }

    # -- token lookup / state validation ---------------------------------
    def _lookup_entry(self, token: str) -> dict[str, Any] | None:
        if not token or not (16 <= len(token) <= 256):
            return None
        t_hash = _token_hash(token)
        try:
            backend = get_patient_otp_service().get_backend()
            raw = backend.get(f"{_TOKEN_NS}:{t_hash}")
        except PatientOtpError as err:
            raise ActivationError(err.status_code, err.detail) from err
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            if (
                not isinstance(entry, dict)
                or "patient_id" not in entry
                or "phone" not in entry
            ):
                return None
        except Exception:  # noqa: BLE001 - corrupt entry -> invalid token
            return None
        try:
            idx = backend.get(f"{_PATIENT_IDX_NS}:{entry['patient_id']}")
        except PatientOtpError as err:
            raise ActivationError(err.status_code, err.detail) from err
        # Codex P2 (reissue race): the revocation index is the source of
        # truth. A losing concurrent reissue can leave its token entry
        # behind; index mismatch/absence means REVOKED.
        if idx != t_hash:
            return None
        return entry

    def _validate_patient_state(
        self, db: Session, entry: dict[str, Any]
    ) -> Patient | None:
        """The token is usable ONLY while the card still matches the state
        captured at issuance: exists, not deleted, NOT yet linked, phone
        unchanged. Any drift makes the token unusable (reissue required)."""
        patient = db.execute(
            select(Patient).where(Patient.id == entry["patient_id"])
        ).scalar_one_or_none()
        if patient is None or patient.is_deleted:
            return None
        if patient.user_id is not None:
            return None
        if normalize_phone(patient.phone or "") != entry["phone"]:
            return None
        return patient

    # -- step 2: OTP to the card phone ONLY ------------------------------
    async def request_activation_otp(
        self, db: Session, token: str, locale: str | None = None
    ) -> dict[str, Any]:
        entry = self._lookup_entry(token)
        if entry is None:
            raise ActivationError(400, ERR_TOKEN_INVALID)
        if self._validate_patient_state(db, entry) is None:
            raise ActivationError(400, ERR_TOKEN_INVALID)
        # Owner GO (variant A, point 2): never send an SMS for a doomed
        # activation. Neutral generic response — reveals nothing about
        # other accounts (anti-enum).
        if _portal_user_count_for_phone(db, entry["phone"]) > 0:
            raise ActivationError(409, ERR_ACTIVATION_GENERIC)
        try:
            await get_patient_otp_service().send_activation_otp(entry["phone"], locale)
        except PatientOtpError as err:
            raise ActivationError(err.status_code, err.detail) from err
        return {
            "phone_masked": mask_phone(entry["phone"]),
            "expires_in_minutes": 5,
            "resend_after_seconds": 60,
        }

    # -- step 3: atomic activation ---------------------------------------
    def activate(self, db: Session, token: str, code: str) -> dict[str, Any]:
        """OTP + token -> canonical User(role=Patient) session.

        Order (owner GO 2026-09-18, variant A): token lookup -> phone-scope
        precheck (no OTP burned on a doomed activation) -> transaction-
        scoped advisory lock on the phone fingerprint -> authoritative
        candidate RE-READ under the lock -> OTP verify (single-use) ->
        locked patient revalidation -> staged User+UserProfile+link ->
        ONE commit -> token consumed. Every failure is generic (anti-enum)."""
        entry = self._lookup_entry(token)
        if entry is None:
            raise ActivationError(400, ERR_TOKEN_INVALID)

        # Owner GO (variant A, points 3-5): phone-scope serialization.
        # Pre-transaction check first: a deterministically doomed activation
        # must not consume a valid single-use OTP (owner point 5).
        if _portal_user_count_for_phone(db, entry["phone"]) > 0:
            raise ActivationError(409, ERR_PHONE_ALREADY_BOUND)

        # A single `Patient ... FOR UPDATE` does NOT serialize two DIFFERENT
        # family cards sharing one phone — the phone-scope advisory lock
        # does. State under the lock is RE-READ, never trusted from the
        # precheck (owner point 5).
        _acquire_phone_scope_lock(db, entry["phone"])
        if _portal_user_count_for_phone(db, entry["phone"]) > 0:
            db.rollback()  # release the lock; OTP still intact
            raise ActivationError(409, ERR_PHONE_ALREADY_BOUND)

        otp_service = get_patient_otp_service()
        try:
            # Single-use OTP consumed ONLY after the authoritative check.
            otp_service.verify_activation_otp(entry["phone"], code)
        except PatientOtpError as err:
            db.rollback()  # release the lock; nothing was written
            raise ActivationError(err.status_code, err.detail) from err

        # Lock the patient row: serializes concurrent activations of the
        # same card; second contender sees user_id set and fails closed.
        patient = db.execute(
            select(Patient).where(Patient.id == entry["patient_id"]).with_for_update()
        ).scalar_one_or_none()
        if (
            patient is None
            or patient.is_deleted
            or patient.user_id is not None
            or normalize_phone(patient.phone or "") != entry["phone"]
        ):
            raise ActivationError(400, ERR_TOKEN_INVALID)

        username = self._generate_unique_username(db, patient.id)

        # Codex P2 (round 2): users.full_name is VARCHAR(100) while Patient
        # names are 3 x VARCHAR(128) — compute ONE bounded display name for
        # BOTH rows, or a schema-valid long name would fail the PostgreSQL
        # flush AFTER the single-use OTP was already consumed.
        display_name = patient.short_name()[:100]

        # Owner correction #4: normal hash of a random unknown secret.
        user = User(
            username=username,
            full_name=display_name,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            role=Roles.PATIENT,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()  # staged: user.id available, NOT committed (correction #3)

        profile = UserProfile(
            user_id=user.id,
            full_name=display_name,
            first_name=(patient.first_name or "")[:50] or None,
            last_name=(patient.last_name or "")[:50] or None,
            phone=entry["phone"],
            phone_verified=True,
        )
        db.add(profile)
        db.flush()

        patient.user_id = user.id  # UNIQUE(patients.user_id) = race backstop

        # Codex P2 (round 2): durable audit of the IDENTITY LINKING itself
        # ("Patient.id N was bound to User.id M — a new authentication
        # principal was created"), written in the SAME transaction as the
        # link so "link committed without audit" is impossible. The
        # activation is self-service: the new principal is the actor.
        log_critical_change(
            db,
            user_id=user.id,
            action="UPDATE",
            table_name="patients",
            row_id=patient.id,
            old_data={"user_id": None},
            new_data={"user_id": user.id},
            description=(
                "Patient portal activation: patient card linked to a newly "
                "created portal account (authentication principal created)"
            ),
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            # CodeQL 1313 fix: constant message — no entry-derived values and
            # no raw DB error text (constraint detail) in logs.
            logger.warning(
                "activation commit conflict (UNIQUE race backstop) -> generic 409"
            )
            raise ActivationError(409, ERR_ACTIVATION_GENERIC) from exc
        db.refresh(patient)
        db.refresh(user)

        # Token is single-use: consumed ONLY after a successful commit. A KV
        # outage here must NOT fail an already-committed activation — the
        # linked card makes the token unusable anyway (state revalidation).
        # Codex P2 (round 2): best-effort by contract — ANY cleanup failure
        # (PatientOtpError from the normalized backend, or anything else
        # unexpected) must never turn a committed activation into a 500.
        try:
            backend = otp_service.get_backend()
            backend.getdel(f"{_TOKEN_NS}:{_token_hash(token)}")
            backend.delete(f"{_PATIENT_IDX_NS}:{entry['patient_id']}")
        except Exception:  # noqa: BLE001 - post-commit cleanup is best-effort
            logger.warning("activation token cleanup skipped: KV unavailable")

        logger.info("patient activated: patient_id=%s user_id=%s", patient.id, user.id)

        from app.api.deps import create_access_token

        access_token = create_access_token(data={"sub": str(user.id)})
        return {
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
            "patient_id": patient.id,
        }

    # -- helpers ----------------------------------------------------------
    def _generate_unique_username(self, db: Session, patient_id: int) -> str:
        """patient_{id}_{hex6} — practically collision-free, still checked
        against UNIQUE(users.username) with bounded regeneration."""
        base = f"patient_{patient_id}"
        for _ in range(5):
            candidate = f"{base}_{secrets.token_hex(3)}"
            exists = db.execute(
                select(User.id).where(User.username == candidate)
            ).scalar_one_or_none()
            if exists is None:
                return candidate
        # CodeQL 1314 fix: no interpolated identifiers in the log.
        logger.error("username generation exhausted after 5 attempts")
        raise ActivationError(503, ERR_ACTIVATION_GENERIC)


# Module-level singleton (mirrors patient_otp_service convention)
patient_activation_service = PatientActivationService()


def get_patient_activation_service() -> PatientActivationService:
    return patient_activation_service
