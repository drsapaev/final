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
    patact:idx:{patient_id}       -> sha256(token) (revocation) TTL 72h
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


@dataclass
class ActivationError(Exception):
    status_code: int
    detail: str


def mask_phone(phone: str) -> str:
    """+998901112233 -> +99890***2233 (staff-facing; never full number)."""
    if not phone or len(phone) < 10:
        return "***"
    return f"{phone[:6]}***{phone[-4:]}"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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

        backend = get_patient_otp_service().get_backend()
        token = secrets.token_urlsafe(32)
        t_hash = _token_hash(token)

        # Reissue revokes any outstanding token for this patient.
        old_hash = backend.get(f"{_PATIENT_IDX_NS}:{patient.id}")
        if old_hash:
            backend.delete(f"{_TOKEN_NS}:{old_hash}")

        entry = json.dumps({"patient_id": patient.id, "phone": normalized})
        backend.set(f"{_TOKEN_NS}:{t_hash}", entry, ACTIVATION_TOKEN_TTL_SECONDS)
        backend.set(
            f"{_PATIENT_IDX_NS}:{patient.id}", t_hash, ACTIVATION_TOKEN_TTL_SECONDS
        )

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
        raw = (
            get_patient_otp_service()
            .get_backend()
            .get(f"{_TOKEN_NS}:{_token_hash(token)}")
        )
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
            return entry
        except Exception:  # noqa: BLE001 - corrupt entry -> invalid token
            return None

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

        Order: token lookup -> OTP verify (single-use) -> locked patient
        revalidation -> staged User+UserProfile+link -> ONE commit ->
        token consumed. Every failure is generic (anti-enum)."""
        entry = self._lookup_entry(token)
        if entry is None:
            raise ActivationError(400, ERR_TOKEN_INVALID)

        otp_service = get_patient_otp_service()
        try:
            otp_service.verify_activation_otp(entry["phone"], code)
        except PatientOtpError as err:
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

        # Owner correction #4: normal hash of a random unknown secret.
        user = User(
            username=username,
            full_name=patient.short_name(),
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            role=Roles.PATIENT,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()  # staged: user.id available, NOT committed (correction #3)

        profile = UserProfile(
            user_id=user.id,
            full_name=patient.short_name()[:100],
            first_name=(patient.first_name or "")[:50] or None,
            last_name=(patient.last_name or "")[:50] or None,
            phone=entry["phone"],
            phone_verified=True,
        )
        db.add(profile)
        db.flush()

        patient.user_id = user.id  # UNIQUE(patients.user_id) = race backstop
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            logger.warning(
                "activation commit conflict: patient_id=%s (%s)",
                entry["patient_id"],
                exc.orig,
            )
            raise ActivationError(409, ERR_ACTIVATION_GENERIC) from exc
        db.refresh(patient)
        db.refresh(user)

        # Token is single-use: consumed ONLY after a successful commit.
        backend = otp_service.get_backend()
        backend.getdel(f"{_TOKEN_NS}:{_token_hash(token)}")
        backend.delete(f"{_PATIENT_IDX_NS}:{entry['patient_id']}")

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
        logger.error("username generation exhausted for patient_id=%s", patient_id)
        raise ActivationError(503, ERR_ACTIVATION_GENERIC)


# Module-level singleton (mirrors patient_otp_service convention)
patient_activation_service = PatientActivationService()


def get_patient_activation_service() -> PatientActivationService:
    return patient_activation_service
