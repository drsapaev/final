"""Telegram Mini App initData validation helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qsl

from sqlalchemy.orm import Session

from app.crud import telegram_config as crud_telegram
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.user import User


DEFAULT_MAX_AUTH_AGE_SECONDS = 24 * 60 * 60
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 60
_HASH_FIELD = "hash"
_AUTH_DATE_FIELD = "auth_date"
_VALID_MINI_APP_SCOPES = {"patient", "staff"}
_STAFF_MINI_APP_SUPPORTED_ROLES = frozenset(
    {"admin", "owner", "doctor", "cashier", "lab", "registrar"}
)
_STAFF_ROLE_ALIASES = {
    "administrator": "admin",
    "super_admin": "admin",
    "superadmin": "admin",
    "admin": "admin",
    "owner": "owner",
    "doctor": "doctor",
    "cashier": "cashier",
    "lab": "lab",
    "lab_tech": "lab",
    "laboratory": "lab",
    "registrar": "registrar",
    "receptionist": "registrar",
}

TelegramMiniAppScopeType = Literal["patient", "staff"]


class TelegramMiniAppInitDataError(ValueError):
    """Raised when Telegram Mini App initData cannot be trusted."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TelegramMiniAppInitData:
    """Validated Telegram Mini App initData without the untrusted hash field."""

    fields: dict[str, str]
    auth_date: datetime
    age_seconds: int
    user: dict[str, Any] | None = None


