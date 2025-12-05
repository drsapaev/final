"""
Модели для системы ролей и разрешений
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

# Таблица связи многие-ко-многим для пользователей и ролей
user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("assigned_at", DateTime(timezone=True), server_default=func.now()),
    Column("assigned_by", Integer, ForeignKey("users.id"), nullable=True),
    extend_existing=True,
)

# Таблица связи многие-ко-многим для ролей и разрешений
role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("granted_at", DateTime(timezone=True), server_default=func.now()),
    Column("granted_by", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    extend_existing=True,
)

# Таблица связи многие-ко-многим для пользователей и групп
user_groups_table = Table(
    "user_groups_members",
    Base.metadata,
    Column(
        "user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("user_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("joined_at", DateTime(timezone=True), server_default=func.now()),
    Column("added_by", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    extend_existing=True,
)

# Таблица связи многие-ко-многим для групп и ролей
group_roles_table = Table(
    "group_roles",
    Base.metadata,
    Column(
        "group_id",
        Integer,
        ForeignKey("user_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("assigned_at", DateTime(timezone=True), server_default=func.now()),
    Column("assigned_by", Integer, ForeignKey("users.id"), nullable=True),
    extend_existing=True,
)


class Permission(Base):
    """Разрешения системы"""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    codename: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )

    # Метаданные
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=role_permissions_table, back_populates="permissions"
    )


class Role(Base):
    """Роли пользователей"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Иерархия ролей
    parent_role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=True
    )
    level: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # Уровень в иерархии

    # Метаданные
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # Системная роль
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    parent_role: Mapped[Optional["Role"]] = relationship("Role", remote_side=[id])
    child_roles: Mapped[List["Role"]] = relationship(
        "Role", back_populates="parent_role"
    )

    permissions: Mapped[List["Permission"]] = relationship(
        "Permission", secondary=role_permissions_table, back_populates="roles"
    )

    # users: Mapped[List["User"]] = relationship(
    #     "User",
    #     secondary=user_roles_table,
    #     back_populates="roles"
    # )

    # groups: Mapped[List["UserGroup"]] = relationship(
    #     "UserGroup",
    #     secondary=group_roles_table,
    #     back_populates="roles"
    # )


class UserGroup(Base):
    """Группы пользователей"""

    __tablename__ = "user_groups"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Тип группы
    group_type: Mapped[str] = mapped_column(
        String(50), default="custom", nullable=False, index=True
    )  # department, custom, system

    # Метаданные
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    # users: Mapped[List["User"]] = relationship(
    #     "User",
    #     secondary=user_groups_table,
    #     back_populates="groups"
    # )

    # roles: Mapped[List["Role"]] = relationship(
    #     "Role",
    #     secondary=group_roles_table,
    #     back_populates="groups"
    # )


class UserPermissionOverride(Base):
    """Индивидуальные переопределения разрешений пользователей"""

    __tablename__ = "user_permission_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип переопределения
    override_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # grant, deny
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Временные ограничения
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Метаданные
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    permission: Mapped["Permission"] = relationship(
        "Permission", foreign_keys=[permission_id]
    )
    granted_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[granted_by]
    )


class RoleHierarchy(Base):
    """Иерархия ролей для наследования разрешений"""

    __tablename__ = "role_hierarchy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail

    # Связи
    parent_role: Mapped["Role"] = relationship("Role", foreign_keys=[parent_role_id])
    child_role: Mapped["Role"] = relationship("Role", foreign_keys=[child_role_id])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class PermissionAuditLog(Base):
    """Аудит изменений разрешений"""

    __tablename__ = "permission_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve audit (user may be deleted but audit must remain)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # grant, revoke, override
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # user, role, group
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    permission_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("permissions.id"), nullable=True
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=True
    )

    # Детали изменения
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Метаданные
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связи
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    permission: Mapped[Optional["Permission"]] = relationship(
        "Permission", foreign_keys=[permission_id]
    )
    role: Mapped[Optional["Role"]] = relationship("Role", foreign_keys=[role_id])
