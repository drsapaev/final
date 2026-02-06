from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.models.role_permission import user_groups_table, user_roles_table


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
    # Требуется смена пароля при следующем входе
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # FCM Device Token for Push Notifications
    device_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Метаданные
    created_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 2FA связи
    two_factor_auth: Mapped[Optional["TwoFactorAuth"]] = relationship(
        "TwoFactorAuth", back_populates="user", uselist=False
    )

    # Аутентификация связи
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    user_sessions: Mapped[List["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[List["EmailVerificationToken"]] = relationship(
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )
    login_attempts: Mapped[List["LoginAttempt"]] = relationship(
        "LoginAttempt", back_populates="user", cascade="all, delete-orphan"
    )
    user_activities: Mapped[List["UserActivity"]] = relationship(
        "UserActivity", back_populates="user", cascade="all, delete-orphan"
    )
    security_events: Mapped[List["SecurityEvent"]] = relationship(
        "SecurityEvent",
        foreign_keys="SecurityEvent.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Профиль и настройки
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    preferences: Mapped[Optional["UserPreferences"]] = relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    notification_settings: Mapped[Optional["UserNotificationSettings"]] = relationship(
        "UserNotificationSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Связь с пациентом
    patient: Mapped[Optional["Patient"]] = relationship(
        "Patient", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan",
        foreign_keys="Patient.user_id"  # ✅ FIX: Explicit FK to resolve ambiguity with Patient.deleted_by
    )

    # Роли и группы (через единые M2M таблицы)
    # passive_deletes=True - let DB handle cascade deletion
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles_table,
        primaryjoin=lambda: User.id == user_roles_table.c.user_id,
        secondaryjoin=lambda: __import__('app').models.role_permission.Role.id
        == user_roles_table.c.role_id,
        viewonly=True,  # Read-only to avoid conflicts with string role field
        lazy="noload",  # Don't load by default to avoid query errors
    )
    groups: Mapped[List["UserGroup"]] = relationship(
        "UserGroup",
        secondary=user_groups_table,
        primaryjoin=lambda: User.id == user_groups_table.c.user_id,
        secondaryjoin=lambda: __import__('app').models.role_permission.UserGroup.id
        == user_groups_table.c.group_id,
        viewonly=True,  # Read-only
        lazy="noload",  # Don't load by default
    )

    # Переопределения разрешений
    permission_overrides: Mapped[List["UserPermissionOverride"]] = relationship(
        "UserPermissionOverride",
        foreign_keys="UserPermissionOverride.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # group_memberships: Mapped[List["UserGroupMember"]] = relationship("UserGroupMember", back_populates="user", cascade="all, delete-orphan")  # Временно отключено

    # Аудит
    audit_logs: Mapped[List["UserAuditLog"]] = relationship(
        "UserAuditLog", back_populates="user", cascade="all, delete-orphan"
    )

    # Персональная клиническая память врача
    treatment_templates: Mapped[List["DoctorTreatmentTemplate"]] = relationship(
        "DoctorTreatmentTemplate",
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="noload",  # Don't load by default
    )
