"""
Модели для системы аутентификации
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base):
    """Модель для refresh токенов"""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index('idx_refresh_tokens_user_expires', 'user_id', 'expires_at'),
        Index('idx_refresh_tokens_token_revoked', 'token', 'revoked'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (tokens die with user)

    # Токен и его данные
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)  # JWT ID

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # IP и устройство
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4 или IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class UserSession(Base):
    """Модель для пользовательских сессий"""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index('idx_user_sessions_user_active', 'user_id', 'revoked'),
        Index('idx_user_sessions_expires', 'expires_at'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (tokens die with user)

    # Сессия (соответствует реальной схеме БД)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="user_sessions")


class PasswordResetToken(Base):
    """Модель для токенов сброса пароля"""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index('idx_password_reset_tokens_user', 'user_id'),
        Index('idx_password_reset_tokens_expires', 'expires_at'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (tokens die with user)

    # Токен
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # IP и устройство
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="password_reset_tokens")


class EmailVerificationToken(Base):
    """Модель для токенов верификации email"""

    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        Index('idx_email_verification_tokens_user', 'user_id'),
        Index('idx_email_verification_tokens_expires', 'expires_at'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (tokens die with user)

    # Токен
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # IP и устройство
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="email_verification_tokens")


class LoginAttempt(Base):
    """Модель для попыток входа"""

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index('idx_login_attempts_user', 'user_id'),
        Index('idx_login_attempts_attempted', 'attempted_at'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve failed attempts even if user deleted

    # Данные попытки
    username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Для неудачных попыток
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Результат
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # "invalid_password", "user_not_found", etc.

    # Метаданные
    attempted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связи
    user: Mapped[Optional["User"]] = relationship("User", back_populates="login_attempts")


class UserActivity(Base):
    """Модель для активности пользователей"""

    __tablename__ = "user_activities"
    __table_args__ = (
        Index('idx_user_activities_user_type', 'user_id', 'activity_type'),
        Index('idx_user_activities_created', 'created_at'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )  # ✅ SECURITY: CASCADE (tokens die with user)

    # Активность
    activity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "login", "logout", "profile_update", etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Дополнительные данные
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON строка с дополнительными данными

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="user_activities")


class SecurityEvent(Base):
    """Модель для событий безопасности"""

    __tablename__ = "security_events"
    __table_args__ = (
        Index('idx_security_events_user_type', 'user_id', 'event_type'),
        Index('idx_security_events_created', 'created_at'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve security events

    # Событие
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "suspicious_login", "password_changed", etc.
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # "low", "medium", "high", "critical"
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Дополнительные данные
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON строка с дополнительными данными
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail

    # Связи
    user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[user_id], back_populates="security_events"
    )
    resolver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by])
