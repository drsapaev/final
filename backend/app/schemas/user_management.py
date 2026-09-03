"""
Pydantic схемы для управления пользователями
"""

import logging
import os
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Union

from email_validator import EmailNotValidError
from email_validator import validate_email as validate_email_address
from typing_extensions import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.config import ConfigDict

from app.core.roles import DOCTOR_ROLE_SPELLINGS

logger = logging.getLogger(__name__)


class UserStatus(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Статусы пользователя"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    LOCKED = "locked"


class Gender(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Пол пользователя"""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Theme(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Темы интерфейса"""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    SYSTEM = "system"
    VIBRANT = "vibrant"
    GLASS = "glass"
    GRADIENT = "gradient"


class TimeFormat(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Форматы времени"""

    HOUR_12 = "12"
    HOUR_24 = "24"


_RESERVED_EMAIL_DOMAIN_SUFFIXES = (".local", ".test", ".invalid", ".example")
_RESERVED_EMAIL_DOMAINS = {
    "arpa",
    "example",
    "example.com",
    "example.net",
    "example.org",
    "invalid",
    "localhost.localdomain",
    "onion",
    "test",
}


def _allow_reserved_email_domains() -> bool:
    env = os.getenv("ENV", "dev").lower()
    testing = os.getenv("TESTING", "0").lower() in ("1", "true", "yes")
    return testing or env not in ("prod", "production")


def _is_reserved_email_domain(domain: str) -> bool:
    domain = domain.strip().lower()
    return domain in _RESERVED_EMAIL_DOMAINS or any(
        domain.endswith(suffix) for suffix in _RESERVED_EMAIL_DOMAIN_SUFFIXES
    )


def _normalize_user_management_email(value: str, *, allow_reserved: bool) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Email обязателен")

    try:
        validated = validate_email_address(
            normalized,
            check_deliverability=False,
            test_environment=True,
            globally_deliverable=False,
        )
        return validated.email
    except EmailNotValidError as exc:
        message = str(exc)
        domain = normalized.rsplit("@", 1)[-1] if "@" in normalized else ""
        if (
            allow_reserved
            and "special-use or reserved name" in message
            and _is_reserved_email_domain(domain)
        ):
            logger.info(
                "[FIX:ADM-03] Allowing reserved email domain in admin user flow: %s",
                normalized,
            )
            return normalized
        raise ValueError("Некорректный email") from exc


# Схемы для профиля пользователя


class UserProfileBase(BaseModel):
    """Базовая схема профиля пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    full_name: str | None = Field(None, min_length=1, max_length=100)
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    middle_name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, min_length=10, max_length=20)
    date_of_birth: datetime | None = None
    gender: Gender | None = None
    nationality: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=10)
    timezone: str | None = Field(None, max_length=50)
    bio: str | None = Field(None, max_length=1000)
    website: str | None = Field(None, max_length=200)


class UserProfileCreate(UserProfileBase):
    """Схема создания профиля пользователя"""

    user_id: int


class UserProfileUpdate(UserProfileBase):
    """Схема обновления профиля пользователя"""

    pass


class UserProfileResponse(UserProfileBase):
    """Схема ответа профиля пользователя"""

    model_config = ConfigDict(protected_namespaces=(), extra='ignore')
    id: int
    user_id: int
    phone_verified: bool
    email_verified: bool
    alternative_email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    job_title: str | None = None
    department: str | None = None
    employee_id: str | None = None
    hire_date: datetime | None = None
    avatar_url: str | None = None
    social_links: dict[str, str] | None = None
    status: UserStatus
    last_login: datetime | None = None
    last_activity: datetime | None = None
    login_count: int
    failed_login_attempts: int
    locked_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


# Схемы для настроек пользователя


class UserPreferencesBase(BaseModel):
    """Базовая схема настроек пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    theme: Theme | None = Theme.AUTO
    language: str | None = Field(None, max_length=10)
    timezone: str | None = Field(None, max_length=50)
    date_format: str | None = Field(None, max_length=20)
    time_format: TimeFormat | None = TimeFormat.HOUR_24
    email_notifications: bool | None = True
    sms_notifications: bool | None = False
    push_notifications: bool | None = True
    desktop_notifications: bool | None = True
    security_settings: dict[str, Any] | None = None


class UserPreferencesCreate(UserPreferencesBase):
    """Схема создания настроек пользователя"""

    user_id: int
    profile_id: int


class UserPreferencesUpdate(UserPreferencesBase):
    """Схема обновления настроек пользователя"""

    working_hours_start: str | None = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    working_hours_end: str | None = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    working_days: list[int] | None = Field(None, min_length=1, max_length=7)
    break_duration: int | None = Field(None, ge=0, le=480)  # 0-8 часов
    dashboard_layout: dict[str, Any] | None = None
    sidebar_collapsed: bool | None = False
    compact_mode: bool | None = False
    show_tooltips: bool | None = True
    session_timeout: int | None = Field(None, ge=5, le=480)  # 5 минут - 8 часов
    require_2fa: bool | None = False
    auto_logout: bool | None = True

    # ============================================
    # EMR PREFERENCES (Smart Autocomplete)
    # ============================================
    # Режим умного поля (ghost | mvp | hybrid | word)
    emr_smart_field_mode: str | None = Field(None, pattern=r"^(ghost|mvp|hybrid|word)$")
    # Показывать переключатель режимов
    emr_show_mode_switcher: bool | None = None
    # Задержка debounce в мс
    emr_debounce_ms: int | None = Field(None, ge=100, le=2000)
    # Недавно использованные коды МКБ-10
    emr_recent_icd10: list[str] | None = Field(None, max_length=20)
    # Недавно использованные шаблоны назначений
    emr_recent_templates: list[str] | None = Field(None, max_length=20)
    # Избранные шаблоны по специальностям
    emr_favorite_templates: dict[str, list[str]] | None = None
    # Кастомные шаблоны пользователя
    emr_custom_templates: list[dict[str, Any]] | None = None


class UserPreferencesResponse(UserPreferencesBase):
    """Схема ответа настроек пользователя"""

    model_config = ConfigDict(protected_namespaces=(), extra='ignore')
    id: int
    user_id: int
    profile_id: int
    working_hours_start: str
    working_hours_end: str
    working_days: list[int]
    break_duration: int
    dashboard_layout: dict[str, Any] | None = None
    sidebar_collapsed: bool
    compact_mode: bool
    show_tooltips: bool
    session_timeout: int
    require_2fa: bool
    auto_logout: bool

    # EMR Preferences
    emr_smart_field_mode: str | None = "ghost"
    emr_show_mode_switcher: bool | None = True
    emr_debounce_ms: int | None = 500
    emr_recent_icd10: list[str] | None = None
    emr_recent_templates: list[str] | None = None
    emr_favorite_templates: dict[str, list[str]] | None = None
    emr_custom_templates: list[dict[str, Any]] | None = None

    created_at: datetime
    updated_at: datetime


# Схемы для настроек уведомлений


class UserNotificationSettingsBase(BaseModel):
    """Базовая схема настроек уведомлений"""

    model_config = ConfigDict(protected_namespaces=())

    email_appointment_reminder: bool | None = True
    email_appointment_cancellation: bool | None = True
    email_appointment_confirmation: bool | None = True
    email_payment_receipt: bool | None = True
    email_payment_reminder: bool | None = True
    email_system_updates: bool | None = True
    email_security_alerts: bool | None = True
    email_newsletter: bool | None = False
    sms_appointment_reminder: bool | None = False
    sms_appointment_cancellation: bool | None = False
    sms_appointment_confirmation: bool | None = False
    sms_payment_receipt: bool | None = False
    sms_emergency: bool | None = True
    push_appointment_reminder: bool | None = True
    push_appointment_cancellation: bool | None = True
    push_appointment_confirmation: bool | None = True
    push_payment_receipt: bool | None = True
    push_system_updates: bool | None = True
    push_security_alerts: bool | None = True


class UserNotificationSettingsCreate(UserNotificationSettingsBase):
    """Схема создания настроек уведомлений"""

    user_id: int
    profile_id: int


class UserNotificationSettingsUpdate(UserNotificationSettingsBase):
    """Схема обновления настроек уведомлений"""

    reminder_time_before: int | None = Field(
        None, ge=5, le=10080
    )  # 5 минут - 7 дней
    quiet_hours_start: str | None = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    quiet_hours_end: str | None = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    weekend_notifications: bool | None = False


class UserNotificationSettingsResponse(UserNotificationSettingsBase):
    """Схема ответа настроек уведомлений"""

    model_config = ConfigDict(protected_namespaces=(), extra='ignore')
    id: int
    user_id: int
    profile_id: int
    reminder_time_before: int
    quiet_hours_start: str
    quiet_hours_end: str
    weekend_notifications: bool
    created_at: datetime
    updated_at: datetime


# Схемы для ролей и разрешений


class UserRoleBase(BaseModel):
    """Базовая схема роли пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    permissions: list[str] | None = None


class UserRoleCreate(UserRoleBase):
    """Схема создания роли пользователя"""

    is_system: bool | None = False
    is_active: bool | None = True


class UserRoleUpdate(BaseModel):
    """Схема обновления роли пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    permissions: list[str] | None = None
    is_active: bool | None = None


class UserRoleResponse(UserRoleBase):
    """Схема ответа роли пользователя"""

    id: int
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserPermissionBase(BaseModel):
    """Базовая схема разрешения пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=50)


