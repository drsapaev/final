"""
Pydantic схемы для системы аутентификации
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, validator
from pydantic.config import ConfigDict


class LoginRequest(BaseModel):
    """Схема для запроса входа"""

    model_config = ConfigDict(protected_namespaces=())

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    remember_me: bool = Field(False, description="Запомнить пользователя")
    device_fingerprint: Optional[str] = Field(None, max_length=64)


class LoginResponse(BaseModel):
    """Схема для ответа входа"""

    model_config = ConfigDict(protected_namespaces=())

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]
    requires_2fa: bool = False
    two_factor_method: Optional[str] = None
    pending_2fa_token: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Схема для запроса обновления токена"""

    model_config = ConfigDict(protected_namespaces=())

    refresh_token: str = Field(..., min_length=1)


class RefreshTokenResponse(BaseModel):
    """Схема для ответа обновления токена"""

    model_config = ConfigDict(protected_namespaces=())

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    """Схема для запроса выхода"""

    model_config = ConfigDict(protected_namespaces=())

    refresh_token: Optional[str] = None
    logout_all_devices: bool = False


class LogoutResponse(BaseModel):
    """Схема для ответа выхода"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str


class PasswordResetRequest(BaseModel):
    """Схема для запроса сброса пароля"""

    model_config = ConfigDict(protected_namespaces=())

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Схема для подтверждения сброса пароля"""

    model_config = ConfigDict(protected_namespaces=())

    token: str = Field(..., min_length=32, max_length=64)
    new_password: str = Field(..., min_length=8, max_length=100)

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        if not any(c.isupper() for c in v):
            raise ValueError('Пароль должен содержать минимум одну заглавную букву')
        if not any(c.islower() for c in v):
            raise ValueError('Пароль должен содержать минимум одну строчную букву')
        if not any(c.isdigit() for c in v):
            raise ValueError('Пароль должен содержать минимум одну цифру')
        return v


class PasswordChangeRequest(BaseModel):
    """Схема для смены пароля"""

    model_config = ConfigDict(protected_namespaces=())

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        if not any(c.isupper() for c in v):
            raise ValueError('Пароль должен содержать минимум одну заглавную букву')
        if not any(c.islower() for c in v):
            raise ValueError('Пароль должен содержать минимум одну строчную букву')
        if not any(c.isdigit() for c in v):
            raise ValueError('Пароль должен содержать минимум одну цифру')
        return v


class EmailVerificationRequest(BaseModel):
    """Схема для запроса верификации email"""

    model_config = ConfigDict(protected_namespaces=())

    email: EmailStr


class EmailVerificationConfirmRequest(BaseModel):
    """Схема для подтверждения верификации email"""

    model_config = ConfigDict(protected_namespaces=())

    token: str = Field(..., min_length=32, max_length=64)


class UserProfileUpdateRequest(BaseModel):
    """Схема для обновления профиля пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserProfileResponse(BaseModel):
    """Схема для ответа профиля пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool
    email_verified: bool
    phone_verified: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    two_factor_enabled: bool = False


class UserSessionResponse(BaseModel):
    """Схема для ответа сессии пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    session_id: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    current_session: bool = False


class LoginAttemptResponse(BaseModel):
    """Схема для ответа попытки входа"""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    username: Optional[str] = None
    email: Optional[str] = None
    ip_address: str
    success: bool
    failure_reason: Optional[str] = None
    attempted_at: datetime


class UserActivityResponse(BaseModel):
    """Схема для ответа активности пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    activity_type: str
    description: Optional[str] = None
    created_at: datetime
    ip_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SecurityEventResponse(BaseModel):
    """Схема для ответа события безопасности"""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    event_type: str
    severity: str
    description: str
    created_at: datetime
    ip_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    resolved: bool
    resolved_at: Optional[datetime] = None


class TokenValidationResponse(BaseModel):
    """Схема для ответа валидации токена"""

    model_config = ConfigDict(protected_namespaces=())

    valid: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
    requires_2fa: bool = False


class AuthStatusResponse(BaseModel):
    """Схема для ответа статуса аутентификации"""

    model_config = ConfigDict(protected_namespaces=())

    authenticated: bool
    user: Optional[UserProfileResponse] = None
    session: Optional[UserSessionResponse] = None
    two_factor_required: bool = False
    two_factor_verified: bool = False


class PasswordStrengthResponse(BaseModel):
    """Схема для ответа проверки силы пароля"""

    model_config = ConfigDict(protected_namespaces=())

    score: int = Field(..., ge=0, le=100)
    strength: str = Field(..., pattern="^(weak|fair|good|strong|very_strong)$")
    suggestions: List[str] = []


class DeviceInfoResponse(BaseModel):
    """Схема для ответа информации об устройстве"""

    model_config = ConfigDict(protected_namespaces=())

    device_fingerprint: str
    ip_address: str
    user_agent: str
    device_name: Optional[str] = None
    is_trusted: bool = False
    last_used: Optional[datetime] = None


class AuthErrorResponse(BaseModel):
    """Схема для ответа ошибки аутентификации"""

    model_config = ConfigDict(protected_namespaces=())

    error: str
    error_description: str
    error_code: str
    details: Optional[Dict[str, Any]] = None


class AuthSuccessResponse(BaseModel):
    """Схема для ответа успешной аутентификации"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# Схемы для административных функций


class UserListResponse(BaseModel):
    """Схема для ответа списка пользователей"""

    model_config = ConfigDict(protected_namespaces=())

    users: List[UserProfileResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserCreateRequest(BaseModel):
    """Схема для создания пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    role: str = Field(..., pattern="^(Admin|Doctor|Nurse|Receptionist|Patient)$")
    is_active: bool = True
    is_superuser: bool = False

    @validator('password')
    def validate_password(cls, v):
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
    """Схема для обновления пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(
        None, pattern="^(Admin|Doctor|Nurse|Receptionist|Patient)$"
    )
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


class UserDeleteRequest(BaseModel):
    """Схема для удаления пользователя"""

    model_config = ConfigDict(protected_namespaces=())

    confirm: bool = Field(True, description="Подтверждение удаления")
    transfer_to: Optional[int] = Field(
        None, description="ID пользователя для передачи данных"
    )


class SessionListResponse(BaseModel):
    """Схема для ответа списка сессий"""

    model_config = ConfigDict(protected_namespaces=())

    sessions: List[UserSessionResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class SessionRevokeRequest(BaseModel):
    """Схема для отзыва сессии"""

    model_config = ConfigDict(protected_namespaces=())

    session_id: int
    reason: Optional[str] = Field(None, max_length=200)


class SecurityEventListResponse(BaseModel):
    """Схема для ответа списка событий безопасности"""

    model_config = ConfigDict(protected_namespaces=())

    events: List[SecurityEventResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class SecurityEventResolveRequest(BaseModel):
    """Схема для разрешения события безопасности"""

    model_config = ConfigDict(protected_namespaces=())

    event_id: int
    resolution_notes: Optional[str] = Field(None, max_length=500)


# Схемы для статистики


class AuthStatsResponse(BaseModel):
    """Схема для ответа статистики аутентификации"""

    model_config = ConfigDict(protected_namespaces=())

    total_users: int
    active_users: int
    total_sessions: int
    active_sessions: int
    failed_login_attempts: int
    security_events: int
    unresolved_security_events: int
    two_factor_enabled_users: int
    last_24h_logins: int
    last_24h_failed_attempts: int
