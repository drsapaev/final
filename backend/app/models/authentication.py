"""
Модели для системы аутентификации
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class RefreshToken(Base):
    """Модель для refresh токенов"""
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index('idx_refresh_tokens_user_expires', 'user_id', 'expires_at'),
        Index('idx_refresh_tokens_token_revoked', 'token', 'revoked'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Токен и его данные
    token = Column(String(255), unique=True, nullable=False, index=True)
    jti = Column(String(36), unique=True, nullable=False, index=True)  # JWT ID
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # IP и устройство
    ip_address = Column(String(45), nullable=True)  # IPv4 или IPv6
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(64), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="refresh_tokens")


class UserSession(Base):
    """Модель для пользовательских сессий"""
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index('idx_user_sessions_user_active', 'user_id', 'revoked'),
        Index('idx_user_sessions_expires', 'expires_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Сессия (соответствует реальной схеме БД)
    refresh_token = Column(String(128), nullable=True)  # Соответствует БД
    user_agent = Column(String(512), nullable=True)     # Соответствует БД
    ip = Column(String(64), nullable=True)              # Соответствует БД
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)            # Соответствует БД
    
    # Связи
    user = relationship("User", back_populates="user_sessions")


class PasswordResetToken(Base):
    """Модель для токенов сброса пароля"""
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index('idx_password_reset_tokens_user', 'user_id'),
        Index('idx_password_reset_tokens_expires', 'expires_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Токен
    token = Column(String(64), unique=True, nullable=False, index=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # IP и устройство
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="password_reset_tokens")


class EmailVerificationToken(Base):
    """Модель для токенов верификации email"""
    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        Index('idx_email_verification_tokens_user', 'user_id'),
        Index('idx_email_verification_tokens_expires', 'expires_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Токен
    token = Column(String(64), unique=True, nullable=False, index=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # IP и устройство
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="email_verification_tokens")


class LoginAttempt(Base):
    """Модель для попыток входа"""
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index('idx_login_attempts_user', 'user_id'),
        Index('idx_login_attempts_attempted', 'attempted_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Может быть null для неудачных попыток
    
    # Данные попытки
    username = Column(String(50), nullable=True)  # Для неудачных попыток
    email = Column(String(120), nullable=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    
    # Результат
    success = Column(Boolean, default=False)
    failure_reason = Column(String(100), nullable=True)  # "invalid_password", "user_not_found", etc.
    
    # Метаданные
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    user = relationship("User", back_populates="login_attempts")


class UserActivity(Base):
    """Модель для активности пользователей"""
    __tablename__ = "user_activities"
    __table_args__ = (
        Index('idx_user_activities_user_type', 'user_id', 'activity_type'),
        Index('idx_user_activities_created', 'created_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Активность
    activity_type = Column(String(50), nullable=False)  # "login", "logout", "profile_update", etc.
    description = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Дополнительные данные
    extra_data = Column(Text, nullable=True)  # JSON строка с дополнительными данными
    
    # Связи
    user = relationship("User", back_populates="user_activities")


class SecurityEvent(Base):
    """Модель для событий безопасности"""
    __tablename__ = "security_events"
    __table_args__ = (
        Index('idx_security_events_user_type', 'user_id', 'event_type'),
        Index('idx_security_events_created', 'created_at'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Может быть null для системных событий
    
    # Событие
    event_type = Column(String(50), nullable=False)  # "suspicious_login", "password_changed", etc.
    severity = Column(String(20), nullable=False)  # "low", "medium", "high", "critical"
    description = Column(Text, nullable=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Дополнительные данные
    extra_data = Column(Text, nullable=True)  # JSON строка с дополнительными данными
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="security_events")
    resolver = relationship("User", foreign_keys=[resolved_by])
