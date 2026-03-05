"""
Pydantic схемы для управления пользователями
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic.config import ConfigDict


class UserStatus(str, Enum):
    """Статусы пользователя"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    LOCKED = "locked"


class Gender(str, Enum):
    """Пол пользователя"""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Theme(str, Enum):
    """Темы интерфейса"""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    SYSTEM = "system"
    VIBRANT = "vibrant"
    GLASS = "glass"
    GRADIENT = "gradient"


class TimeFormat(str, Enum):
    """Форматы времени"""

    HOUR_12 = "12"
    HOUR_24 = "24"


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


class UserCreateRequest(BaseModel):
    """Схема создания пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: str = Field(..., pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$")
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


class UserUpdateRequest(BaseModel):
    """Схема обновления пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    username: str | None = Field(None, min_length=3, max_length=50)
    email: EmailStr | None = None
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: str | None = Field(
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$"
    )
    is_active: bool | None = None
    is_superuser: bool | None = None

    # Профиль
    full_name: str | None = Field(None, min_length=1, max_length=100)
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, min_length=10, max_length=20)


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
    role: str | None = Field(
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$"
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
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$"
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
