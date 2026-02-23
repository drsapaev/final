"""
Pydantic схемы для двухфакторной аутентификации (2FA)
"""

from datetime import datetime

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class TwoFactorAuthBase(BaseModel):
    """Базовая схема 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    totp_enabled: bool = False
    recovery_email: str | None = Field(None, max_length=255)
    recovery_phone: str | None = Field(None, max_length=20)
    recovery_enabled: bool = False


class TwoFactorAuthCreate(TwoFactorAuthBase):
    """Схема для создания 2FA"""

    user_id: int


class TwoFactorAuthUpdate(TwoFactorAuthBase):
    """Схема для обновления 2FA"""

    totp_secret: str | None = None
    totp_verified: bool | None = None
    backup_codes_generated: bool | None = None
    recovery_enabled: bool | None = None


class TwoFactorAuthOut(TwoFactorAuthBase):
    """Схема для вывода 2FA"""

    id: int
    user_id: int
    totp_verified: bool
    backup_codes_generated: bool
    backup_codes_count: int
    created_at: datetime
    updated_at: datetime | None = None
    last_used: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TwoFactorBackupCodeBase(BaseModel):
    """Базовая схема backup кода"""

    model_config = ConfigDict(protected_namespaces=())

    code: str = Field(..., min_length=8, max_length=10)
    used: bool = False


class TwoFactorBackupCodeCreate(TwoFactorBackupCodeBase):
    """Схема для создания backup кода"""

    two_factor_auth_id: int


class TwoFactorBackupCodeOut(TwoFactorBackupCodeBase):
    """Схема для вывода backup кода"""

    id: int
    two_factor_auth_id: int
    used_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TwoFactorRecoveryBase(BaseModel):
    """Базовая схема восстановления 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_type: str = Field(..., pattern="^(email|phone|backup_code)$")
    recovery_value: str = Field(..., max_length=255)
    recovery_token: str | None = None


class TwoFactorRecoveryCreate(TwoFactorRecoveryBase):
    """Схема для создания попытки восстановления"""

    two_factor_auth_id: int
    ip_address: str | None = None
    user_agent: str | None = None


class TwoFactorRecoveryVerify(BaseModel):
    """Схема для верификации восстановления"""

    recovery_token: str = Field(..., min_length=32, max_length=64)
    verification_code: str = Field(..., min_length=6, max_length=8)


class TwoFactorRecoveryOut(TwoFactorRecoveryBase):
    """Схема для вывода попытки восстановления"""

    id: int
    two_factor_auth_id: int
    verified: bool
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TwoFactorSessionBase(BaseModel):
    """Базовая схема сессии 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    session_token: str = Field(..., min_length=32, max_length=64)
    device_fingerprint: str | None = None
    two_factor_verified: bool = False
    two_factor_method: str | None = Field(
        None, pattern="^(totp|backup_code|recovery)$"
    )


class TwoFactorSessionCreate(TwoFactorSessionBase):
    """Схема для создания сессии 2FA"""

    user_id: int
    expires_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    device_name: str | None = None


class TwoFactorSessionOut(TwoFactorSessionBase):
    """Схема для вывода сессии 2FA"""

    id: int
    user_id: int
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    device_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TwoFactorDeviceBase(BaseModel):
    """Базовая схема устройства 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    device_name: str = Field(..., min_length=1, max_length=100)
    device_type: str = Field(..., pattern="^(mobile|desktop|tablet)$")
    device_fingerprint: str = Field(..., min_length=32, max_length=64)
    trusted: bool = False
    active: bool = True


class TwoFactorDeviceCreate(TwoFactorDeviceBase):
    """Схема для создания устройства 2FA"""

    user_id: int
    ip_address: str | None = None
    user_agent: str | None = None


class TwoFactorDeviceOut(TwoFactorDeviceBase):
    """Схема для вывода устройства 2FA"""

    id: int
    user_id: int
    created_at: datetime
    last_used: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    model_config = ConfigDict(from_attributes=True)


# Схемы для API запросов


class TwoFactorSetupRequest(BaseModel):
    """Запрос на настройку 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_email: str | None = Field(None, max_length=255)
    recovery_phone: str | None = Field(None, max_length=20)
    device_name: str | None = Field(None, max_length=100)
    device_type: str | None = Field(None, pattern="^(mobile|desktop|tablet)$")


class TwoFactorVerifyRequest(BaseModel):
    """Запрос на верификацию 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    totp_code: str | None = Field(None, min_length=6, max_length=6)
    backup_code: str | None = Field(None, min_length=8, max_length=10)
    recovery_token: str | None = Field(None, min_length=32, max_length=64)
    device_fingerprint: str | None = None
    remember_device: bool = False
    # Для блокирующего флоу входа (нет access токена до подтверждения)
    pending_2fa_token: str | None = None


class TwoFactorDisableRequest(BaseModel):
    """Запрос на отключение 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    password: str = Field(..., min_length=1)
    totp_code: str | None = Field(None, min_length=6, max_length=6)
    backup_code: str | None = Field(None, min_length=8, max_length=10)


class TwoFactorRecoveryRequest(BaseModel):
    """Запрос на восстановление 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_type: str = Field(..., pattern="^(email|phone|backup_code)$")
    recovery_value: str = Field(..., max_length=255)
    device_fingerprint: str | None = None


class TwoFactorStatusResponse(BaseModel):
    """Ответ со статусом 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    enabled: bool
    totp_enabled: bool
    totp_verified: bool
    backup_codes_generated: bool
    backup_codes_count: int
    recovery_enabled: bool
    recovery_email: str | None = None
    recovery_phone: str | None = None
    trusted_devices_count: int
    last_used: datetime | None = None


class TwoFactorSetupResponse(BaseModel):
    """Ответ на настройку 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    qr_code_url: str
    secret_key: str
    backup_codes: list[str]
    recovery_token: str
    expires_at: datetime


class TwoFactorVerifyResponse(BaseModel):
    """Ответ на верификацию 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    session_token: str | None = None
    device_trusted: bool = False
    backup_codes_remaining: int | None = None
    # Для завершения логина, если сервер обменял pending_2fa_token на токены
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None


class TwoFactorRecoveryResponse(BaseModel):
    """Ответ на запрос восстановления 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_token: str
    expires_at: datetime
    message: str


class TwoFactorDeviceListResponse(BaseModel):
    """Ответ со списком устройств 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    devices: list[TwoFactorDeviceOut]
    total: int


class TwoFactorBackupCodesResponse(BaseModel):
    """Ответ со списком backup кодов"""

    model_config = ConfigDict(protected_namespaces=())

    backup_codes: list[str]
    total: int
    generated_at: datetime


# Схемы для ошибок


class TwoFactorErrorResponse(BaseModel):
    """Схема ошибки 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    error: str
    message: str
    code: str
    details: dict | None = None


class TwoFactorSuccessResponse(BaseModel):
    """Схема успешного ответа 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    data: dict | None = None