class TelegramMiniAppSessionScopeError(ValueError):
    """Raised when validated Mini App initData has no trusted application scope."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TelegramMiniAppSessionScope:
    """Application identity scope bound to an existing Telegram account link."""

    scope_type: TelegramMiniAppScopeType
    telegram_user_id: int
    telegram_chat_id: int
    patient_id: int | None = None
    staff_user_id: int | None = None
    staff_role: str | None = None


@dataclass(frozen=True)
class TelegramMiniAppAppointmentBookingDraft:
    """Safe appointment booking payload prepared from a patient Mini App scope."""

    patient_id: int
    appointment_date: date
    appointment_time: str | None = None
    doctor_id: int | None = None
    department: str | None = None
    notes: str | None = None
    services: tuple[str, ...] = ()
    status: str = "scheduled"
    visit_type: str = "paid"
    payment_type: str = "cash"
    payment_currency: str = "UZS"

    def to_appointment_create_payload(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "department": self.department,
            "appointment_date": self.appointment_date,
            "appointment_time": self.appointment_time,
            "notes": self.notes,
            "status": self.status,
            "visit_type": self.visit_type,
            "payment_type": self.payment_type,
            "services": list(self.services),
            "payment_amount": None,
            "payment_currency": self.payment_currency,
            "payment_provider": None,
            "payment_transaction_id": None,
            "payment_webhook_id": None,
            "payment_processed_at": None,
        }


@dataclass(frozen=True)
class TelegramMiniAppAppointmentBookingPreview:
    """Preview-only booking response prepared before any appointment mutation."""

    scope: TelegramMiniAppSessionScope
    draft: TelegramMiniAppAppointmentBookingDraft
    preview_only: bool = True
    mutation_allowed: bool = False
    message_key: str = "telegram_mini_app_booking_preview_ready"

    def to_response_payload(self) -> dict[str, Any]:
        return {
            "preview_only": self.preview_only,
            "mutation_allowed": self.mutation_allowed,
            "message_key": self.message_key,
            "scope": {
                "type": self.scope.scope_type,
                "patient_id": self.draft.patient_id,
            },
            "appointment": self.draft.to_appointment_create_payload(),
        }


@dataclass(frozen=True)
class TelegramMiniAppPatientFormField:
    """Safe patient-facing Mini App form field metadata."""

    key: str
    label: str
    field_type: str
    required: bool = False
    max_length: int | None = None
    options: tuple[str, ...] = ()

    def to_response_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "type": self.field_type,
            "required": self.required,
        }
        if self.max_length is not None:
            payload["max_length"] = self.max_length
        if self.options:
            payload["options"] = list(self.options)
        return payload


@dataclass(frozen=True)
class TelegramMiniAppPatientFormDefinition:
    """Safe patient-facing Mini App form definition."""

    form_id: str
    title: str
    description: str
    fields: tuple[TelegramMiniAppPatientFormField, ...]

    def to_response_payload(self) -> dict[str, Any]:
        return {
            "id": self.form_id,
            "title": self.title,
            "description": self.description,
            "fields": [field.to_response_payload() for field in self.fields],
        }


@dataclass(frozen=True)
class TelegramMiniAppPatientFormsPreview:
    """Preview-only patient forms response prepared before any form mutation."""

    scope: TelegramMiniAppSessionScope
    forms: tuple[TelegramMiniAppPatientFormDefinition, ...]
    preview_only: bool = True
    mutation_allowed: bool = False
    message_key: str = "telegram_mini_app_patient_forms_preview_ready"

    def to_response_payload(self) -> dict[str, Any]:
        return {
            "preview_only": self.preview_only,
            "mutation_allowed": self.mutation_allowed,
            "message_key": self.message_key,
            "scope": {
                "type": self.scope.scope_type,
                "patient_id": self.scope.patient_id,
            },
            "forms": [form.to_response_payload() for form in self.forms],
            "policy": {
                "plain_telegram_chat_allowed": False,
                "medical_details_in_chat": False,
                "storage_enabled": False,
            },
        }


TELEGRAM_MINI_APP_PATIENT_FORMS: tuple[TelegramMiniAppPatientFormDefinition, ...] = (
    TelegramMiniAppPatientFormDefinition(
        form_id="patient_intake",
        title="Patient intake",
        description="Basic pre-visit details for protected clinic intake.",
        fields=(
            TelegramMiniAppPatientFormField(
                key="chief_complaint",
                label="Reason for visit",
                field_type="textarea",
                max_length=1000,
            ),
            TelegramMiniAppPatientFormField(
                key="allergies",
                label="Allergies",
                field_type="textarea",
                max_length=1000,
            ),
            TelegramMiniAppPatientFormField(
                key="current_medications",
                label="Current medications",
                field_type="textarea",
                max_length=1000,
            ),
            TelegramMiniAppPatientFormField(
                key="medical_history",
                label="Important medical history",
                field_type="textarea",
                max_length=1500,
            ),
            TelegramMiniAppPatientFormField(
                key="consent_to_contact",
                label="Allow clinic follow-up",
                field_type="boolean",
            ),
        ),
    ),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_init_data(init_data: str) -> dict[str, str]:
    pairs = parse_qsl(str(init_data or ""), keep_blank_values=True, strict_parsing=False)
    fields: dict[str, str] = {}
    for key, value in pairs:
        key_text = str(key)
        if key_text in fields:
            raise TelegramMiniAppInitDataError("duplicate_field")
        fields[key_text] = str(value)
    return fields


def _data_check_string(fields: dict[str, str]) -> str:
    return "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items()) if key != _HASH_FIELD
    )


def _expected_hash(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _parse_auth_date(value: str) -> datetime:
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as exc:
        raise TelegramMiniAppInitDataError("invalid_auth_date") from exc
    return datetime.fromtimestamp(timestamp, timezone.utc)


def _parse_user(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise TelegramMiniAppInitDataError("invalid_user_json") from exc
    if not isinstance(parsed, dict):
        raise TelegramMiniAppInitDataError("invalid_user_json")
    return parsed


def _trim_optional_text(
    value: str | None,
    *,
    max_length: int,
    reason: str,
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        raise TelegramMiniAppSessionScopeError(reason)
    return text


def _normalize_services(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not values:
        return ()
    services: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            raise TelegramMiniAppSessionScopeError("appointment_service_invalid")
        if len(text) > 128:
            raise TelegramMiniAppSessionScopeError("appointment_service_too_long")
        services.append(text)
    return tuple(services)


def _normalize_appointment_time(value: str | None) -> str | None:
    text = _trim_optional_text(
        value,
        max_length=8,
        reason="appointment_time_invalid",
    )
    if text is None:
        return None
    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError as exc:
        raise TelegramMiniAppSessionScopeError("appointment_time_invalid") from exc
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def _normalize_staff_role(role: Any) -> str:
    role_key = str(role or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _STAFF_ROLE_ALIASES.get(role_key, role_key)


def _telegram_account_id(init_data: TelegramMiniAppInitData) -> int:
    user = init_data.user
    if not isinstance(user, dict):
        raise TelegramMiniAppSessionScopeError("telegram_user_required")
    try:
        account_id = int(user.get("id"))
    except (TypeError, ValueError) as exc:
        raise TelegramMiniAppSessionScopeError("telegram_user_id_required") from exc
    if account_id <= 0:
        raise TelegramMiniAppSessionScopeError("telegram_user_id_required")
    return account_id


def _base_scope(
    telegram_user: TelegramUser,
    scope_type: TelegramMiniAppScopeType,
    *,
    patient_id: int | None = None,
    staff_user_id: int | None = None,
    staff_role: str | None = None,
) -> TelegramMiniAppSessionScope:
    return TelegramMiniAppSessionScope(
        scope_type=scope_type,
        telegram_user_id=int(telegram_user.id),
        telegram_chat_id=int(telegram_user.chat_id),
        patient_id=patient_id,
        staff_user_id=staff_user_id,
        staff_role=staff_role,
    )


def _patient_scope(
    db: Session, telegram_user: TelegramUser
) -> TelegramMiniAppSessionScope | None:
    patient_id = getattr(telegram_user, "patient_id", None)
    if not patient_id:
        return None

    patient = db.query(Patient).filter(Patient.id == int(patient_id)).first()
    if not patient or getattr(patient, "is_deleted", False):
        raise TelegramMiniAppSessionScopeError("patient_link_invalid")

    return _base_scope(
        telegram_user,
        "patient",
        patient_id=int(patient.id),
    )


def _staff_scope(
    db: Session, telegram_user: TelegramUser
) -> TelegramMiniAppSessionScope | None:
    staff_user_id = getattr(telegram_user, "user_id", None)
    if not staff_user_id:
        return None

    staff_user = db.query(User).filter(User.id == int(staff_user_id)).first()
    if not staff_user or not getattr(staff_user, "is_active", False):
        raise TelegramMiniAppSessionScopeError("staff_link_inactive")

    staff_role = _normalize_staff_role(getattr(staff_user, "role", None))
    if staff_role not in _STAFF_MINI_APP_SUPPORTED_ROLES:
        raise TelegramMiniAppSessionScopeError("staff_role_not_allowed")

    return _base_scope(
        telegram_user,
        "staff",
        staff_user_id=int(staff_user.id),
        staff_role=staff_role,
    )


def validate_telegram_mini_app_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int = DEFAULT_MAX_AUTH_AGE_SECONDS,
    max_future_skew_seconds: int = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
    now: datetime | None = None,
) -> TelegramMiniAppInitData:
    """Validate Telegram Mini App initData before trusting Mini App identity."""

    token = str(bot_token or "").strip()
    if not token:
        raise TelegramMiniAppInitDataError("bot_token_required")

    fields = _parse_init_data(init_data)
    received_hash = fields.get(_HASH_FIELD)
    if not received_hash:
        raise TelegramMiniAppInitDataError("hash_required")
    if _AUTH_DATE_FIELD not in fields:
        raise TelegramMiniAppInitDataError("auth_date_required")

    data_check_string = _data_check_string(fields)
    expected_hash = _expected_hash(data_check_string, token)
    if not hmac.compare_digest(received_hash, expected_hash):
        raise TelegramMiniAppInitDataError("hash_mismatch")

    checked_at = now or _utc_now()
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    else:
        checked_at = checked_at.astimezone(timezone.utc)

    auth_date = _parse_auth_date(fields[_AUTH_DATE_FIELD])
    age_seconds = int((checked_at - auth_date).total_seconds())
    if age_seconds > int(max_age_seconds):
        raise TelegramMiniAppInitDataError("auth_date_expired")
    if age_seconds < -int(max_future_skew_seconds):
        raise TelegramMiniAppInitDataError("auth_date_in_future")

    trusted_fields = {key: value for key, value in fields.items() if key != _HASH_FIELD}
    return TelegramMiniAppInitData(
        fields=trusted_fields,
        auth_date=auth_date,
        age_seconds=age_seconds,
        user=_parse_user(trusted_fields.get("user")),
    )


def resolve_telegram_mini_app_session_scope(
    db: Session,
    init_data: TelegramMiniAppInitData,
    *,
    expected_scope: TelegramMiniAppScopeType | None = None,
) -> TelegramMiniAppSessionScope:
    """Resolve validated Mini App identity to a linked patient or staff account."""

    if expected_scope is not None and expected_scope not in _VALID_MINI_APP_SCOPES:
        raise TelegramMiniAppSessionScopeError("invalid_expected_scope")

    telegram_account_id = _telegram_account_id(init_data)
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(
        db,
        telegram_account_id,
    )
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")

    if expected_scope == "patient":
        scope = _patient_scope(db, telegram_user)
        if not scope:
            raise TelegramMiniAppSessionScopeError("patient_scope_required")
        return scope

    if expected_scope == "staff":
        scope = _staff_scope(db, telegram_user)
        if not scope:
            raise TelegramMiniAppSessionScopeError("staff_scope_required")
        return scope

    patient_scope = _patient_scope(db, telegram_user)
    staff_scope = _staff_scope(db, telegram_user)
    if patient_scope and staff_scope:
        raise TelegramMiniAppSessionScopeError("ambiguous_scope")
    if patient_scope:
        return patient_scope
    if staff_scope:
        return staff_scope

    raise TelegramMiniAppSessionScopeError("linked_identity_required")


def require_telegram_mini_app_patient_scope(
    scope: TelegramMiniAppSessionScope,
    *,
    patient_id: int,
) -> TelegramMiniAppSessionScope:
    """Require that a Mini App scope belongs to one concrete linked patient."""

    if scope.scope_type != "patient" or scope.patient_id is None:
        raise TelegramMiniAppSessionScopeError("patient_scope_required")
    if int(scope.patient_id) != int(patient_id):
        raise TelegramMiniAppSessionScopeError("patient_scope_mismatch")
    return scope


def require_telegram_mini_app_staff_scope(
    scope: TelegramMiniAppSessionScope,
    *,
    allowed_roles: set[str] | frozenset[str] | None = None,
) -> TelegramMiniAppSessionScope:
    """Require that a Mini App scope belongs to an authenticated staff user."""

    if scope.scope_type != "staff" or scope.staff_user_id is None:
        raise TelegramMiniAppSessionScopeError("staff_scope_required")

    if allowed_roles:
        normalized_roles = {_normalize_staff_role(role) for role in allowed_roles}
        if scope.staff_role not in normalized_roles:
            raise TelegramMiniAppSessionScopeError("staff_role_denied")
    return scope


def build_telegram_mini_app_appointment_booking_draft(
    scope: TelegramMiniAppSessionScope,
    *,
    appointment_date: date,
    appointment_time: str | None = None,
    doctor_id: int | None = None,
    department: str | None = None,
    notes: str | None = None,
    services: list[str] | tuple[str, ...] | None = None,
    patient_id: int | None = None,
    today: date | None = None,
) -> TelegramMiniAppAppointmentBookingDraft:
    """Prepare a non-mutating appointment booking draft for a linked patient."""

    if scope.patient_id is None:
        raise TelegramMiniAppSessionScopeError("patient_scope_required")
    if patient_id is not None:
        require_telegram_mini_app_patient_scope(scope, patient_id=patient_id)
    elif scope.scope_type != "patient":
        raise TelegramMiniAppSessionScopeError("patient_scope_required")

    if not isinstance(appointment_date, date) or isinstance(appointment_date, datetime):
        raise TelegramMiniAppSessionScopeError("appointment_date_invalid")
    current_day = today or date.today()
    if appointment_date < current_day:
        raise TelegramMiniAppSessionScopeError("appointment_date_in_past")

    normalized_doctor_id = None
    if doctor_id is not None:
        try:
            normalized_doctor_id = int(doctor_id)
        except (TypeError, ValueError) as exc:
            raise TelegramMiniAppSessionScopeError("doctor_id_invalid") from exc
        if normalized_doctor_id <= 0:
            raise TelegramMiniAppSessionScopeError("doctor_id_invalid")

    return TelegramMiniAppAppointmentBookingDraft(
        patient_id=int(scope.patient_id),
        appointment_date=appointment_date,
        appointment_time=_normalize_appointment_time(appointment_time),
        doctor_id=normalized_doctor_id,
        department=_trim_optional_text(
            department,
            max_length=64,
            reason="department_too_long",
        ),
        notes=_trim_optional_text(
            notes,
            max_length=1000,
            reason="notes_too_long",
        ),
        services=_normalize_services(services),
    )


def build_telegram_mini_app_appointment_booking_preview(
    scope: TelegramMiniAppSessionScope,
    *,
    appointment_date: date,
    appointment_time: str | None = None,
    doctor_id: int | None = None,
    department: str | None = None,
    notes: str | None = None,
    services: list[str] | tuple[str, ...] | None = None,
    patient_id: int | None = None,
    today: date | None = None,
) -> TelegramMiniAppAppointmentBookingPreview:
    """Prepare a Mini App booking preview without creating an appointment."""

    draft = build_telegram_mini_app_appointment_booking_draft(
        scope,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        doctor_id=doctor_id,
        department=department,
        notes=notes,
        services=services,
        patient_id=patient_id,
        today=today,
    )
    return TelegramMiniAppAppointmentBookingPreview(
        scope=scope,
        draft=draft,
    )


def build_telegram_mini_app_patient_forms_preview(
    scope: TelegramMiniAppSessionScope,
    *,
    patient_id: int | None = None,
) -> TelegramMiniAppPatientFormsPreview:
    """Prepare protected patient forms metadata without storing submitted data."""

    if scope.patient_id is None:
        raise TelegramMiniAppSessionScopeError("patient_scope_required")
    if patient_id is not None:
        require_telegram_mini_app_patient_scope(scope, patient_id=patient_id)
    elif scope.scope_type != "patient":
        raise TelegramMiniAppSessionScopeError("patient_scope_required")

    return TelegramMiniAppPatientFormsPreview(
        scope=scope,
        forms=TELEGRAM_MINI_APP_PATIENT_FORMS,
    )
