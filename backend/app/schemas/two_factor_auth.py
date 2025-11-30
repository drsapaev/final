"""
Pydantic схемы для двухфакторной аутентификации (2FA)
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator
from pydantic.config import ConfigDict


class TwoFactorAuthBase(BaseModel):
    """Базовая схема 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    totp_enabled: bool = False
    recovery_email: Optional[str] = Field(None, max_length=255)
    recovery_phone: Optional[str] = Field(None, max_length=20)
    recovery_enabled: bool = False


class TwoFactorAuthCreate(TwoFactorAuthBase):
    """Схема для создания 2FA"""

    user_id: int


class TwoFactorAuthUpdate(TwoFactorAuthBase):
    """Схема для обновления 2FA"""

    totp_secret: Optional[str] = None
    totp_verified: Optional[bool] = None
    backup_codes_generated: Optional[bool] = None
    recovery_enabled: Optional[bool] = None


class TwoFactorAuthOut(TwoFactorAuthBase):
    """Схема для вывода 2FA"""

    id: int
    user_id: int
    totp_verified: bool
    backup_codes_generated: bool
    backup_codes_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TwoFactorRecoveryBase(BaseModel):
    """Базовая схема восстановления 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_type: str = Field(..., pattern="^(email|phone|backup_code)$")
    recovery_value: str = Field(..., max_length=255)
    recovery_token: Optional[str] = None


class TwoFactorRecoveryCreate(TwoFactorRecoveryBase):
    """Схема для создания попытки восстановления"""

    two_factor_auth_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class TwoFactorRecoveryVerify(BaseModel):
    """Схема для верификации восстановления"""

    recovery_token: str = Field(..., min_length=32, max_length=64)
    verification_code: str = Field(..., min_length=6, max_length=8)


class TwoFactorRecoveryOut(TwoFactorRecoveryBase):
    """Схема для вывода попытки восстановления"""

    id: int
    two_factor_auth_id: int
    verified: bool
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        from_attributes = True


class TwoFactorSessionBase(BaseModel):
    """Базовая схема сессии 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    session_token: str = Field(..., min_length=32, max_length=64)
    device_fingerprint: Optional[str] = None
    two_factor_verified: bool = False
    two_factor_method: Optional[str] = Field(
        None, pattern="^(totp|backup_code|recovery)$"
    )


class TwoFactorSessionCreate(TwoFactorSessionBase):
    """Схема для создания сессии 2FA"""

    user_id: int
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None


class TwoFactorSessionOut(TwoFactorSessionBase):
    """Схема для вывода сессии 2FA"""

    id: int
    user_id: int
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None

    class Config:
        from_attributes = True


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
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class TwoFactorDeviceOut(TwoFactorDeviceBase):
    """Схема для вывода устройства 2FA"""

    id: int
    user_id: int
    created_at: datetime
    last_used: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        from_attributes = True


# Схемы для API запросов


class TwoFactorSetupRequest(BaseModel):
    """Запрос на настройку 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_email: Optional[str] = Field(None, max_length=255)
    recovery_phone: Optional[str] = Field(None, max_length=20)
    device_name: Optional[str] = Field(None, max_length=100)
    device_type: Optional[str] = Field(None, pattern="^(mobile|desktop|tablet)$")


class TwoFactorVerifyRequest(BaseModel):
    """Запрос на верификацию 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    totp_code: Optional[str] = Field(None, min_length=6, max_length=6)
    backup_code: Optional[str] = Field(None, min_length=8, max_length=10)
    recovery_token: Optional[str] = Field(None, min_length=32, max_length=64)
    device_fingerprint: Optional[str] = None
    remember_device: bool = False
    # Для блокирующего флоу входа (нет access токена до подтверждения)
    pending_2fa_token: Optional[str] = None


class TwoFactorDisableRequest(BaseModel):
    """Запрос на отключение 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    password: str = Field(..., min_length=1)
    totp_code: Optional[str] = Field(None, min_length=6, max_length=6)
    backup_code: Optional[str] = Field(None, min_length=8, max_length=10)


class TwoFactorRecoveryRequest(BaseModel):
    """Запрос на восстановление 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_type: str = Field(..., pattern="^(email|phone|backup_code)$")
    recovery_value: str = Field(..., max_length=255)
    device_fingerprint: Optional[str] = None


class TwoFactorStatusResponse(BaseModel):
    """Ответ со статусом 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    enabled: bool
    totp_enabled: bool
    totp_verified: bool
    backup_codes_generated: bool
    backup_codes_count: int
    recovery_enabled: bool
    recovery_email: Optional[str] = None
    recovery_phone: Optional[str] = None
    trusted_devices_count: int
    last_used: Optional[datetime] = None


class TwoFactorSetupResponse(BaseModel):
    """Ответ на настройку 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    qr_code_url: str
    secret_key: str
    backup_codes: List[str]
    recovery_token: str
    expires_at: datetime


class TwoFactorVerifyResponse(BaseModel):
    """Ответ на верификацию 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    session_token: Optional[str] = None
    device_trusted: bool = False
    backup_codes_remaining: Optional[int] = None
    # Для завершения логина, если сервер обменял pending_2fa_token на токены
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None


class TwoFactorRecoveryResponse(BaseModel):
    """Ответ на запрос восстановления 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    recovery_token: str
    expires_at: datetime
    message: str


class TwoFactorDeviceListResponse(BaseModel):
    """Ответ со списком устройств 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    devices: List[TwoFactorDeviceOut]
    total: int


class TwoFactorBackupCodesResponse(BaseModel):
    """Ответ со списком backup кодов"""

    model_config = ConfigDict(protected_namespaces=())

    backup_codes: List[str]
    total: int
    generated_at: datetime


# Схемы для ошибок


class TwoFactorErrorResponse(BaseModel):
    """Схема ошибки 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    error: str
    message: str
    code: str
    details: Optional[dict] = None


class TwoFactorSuccessResponse(BaseModel):
    """Схема успешного ответа 2FA"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    message: str
    data: Optional[dict] = None
