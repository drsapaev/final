"""
Pydantic схемы для управления пользователями
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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


class TimeFormat(str, Enum):
    """Форматы времени"""

    HOUR_12 = "12"
    HOUR_24 = "24"


# Схемы для профиля пользователя


class UserProfileBase(BaseModel):
    """Базовая схема профиля пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    middle_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    date_of_birth: Optional[datetime] = None
    gender: Optional[Gender] = None
    nationality: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=1000)
    website: Optional[str] = Field(None, max_length=200)


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
    alternative_email: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    employee_id: Optional[str] = None
    hire_date: Optional[datetime] = None
    avatar_url: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    status: UserStatus
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    login_count: int
    failed_login_attempts: int
    locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# Схемы для настроек пользователя


class UserPreferencesBase(BaseModel):
    """Базовая схема настроек пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    theme: Optional[Theme] = Theme.LIGHT
    language: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=50)
    date_format: Optional[str] = Field(None, max_length=20)
    time_format: Optional[TimeFormat] = TimeFormat.HOUR_24
    email_notifications: Optional[bool] = True
    sms_notifications: Optional[bool] = False
    push_notifications: Optional[bool] = True
    desktop_notifications: Optional[bool] = True


class UserPreferencesCreate(UserPreferencesBase):
    """Схема создания настроек пользователя"""

    user_id: int
    profile_id: int


class UserPreferencesUpdate(UserPreferencesBase):
    """Схема обновления настроек пользователя"""

    working_hours_start: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    working_hours_end: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    working_days: Optional[List[int]] = Field(None, min_length=1, max_length=7)
    break_duration: Optional[int] = Field(None, ge=0, le=480)  # 0-8 часов
    dashboard_layout: Optional[Dict[str, Any]] = None
    sidebar_collapsed: Optional[bool] = False
    compact_mode: Optional[bool] = False
    show_tooltips: Optional[bool] = True
    session_timeout: Optional[int] = Field(None, ge=5, le=480)  # 5 минут - 8 часов
    require_2fa: Optional[bool] = False
    auto_logout: Optional[bool] = True

    # ============================================
    # EMR PREFERENCES (Smart Autocomplete)
    # ============================================
    # Режим умного поля (ghost | mvp | hybrid | word)
    emr_smart_field_mode: Optional[str] = Field(None, pattern=r"^(ghost|mvp|hybrid|word)$")
    # Показывать переключатель режимов
    emr_show_mode_switcher: Optional[bool] = None
    # Задержка debounce в мс
    emr_debounce_ms: Optional[int] = Field(None, ge=100, le=2000)
    # Недавно использованные коды МКБ-10
    emr_recent_icd10: Optional[List[str]] = Field(None, max_length=20)
    # Недавно использованные шаблоны назначений
    emr_recent_templates: Optional[List[str]] = Field(None, max_length=20)
    # Избранные шаблоны по специальностям
    emr_favorite_templates: Optional[Dict[str, List[str]]] = None
    # Кастомные шаблоны пользователя
    emr_custom_templates: Optional[List[Dict[str, Any]]] = None


class UserPreferencesResponse(UserPreferencesBase):
    """Схема ответа настроек пользователя"""

    model_config = ConfigDict(protected_namespaces=(), extra='ignore')
    id: int
    user_id: int
    profile_id: int
    working_hours_start: str
    working_hours_end: str
    working_days: List[int]
    break_duration: int
    dashboard_layout: Optional[Dict[str, Any]] = None
    sidebar_collapsed: bool
    compact_mode: bool
    show_tooltips: bool
    session_timeout: int
    require_2fa: bool
    auto_logout: bool

    # EMR Preferences
    emr_smart_field_mode: Optional[str] = "ghost"
    emr_show_mode_switcher: Optional[bool] = True
    emr_debounce_ms: Optional[int] = 500
    emr_recent_icd10: Optional[List[str]] = None
    emr_recent_templates: Optional[List[str]] = None
    emr_favorite_templates: Optional[Dict[str, List[str]]] = None
    emr_custom_templates: Optional[List[Dict[str, Any]]] = None

    created_at: datetime
    updated_at: datetime


# Схемы для настроек уведомлений


class UserNotificationSettingsBase(BaseModel):
    """Базовая схема настроек уведомлений"""

    model_config = ConfigDict(protected_namespaces=())

    email_appointment_reminder: Optional[bool] = True
    email_appointment_cancellation: Optional[bool] = True
    email_appointment_confirmation: Optional[bool] = True
    email_payment_receipt: Optional[bool] = True
    email_payment_reminder: Optional[bool] = True
    email_system_updates: Optional[bool] = True
    email_security_alerts: Optional[bool] = True
    email_newsletter: Optional[bool] = False
    sms_appointment_reminder: Optional[bool] = False
    sms_appointment_cancellation: Optional[bool] = False
    sms_appointment_confirmation: Optional[bool] = False
    sms_payment_receipt: Optional[bool] = False
    sms_emergency: Optional[bool] = True
    push_appointment_reminder: Optional[bool] = True
    push_appointment_cancellation: Optional[bool] = True
    push_appointment_confirmation: Optional[bool] = True
    push_payment_receipt: Optional[bool] = True
    push_system_updates: Optional[bool] = True
    push_security_alerts: Optional[bool] = True


class UserNotificationSettingsCreate(UserNotificationSettingsBase):
    """Схема создания настроек уведомлений"""

    user_id: int
    profile_id: int


class UserNotificationSettingsUpdate(UserNotificationSettingsBase):
    """Схема обновления настроек уведомлений"""

    reminder_time_before: Optional[int] = Field(
        None, ge=5, le=10080
    )  # 5 минут - 7 дней
    quiet_hours_start: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    quiet_hours_end: Optional[str] = Field(
        None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    weekend_notifications: Optional[bool] = False


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
    description: Optional[str] = Field(None, max_length=500)
    permissions: Optional[List[str]] = None


class UserRoleCreate(UserRoleBase):
    """Схема создания роли пользователя"""

    is_system: Optional[bool] = False
    is_active: Optional[bool] = True


class UserRoleUpdate(BaseModel):
    """Схема обновления роли пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


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
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=50)


