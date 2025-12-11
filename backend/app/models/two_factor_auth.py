"""
Модели для двухфакторной аутентификации (2FA)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class TwoFactorAuth(Base):
    """Основная модель 2FA для пользователя"""

    __tablename__ = "two_factor_auth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False
    )  # ✅ SECURITY: CASCADE (2FA dies with user)

    # TOTP настройки
    totp_secret: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Base32 encoded secret
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Backup коды
    backup_codes_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes_count: Mapped[int] = mapped_column(Integer, default=0)

    # Recovery настройки
    recovery_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recovery_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recovery_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="two_factor_auth")
    backup_codes: Mapped[List["TwoFactorBackupCode"]] = relationship(
        "TwoFactorBackupCode",
        back_populates="two_factor_auth",
        cascade="all, delete-orphan",
    )
    recovery_attempts: Mapped[List["TwoFactorRecovery"]] = relationship(
        "TwoFactorRecovery",
        back_populates="two_factor_auth",
        cascade="all, delete-orphan",
    )


class TwoFactorBackupCode(Base):
    """Backup коды для 2FA"""

    __tablename__ = "two_factor_backup_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    two_factor_auth_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("two_factor_auth.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (backup codes die with 2FA)

    # Код и его статус
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # 8-символьный код
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связи
    two_factor_auth: Mapped["TwoFactorAuth"] = relationship(
        "TwoFactorAuth", back_populates="backup_codes"
    )


class TwoFactorRecovery(Base):
    """Попытки восстановления 2FA"""

    __tablename__ = "two_factor_recovery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    two_factor_auth_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("two_factor_auth.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (backup codes die with 2FA)

    # Данные восстановления
    recovery_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'email', 'phone', 'backup_code'
    recovery_value: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # email, phone, или backup code
    recovery_token: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # токен для подтверждения

    # Статус
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4 или IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Связи
    two_factor_auth: Mapped["TwoFactorAuth"] = relationship(
        "TwoFactorAuth", back_populates="recovery_attempts"
    )


class TwoFactorSession(Base):
    """Сессии с 2FA"""

    __tablename__ = "two_factor_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (sessions/devices die with user)

    # Сессия
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 2FA статус
    two_factor_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    two_factor_method: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # 'totp', 'backup_code', 'recovery'

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # IP и устройство
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User")


class TwoFactorDevice(Base):
    """Зарегистрированные устройства для 2FA"""

    __tablename__ = "two_factor_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (sessions/devices die with user)

    # Устройство
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'mobile', 'desktop', 'tablet'
    device_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Статус
    trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # IP и браузер
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User")
