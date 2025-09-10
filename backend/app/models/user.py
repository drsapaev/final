from __future__ import annotations

from typing import Optional, List

from sqlalchemy import Boolean, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    email: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="Admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Метаданные
    created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 2FA связи
    two_factor_auth: Mapped[Optional["TwoFactorAuth"]] = relationship("TwoFactorAuth", back_populates="user", uselist=False)
    
    # Аутентификация связи
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    user_sessions: Mapped[List["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens: Mapped[List["PasswordResetToken"]] = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    email_verification_tokens: Mapped[List["EmailVerificationToken"]] = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    login_attempts: Mapped[List["LoginAttempt"]] = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")
    user_activities: Mapped[List["UserActivity"]] = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")
    security_events: Mapped[List["SecurityEvent"]] = relationship("SecurityEvent", foreign_keys="SecurityEvent.user_id", back_populates="user", cascade="all, delete-orphan")
    
    # Профиль и настройки
    profile: Mapped[Optional["UserProfile"]] = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    preferences: Mapped[Optional["UserPreferences"]] = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notification_settings: Mapped[Optional["UserNotificationSettings"]] = relationship("UserNotificationSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Роли и группы
    # user_role: Mapped[Optional["UserRole"]] = relationship("UserRole", back_populates="users")  # Временно отключено - нет внешнего ключа
    # groups: Mapped[List["UserGroup"]] = relationship("UserGroup", secondary="user_group_members", back_populates="users")  # Временно отключено
    # group_memberships: Mapped[List["UserGroupMember"]] = relationship("UserGroupMember", back_populates="user", cascade="all, delete-orphan")  # Временно отключено
    
    # Аудит
    audit_logs: Mapped[List["UserAuditLog"]] = relationship("UserAuditLog", back_populates="user", cascade="all, delete-orphan")