class UserPermissionCreate(UserPermissionBase):
    """Схема создания разрешения пользователя"""

    is_system: Optional[bool] = False
    is_active: Optional[bool] = True


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
    description: Optional[str] = Field(None, max_length=500)


class UserGroupCreate(UserGroupBase):
    """Схема создания группы пользователей"""

    is_active: Optional[bool] = True
    is_system: Optional[bool] = False


class UserGroupUpdate(BaseModel):
    """Схема обновления группы пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


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
    resource_type: Optional[str] = Field(None, max_length=50)
    resource_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=1000)
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None


class UserAuditLogCreate(UserAuditLogBase):
    """Схема создания аудита пользователя"""

    user_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None


class UserAuditLogResponse(UserAuditLogBase):
    """Схема ответа аудита пользователя"""

    id: int
    user_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
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
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    must_change_password: Optional[bool] = False  # Требуется смена пароля при первом входе

    # Профиль
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)

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

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: Optional[str] = Field(
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$"
    )
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

    # Профиль
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)


class UserResponse(BaseModel):
    """Схема ответа пользователя"""

    model_config = ConfigDict(protected_namespaces=(), extra='ignore')

    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Профиль
    profile: Optional[UserProfileResponse] = None
    preferences: Optional[UserPreferencesResponse] = None
    notification_settings: Optional[UserNotificationSettingsResponse] = None


class UserListResponse(BaseModel):
    """Схема ответа списка пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    users: List[UserResponse]
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
    users_by_role: Dict[str, int]
    users_with_profiles: int
    users_with_2fa: int
    recent_registrations: int  # За последние 30 дней
    recent_logins: int  # За последние 24 часа


class UserSearchRequest(BaseModel):
    """Схема поиска пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    query: Optional[str] = Field(None, min_length=1, max_length=100)
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: Optional[str] = Field(
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$"
    )
    status: Optional[UserStatus] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    last_login_from: Optional[datetime] = None
    last_login_to: Optional[datetime] = None
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class UserBulkActionRequest(BaseModel):
    """Схема массовых действий с пользователями"""

    model_config = ConfigDict(protected_namespaces=())

    user_ids: List[int] = Field(..., min_items=1, max_items=100)
    action: str = Field(
        ..., pattern="^(activate|deactivate|suspend|unsuspend|delete|change_role)$"
    )
    # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    role: Optional[str] = Field(
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Cashier|Lab|Patient)$"
    )
    reason: Optional[str] = Field(None, max_length=500)


class UserBulkActionResponse(BaseModel):
    """Схема ответа массовых действий"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    processed_count: int
    failed_count: int
    failed_users: List[Dict[str, Any]] = []


class UserExportRequest(BaseModel):
    """Схема экспорта пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    format: str = Field(..., pattern="^(csv|excel|json|pdf)$")
    fields: Optional[List[str]] = None
    filters: Optional[UserSearchRequest] = None
    include_profile: bool = False
    include_preferences: bool = False
    include_audit_logs: bool = False


class UserExportResponse(BaseModel):
    """Схема ответа экспорта пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    record_count: int
