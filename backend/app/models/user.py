from __future__ import annotations

from typing import Optional, List

from sqlalchemy import Boolean, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.models.role_permission import user_roles_table, user_groups_table


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
    
    # Связь с пациентом
    patient: Mapped[Optional["Patient"]] = relationship("Patient", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Роли и группы (через единые M2M таблицы)
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles_table,
        primaryjoin=lambda: User.id == user_roles_table.c.user_id,
        secondaryjoin=lambda: __import__('app').models.role_permission.Role.id == user_roles_table.c.role_id,
        viewonly=False
    )
    groups: Mapped[List["UserGroup"]] = relationship(
        "UserGroup",
        secondary=user_groups_table,
        primaryjoin=lambda: User.id == user_groups_table.c.user_id,
        secondaryjoin=lambda: __import__('app').models.role_permission.UserGroup.id == user_groups_table.c.group_id,
        viewonly=False
    )
    
    # Переопределения разрешений
    permission_overrides: Mapped[List["UserPermissionOverride"]] = relationship(
        "UserPermissionOverride", 
        foreign_keys="UserPermissionOverride.user_id",
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    # group_memberships: Mapped[List["UserGroupMember"]] = relationship("UserGroupMember", back_populates="user", cascade="all, delete-orphan")  # Временно отключено
    
    # Аудит
    audit_logs: Mapped[List["UserAuditLog"]] = relationship("UserAuditLog", back_populates="user", cascade="all, delete-orphan")