class UserPermissionCreate(UserPermissionBase):
    """Схема создания разрешения пользователя"""

    is_system: bool | None = False
    is_active: bool | None = True


class UserPermissionResponse(UserPermissionBase):
    """Схема ответа разрешения пользователя"""

    id: int
    is_system: bool
    is_active: bool
    created_at: datetime


# Схемы для групп пользователей


class UserGroupBase(BaseModel):
    """Базовая схема группы пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)


class UserGroupCreate(UserGroupBase):
    """Схема создания группы пользователей"""

    is_active: bool | None = True
    is_system: bool | None = False


class UserGroupUpdate(BaseModel):
    """Схема обновления группы пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    display_name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class UserGroupResponse(UserGroupBase):
    """Схема ответа группы пользователей"""

    id: int
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime


class UserGroupMemberBase(BaseModel):
    """Базовая схема участника группы"""

    model_config = ConfigDict(protected_namespaces=())

    user_id: int
    group_id: int
    role: str = Field(..., pattern="^(member|admin|moderator)$")


class UserGroupMemberCreate(UserGroupMemberBase):
    """Схема создания участника группы"""

    pass


class UserGroupMemberResponse(UserGroupMemberBase):
    """Схема ответа участника группы"""

    id: int
    joined_at: datetime


# Схемы для аудита


