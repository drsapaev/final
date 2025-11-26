"""
Модели для двухфакторной аутентификации (2FA)
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class TwoFactorAuth(Base):
    """Основная модель 2FA для пользователя"""
    __tablename__ = "two_factor_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # TOTP настройки
    totp_secret = Column(String(32), nullable=True)  # Base32 encoded secret
    totp_enabled = Column(Boolean, default=False)
    totp_verified = Column(Boolean, default=False)
    
    # Backup коды
    backup_codes_generated = Column(Boolean, default=False)
    backup_codes_count = Column(Integer, default=0)
    
    # Recovery настройки
    recovery_email = Column(String(255), nullable=True)
    recovery_phone = Column(String(20), nullable=True)
    recovery_enabled = Column(Boolean, default=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="two_factor_auth")
    backup_codes = relationship("TwoFactorBackupCode", back_populates="two_factor_auth", cascade="all, delete-orphan")
    recovery_attempts = relationship("TwoFactorRecovery", back_populates="two_factor_auth", cascade="all, delete-orphan")


class TwoFactorBackupCode(Base):
    """Backup коды для 2FA"""
    __tablename__ = "two_factor_backup_codes"

    id = Column(Integer, primary_key=True, index=True)
    two_factor_auth_id = Column(Integer, ForeignKey("two_factor_auth.id"), nullable=False)
    
    # Код и его статус
    code = Column(String(10), nullable=False)  # 8-символьный код
    used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    two_factor_auth = relationship("TwoFactorAuth", back_populates="backup_codes")


class TwoFactorRecovery(Base):
    """Попытки восстановления 2FA"""
    __tablename__ = "two_factor_recovery"

    id = Column(Integer, primary_key=True, index=True)
    two_factor_auth_id = Column(Integer, ForeignKey("two_factor_auth.id"), nullable=False)
    
    # Данные восстановления
    recovery_type = Column(String(20), nullable=False)  # 'email', 'phone', 'backup_code'
    recovery_value = Column(String(255), nullable=False)  # email, phone, или backup code
    recovery_token = Column(String(64), nullable=True)  # токен для подтверждения
    
    # Статус
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)  # IPv4 или IPv6
    user_agent = Column(Text, nullable=True)
    
    # Связи
    two_factor_auth = relationship("TwoFactorAuth", back_populates="recovery_attempts")


class TwoFactorSession(Base):
    """Сессии с 2FA"""
    __tablename__ = "two_factor_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Сессия
    session_token = Column(String(64), unique=True, nullable=False)
    device_fingerprint = Column(String(64), nullable=True)
    
    # 2FA статус
    two_factor_verified = Column(Boolean, default=False)
    two_factor_method = Column(String(20), nullable=True)  # 'totp', 'backup_code', 'recovery'
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    # IP и устройство
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_name = Column(String(100), nullable=True)
    
    # Связи
    user = relationship("User")


class TwoFactorDevice(Base):
    """Зарегистрированные устройства для 2FA"""
    __tablename__ = "two_factor_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Устройство
    device_name = Column(String(100), nullable=False)
    device_type = Column(String(20), nullable=False)  # 'mobile', 'desktop', 'tablet'
    device_fingerprint = Column(String(64), unique=True, nullable=False)
    
    # Статус
    trusted = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
    
    # IP и браузер
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Связи
    user = relationship("User")
