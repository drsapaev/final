"""
Расширенные модели для управления пользователями
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
import enum


class UserStatus(str, enum.Enum):
    """Статусы пользователя"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    LOCKED = "locked"


class UserProfile(Base):
    """Расширенный профиль пользователя"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Основная информация
    full_name = Column(String(100), nullable=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    middle_name = Column(String(50), nullable=True)
    
    # Контактная информация
    phone = Column(String(20), nullable=True)
    phone_verified = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    alternative_email = Column(String(120), nullable=True)
    
    # Личная информация
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(10), nullable=True)  # male, female, other
    nationality = Column(String(50), nullable=True)
    language = Column(String(10), default="ru")
    timezone = Column(String(50), default="Europe/Moscow")
    
    # Адрес
    address_line1 = Column(String(200), nullable=True)
    address_line2 = Column(String(200), nullable=True)
    city = Column(String(50), nullable=True)
    state = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(50), nullable=True)
    
    # Профессиональная информация
    job_title = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    employee_id = Column(String(50), nullable=True)
    hire_date = Column(DateTime, nullable=True)
    salary = Column(Integer, nullable=True)  # В копейках
    
    # Настройки
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    website = Column(String(200), nullable=True)
    social_links = Column(JSON, nullable=True)  # {"linkedin": "...", "twitter": "..."}
    
    # Системная информация
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    last_login = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="profile")
    preferences = relationship("UserPreferences", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("UserNotificationSettings", back_populates="profile", uselist=False, cascade="all, delete-orphan")


class UserPreferences(Base):
    """Настройки пользователя"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, unique=True)
    
    # Общие настройки
    theme = Column(String(20), default="light")  # light, dark, auto
    language = Column(String(10), default="ru")
    timezone = Column(String(50), default="Europe/Moscow")
    date_format = Column(String(20), default="DD.MM.YYYY")
    time_format = Column(String(10), default="24")  # 12, 24
    
    # Уведомления
    email_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)
    push_notifications = Column(Boolean, default=True)
    desktop_notifications = Column(Boolean, default=True)
    
    # Рабочие настройки
    working_hours_start = Column(String(5), default="09:00")
    working_hours_end = Column(String(5), default="18:00")
    working_days = Column(JSON, default=lambda: [1, 2, 3, 4, 5])  # 1=Monday, 7=Sunday
    break_duration = Column(Integer, default=60)  # В минутах
    
    # Интерфейс
    dashboard_layout = Column(JSON, nullable=True)
    sidebar_collapsed = Column(Boolean, default=False)
    compact_mode = Column(Boolean, default=False)
    show_tooltips = Column(Boolean, default=True)
    
    # Безопасность
    session_timeout = Column(Integer, default=30)  # В минутах
    require_2fa = Column(Boolean, default=False)
    auto_logout = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="preferences")
    profile = relationship("UserProfile", back_populates="preferences")


class UserNotificationSettings(Base):
    """Настройки уведомлений пользователя"""
    __tablename__ = "user_notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, unique=True)
    
    # Email уведомления
    email_appointment_reminder = Column(Boolean, default=True)
    email_appointment_cancellation = Column(Boolean, default=True)
    email_appointment_confirmation = Column(Boolean, default=True)
    email_payment_receipt = Column(Boolean, default=True)
    email_payment_reminder = Column(Boolean, default=True)
    email_system_updates = Column(Boolean, default=True)
    email_security_alerts = Column(Boolean, default=True)
    email_newsletter = Column(Boolean, default=False)
    
    # SMS уведомления
    sms_appointment_reminder = Column(Boolean, default=False)
    sms_appointment_cancellation = Column(Boolean, default=False)
    sms_appointment_confirmation = Column(Boolean, default=False)
    sms_payment_receipt = Column(Boolean, default=False)
    sms_emergency = Column(Boolean, default=True)
    
    # Push уведомления
    push_appointment_reminder = Column(Boolean, default=True)
    push_appointment_cancellation = Column(Boolean, default=True)
    push_appointment_confirmation = Column(Boolean, default=True)
    push_payment_receipt = Column(Boolean, default=True)
    push_system_updates = Column(Boolean, default=True)
    push_security_alerts = Column(Boolean, default=True)
    
    # Время уведомлений
    reminder_time_before = Column(Integer, default=60)  # В минутах
    quiet_hours_start = Column(String(5), default="22:00")
    quiet_hours_end = Column(String(5), default="08:00")
    weekend_notifications = Column(Boolean, default=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="notification_settings")
    profile = relationship("UserProfile", back_populates="notifications")


class UserRole(Base):
    """Роли пользователей"""
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Разрешения
    permissions = Column(JSON, nullable=True)  # Список разрешений
    
    # Системная информация
    is_system = Column(Boolean, default=False)  # Системная роль
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Связи
    # users = relationship("User", back_populates="user_role")  # Временно отключено - нет внешнего ключа


class UserPermission(Base):
    """Разрешения пользователей"""
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # auth, patients, appointments, etc.
    
    # Системная информация
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    # roles = relationship("UserRole", secondary="role_permissions", back_populates="permissions")  # Временно отключено - нет соответствующей связи в UserRole


class RolePermission(Base):
    """Связь ролей и разрешений"""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("user_roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("user_permissions.id"), nullable=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    # role = relationship("UserRole", back_populates="role_permissions")  # Временно отключено
    # permission = relationship("UserPermission", back_populates="role_permissions")  # Временно отключено


class UserGroup(Base):
    """Группы пользователей"""
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Настройки группы
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Связи
    # users = relationship("User", secondary="user_group_members", back_populates="groups")  # Временно отключено


class UserGroupMember(Base):
    """Участники групп пользователей"""
    __tablename__ = "user_group_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=False)
    
    # Роль в группе
    role = Column(String(20), default="member")  # member, admin, moderator
    
    # Метаданные
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    # user = relationship("User", back_populates="group_memberships")  # Временно отключено
    # group = relationship("UserGroup", back_populates="members")  # Временно отключено


class UserAuditLog(Base):
    """Аудит действий пользователей"""
    __tablename__ = "user_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Действие
    action = Column(String(50), nullable=False)  # create, update, delete, login, logout, etc.
    resource_type = Column(String(50), nullable=True)  # user, patient, appointment, etc.
    resource_id = Column(Integer, nullable=True)
    
    # Детали
    description = Column(Text, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Контекст
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(64), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    user = relationship("User", back_populates="audit_logs")