class UserAuditLogBase(BaseModel):
    """Базовая схема аудита пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    action: str = Field(..., min_length=1, max_length=50)
    resource_type: str | None = Field(None, max_length=50)
    resource_id: int | None = None
    description: str | None = Field(None, max_length=1000)
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None


class UserAuditLogCreate(UserAuditLogBase):
    """Схема создания аудита пользователя"""

    user_id: int
    ip_address: str | None = None
    user_agent: str | None = None
    session_id: str | None = None


class UserAuditLogResponse(UserAuditLogBase):
    """Схема ответа аудита пользователя"""

    id: int
    user_id: int
    ip_address: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    created_at: datetime


# Схемы для управления пользователями

# Single shared role vocabulary for UserCreateRequest AND UserUpdateRequest
# (D-3 RBAC unification): the two patterns used to drift — creation accepted
# the legacy doctor spellings (cardio/derma/dentist) while updates forbade
# them, so a legacy spelling could never be (re)assigned after creation.
# The doctor-lifecycle mapping (user_mgmt DOCTOR_ROLE_DEFAULT_SPECIALTY)
# normalizes whatever spelling arrives.
# Codex round-1 P2: the doctor-family part is DERIVED from the IAM SSOT
# (core/roles.DOCTOR_ROLE_SPELLINGS) instead of a smaller hardcoded subset —
# cardiology/cardiologist/dermatology/dermatologist/dentistry are authorized
# spellings as well, and the admin modal re-submits a stored user's role
# verbatim, so an omitted spelling turns "edit account" into a 422.
# sorted() keeps the generated OpenAPI contract deterministic.
# REC-1 (Receptionist deprecation): 'Receptionist' removed from the canonical
# write vocabulary — Registrar is the canonical front-desk role and no
# Receptionist rows exist in production (SQL evidence 2026-09-02). The
# backend READ alias (receptionist -> registrar in core/security.require_roles)
# stays during the compatibility window; only NEW stored 'Receptionist'
# writes are frozen. Update-re-submission safety: 0 stored users carry the
# spelling, so no edit flow can re-submit it.
# Codex re-review P2 (PR #3025): the WRITE vocabulary is deliberately
# separate from the READ/FILTER vocabulary below — the search/filter
# surfaces must keep accepting the deprecated spelling so a compatible
# deployment holding legacy rows can still query them (legacy reads
# temporarily accepted; canonical writes only).
_USER_MANAGEMENT_ROLE_PATTERN = (
    "^(Admin|Registrar|Doctor|Nurse|Cashier|Lab|Patient|"
    "SuperAdmin|Manager|"
    + "|".join(sorted(DOCTOR_ROLE_SPELLINGS))
    + ")$"
)

# Roles accepted by POST /users WITHOUT a doctor_profile. Exact complement
# of the canonical "Doctor" variant below — DOCTOR_ROLE_SPELLINGS carries
# every legacy lowercase spelling (including the bare "doctor"), which all
# keep the compatibility auto-map and are NOT canonical onboarding.
# REC-1 (Receptionist deprecation): 'Receptionist' is deliberately ABSENT
# here — the write freeze is absolute; it remains queryable via the filter
# pattern below only.
_NON_DOCTOR_ROLE_VALUES: tuple[str, ...] = (
    "Admin",
    "Registrar",
    "Nurse",
    "Cashier",
    "Lab",
    "Patient",
    "SuperAdmin",
    "Manager",
) + tuple(sorted(DOCTOR_ROLE_SPELLINGS))

# Read/filter vocabulary: canonical write vocabulary PLUS the deprecated
# 'Receptionist' spelling — used ONLY by query/filter surfaces
# (UserSearchRequest.role, GET /users role parameter) so legacy rows in
# compatible deployments remain queryable during the compatibility window.
# NOT used by create/update/bulk-change-role (write freeze stays absolute).
_USER_MANAGEMENT_ROLE_FILTER_PATTERN = (
    _USER_MANAGEMENT_ROLE_PATTERN[:-2] + "|Receptionist)$"
)


NonDoctorRoleLiteral = Literal.__getitem__(_NON_DOCTOR_ROLE_VALUES)

# Codex round-10 P2: Decimal JSON schema publishes a number|string anyOf.
# `multipleOf` (from json_schema_extra) and `maximum` (from le) only bind
# the NUMBER branch; the STRING branch used the default permissive pattern
# and advertised values ("1.234", "999999999.99") that Pydantic then
# rejected with 422 — a schema-valid request could still fail. This hook
# pins the string branch to the Numeric(10, 2) column precision: at most 8
# integer digits, at most 2 fractional digits, no sign other than a
# leading "+". Every string matching it converts to a Decimal that passes
# ge=0 / le=99999999.99 / the two-decimal scale validator.
_PRICE_STRING_PATTERN = r"^[+]?[0-9]{1,8}(\.[0-9]{1,2})?$"


def _pin_price_string_branch(schema: dict) -> None:
    # Round-8 contract: publish the two-decimal scale for client-side
    # pre-validation (asserted by test_openapi_contract.py).
    schema.setdefault("multipleOf", 0.01)
    for sub in schema.get("anyOf", []):
        if isinstance(sub, dict) and sub.get("type") == "string":
            sub["pattern"] = _PRICE_STRING_PATTERN


class DoctorProfileCreate(BaseModel):
    """Doctor profile block for canonical new-doctor onboarding (POST /users).

    Only accepted for role="Doctor" (canonical onboarding); legacy
    doctor-role spellings keep their compatibility auto-map and must not
    send this block. ``specialty`` must be a canonical onboarding id —
    the incomplete sentinel ("general"), legacy dental spellings and any
    free-text value are rejected.
    """

    model_config = ConfigDict(protected_namespaces=())

    specialty: str = Field(..., min_length=1, max_length=100)
    cabinet: str | None = Field(None, max_length=20)
    # Codex round-6 P2: doctors.price_default is Numeric(10, 2) — bound the
    # schema to the column precision so an oversized value surfaces as a
    # field-level 422 instead of a driver overflow rolling back the whole
    # User+Doctor onboarding transaction.
    # Codex round-8 P2: publish both bound AND scale in the JSON schema —
    # maximum (from le) plus multipleOf 0.01 documents the two-decimal
    # scale enforced by validate_price_precision, so contract-generated
    # clients can pre-validate payloads without a 422 round-trip.
    # Codex round-10 P2: `multipleOf` is ignored for string instances and
    # `maximum` lands only on the number branch, so the published string
    # pattern still accepted values ("1.234", "999999999.99") that Pydantic
    # then rejected with 422. The string branch below is pinned to the
    # Numeric(10, 2) precision: at most 8 integer digits and 2 fractional
    # digits, so every schema-valid payload survives the range/scale check.
    price_default: Decimal | None = Field(
        None,
        ge=0,
        le=Decimal("99999999.99"),
        json_schema_extra=_pin_price_string_branch,
    )
    start_number_online: int | None = Field(None, ge=1, le=100)
    max_online_per_day: int | None = Field(None, ge=1, le=100)

    @field_validator("price_default")
    @classmethod
    def validate_price_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and -v.as_tuple().exponent > 2:
            raise ValueError(
                "Цена может содержать не более двух знаков после запятой"
            )
        return v


class _UserCreateCommon(BaseModel):
    """Shared fields of the POST /users create variants (discriminated by role)."""

    model_config = ConfigDict(protected_namespaces=())

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=100)
    is_active: bool | None = True
    is_superuser: bool | None = False
    must_change_password: bool | None = False  # Требуется смена пароля при первом входе

    # Профиль
    full_name: str | None = Field(None, min_length=1, max_length=100)
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, min_length=10, max_length=20)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        if not any(c.isupper() for c in v):
            raise ValueError('Пароль должен содержать минимум одну заглавную букву')
        if not any(c.islower() for c in v):
            raise ValueError('Пароль должен содержать минимум одну строчную букву')
        if not any(c.isdigit() for c in v):
            raise ValueError('Пароль должен содержать минимум одну цифру')
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _normalize_user_management_email(
            v,
            allow_reserved=_allow_reserved_email_domains(),
        )


class DoctorUserCreateRequest(_UserCreateCommon):
    """Canonical new-doctor onboarding variant (POST /users, role=Doctor).

    doctor_profile is REQUIRED here and published as required in OpenAPI, so
    generated clients describe the conditional contract instead of relying
    on the runtime validator alone (Codex P2). Legacy doctor-role spellings
    are handled by NonDoctorUserCreateRequest and keep the auto-map.
    """

    model_config = ConfigDict(protected_namespaces=())

    role: Literal["Doctor"]
    doctor_profile: DoctorProfileCreate

    # NOTE: only FORMAT is validated here (schema layer has no DB access).
    # Catalog membership + active status are enforced at the API boundary
    # (POST /users) against the medical_specialties runtime SSOT — see
    # user_management/_users.py; empty/missing catalog surfaces as 503 there.


class NonDoctorUserCreateRequest(_UserCreateCommon):
    """Every non-canonical-Doctor role variant (POST /users).

    Includes legacy lowercase doctor-role spellings (cardio/derma/dentist/
    doctor/…): they keep the compatibility auto-map and must NOT carry a
    doctor_profile — the block is rejected here instead of being silently
    dropped.
    """

    model_config = ConfigDict(protected_namespaces=())

    role: NonDoctorRoleLiteral
    doctor_profile: None = None


# Conditional create contract: FastAPI publishes this as oneOf with a role
# discriminator, so OpenAPI/generated TS distinguish the Doctor variant
# (doctor_profile REQUIRED) from every non-Doctor create.
UserCreateRequest = Annotated[
    Union[DoctorUserCreateRequest, NonDoctorUserCreateRequest],
    Field(discriminator="role"),
]


class UserUpdateRequest(BaseModel):
    """Схема обновления пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    username: str | None = Field(None, min_length=3, max_length=50)
    email: str | None = Field(None, min_length=3, max_length=254)
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: str | None = Field(
        None, pattern=_USER_MANAGEMENT_ROLE_PATTERN
    )
    is_active: bool | None = None
    is_superuser: bool | None = None

    # Профиль
    full_name: str | None = Field(None, min_length=1, max_length=100)
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, min_length=10, max_length=20)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _normalize_user_management_email(
            v,
            allow_reserved=_allow_reserved_email_domains(),
        )


class UserResponse(BaseModel):
    """Схема ответа пользователя"""

    model_config = ConfigDict(protected_namespaces=(), extra='ignore')

    id: int
    username: str
    email: str | None = None
    role: str
    is_active: bool
    is_superuser: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Профиль
    profile: UserProfileResponse | None = None
    preferences: UserPreferencesResponse | None = None
    notification_settings: UserNotificationSettingsResponse | None = None

    # Lifecycle (decision #5): None = no linked Doctor row; True = linked
    # Doctor profile still has the auto-create placeholder specialty
    # ("general") and must be completed by an admin.
    doctor_profile_incomplete: bool | None = None


class UserListResponse(BaseModel):
    """Схема ответа списка пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    users: list[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserStatsResponse(BaseModel):
    """Схема ответа статистики пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    total_users: int
    active_users: int
    inactive_users: int
    suspended_users: int
    locked_users: int
    users_by_role: dict[str, int]
    users_with_profiles: int
    users_with_2fa: int
    recent_registrations: int  # За последние 30 дней
    recent_logins: int  # За последние 24 часа


class UserSearchRequest(BaseModel):
    """Схема поиска пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    query: str | None = Field(None, min_length=1, max_length=100)
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    # Codex re-review P2 (PR #3025): READ surface — uses the compatibility
    # filter vocabulary so legacy 'Receptionist' rows stay queryable.
    role: str | None = Field(
        None, pattern=_USER_MANAGEMENT_ROLE_FILTER_PATTERN
    )
    status: UserStatus | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    last_login_from: datetime | None = None
    last_login_to: datetime | None = None
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class UserBulkActionRequest(BaseModel):
    """Схема массовых действий с пользователями"""

    model_config = ConfigDict(protected_namespaces=())

    user_ids: list[int] = Field(..., min_length=1, max_length=100)
    action: str = Field(
        ..., pattern="^(activate|deactivate|suspend|unsuspend|delete|change_role)$"
    )
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: str | None = Field(
        None, pattern=_USER_MANAGEMENT_ROLE_PATTERN
    )
    reason: str | None = Field(None, max_length=500)


class UserBulkActionResponse(BaseModel):
    """Схема ответа массовых действий"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    processed_count: int
    failed_count: int
    failed_users: list[dict[str, Any]] = []


class UserExportRequest(BaseModel):
    """Схема экспорта пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    format: str = Field(..., pattern="^(csv|excel|json|pdf)$")
    fields: list[str] | None = None
    filters: UserSearchRequest | None = None
    include_profile: bool = False
    include_preferences: bool = False
    include_audit_logs: bool = False


class UserExportResponse(BaseModel):
    """Схема ответа экспорта пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    file_url: str | None = None
    file_size: int | None = None
    record_count: int
