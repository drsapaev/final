"""
CRUD операции для управления пользователями
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, text
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.role_permission import (
    Permission,
    Role,
    UserGroup,
    UserPermissionOverride,
)
from app.models.user import User
from app.models.user_profile import (
    UserAuditLog,
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
    UserStatus,
)
from app.schemas.user_management import (
    UserBulkActionRequest,
    UserCreateRequest,
    UserGroupCreate,
    UserGroupMemberCreate,
    UserGroupUpdate,
    UserNotificationSettingsCreate,
    UserNotificationSettingsUpdate,
    UserPreferencesCreate,
    UserPreferencesUpdate,
    UserProfileCreate,
    UserProfileUpdate,
    UserRoleCreate,
    UserRoleUpdate,
    UserSearchRequest,
    UserUpdateRequest,
)


class CRUDUserProfile(CRUDBase[UserProfile, UserProfileCreate, UserProfileUpdate]):
    """CRUD операции для профилей пользователей"""

    def get_by_user_id(self, db: Session, user_id: int) -> Optional[UserProfile]:
        """Получить профиль по ID пользователя"""
        return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    def get_by_phone(self, db: Session, phone: str) -> Optional[UserProfile]:
        """Получить профиль по телефону"""
        return db.query(UserProfile).filter(UserProfile.phone == phone).first()

    def get_by_status(
        self, db: Session, status: UserStatus, limit: int = 100
    ) -> List[UserProfile]:
        """Получить профили по статусу"""
        return (
            db.query(UserProfile)
            .filter(UserProfile.status == status)
            .limit(limit)
            .all()
        )

    def get_recent_activity(self, db: Session, hours: int = 24) -> List[UserProfile]:
        """Получить профили с недавней активностью"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return db.query(UserProfile).filter(UserProfile.last_activity >= since).all()

    def update_status(self, db: Session, user_id: int, status: UserStatus) -> bool:
        """Обновить статус профиля"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.status = status
            db.commit()
            return True
        return False

    def update_last_login(self, db: Session, user_id: int) -> bool:
        """Обновить время последнего входа"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.last_login = datetime.utcnow()
            profile.login_count += 1
            db.commit()
            return True
        return False

    def update_last_activity(self, db: Session, user_id: int) -> bool:
        """Обновить время последней активности"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.last_activity = datetime.utcnow()
            db.commit()
            return True
        return False

    def increment_failed_attempts(self, db: Session, user_id: int) -> bool:
        """Увеличить счетчик неудачных попыток входа"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.failed_login_attempts += 1
            db.commit()
            return True
        return False

    def reset_failed_attempts(self, db: Session, user_id: int) -> bool:
        """Сбросить счетчик неудачных попыток входа"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.failed_login_attempts = 0
            profile.locked_until = None
            db.commit()
            return True
        return False

    def lock_user(self, db: Session, user_id: int, until: datetime) -> bool:
        """Заблокировать пользователя до указанного времени"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.locked_until = until
            profile.status = UserStatus.LOCKED
            db.commit()
            return True
        return False

    def unlock_user(self, db: Session, user_id: int) -> bool:
        """Разблокировать пользователя"""
        profile = self.get_by_user_id(db, user_id)
        if profile:
            profile.locked_until = None
            profile.status = UserStatus.ACTIVE
            db.commit()
            return True
        return False

    def is_user_locked(self, db: Session, user_id: int) -> bool:
        """Проверить, заблокирован ли пользователь"""
        profile = self.get_by_user_id(db, user_id)
        if profile and profile.locked_until:
            return profile.locked_until > datetime.utcnow()
        return False


class CRUDUserPreferences(
    CRUDBase[UserPreferences, UserPreferencesCreate, UserPreferencesUpdate]
):
    """CRUD операции для настроек пользователей"""

    def get_by_user_id(self, db: Session, user_id: int) -> Optional[UserPreferences]:
        """Получить настройки по ID пользователя"""
        return (
            db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        )

    def get_by_theme(self, db: Session, theme: str) -> List[UserPreferences]:
        """Получить настройки по теме"""
        return db.query(UserPreferences).filter(UserPreferences.theme == theme).all()

    def get_by_language(self, db: Session, language: str) -> List[UserPreferences]:
        """Получить настройки по языку"""
        return (
            db.query(UserPreferences).filter(UserPreferences.language == language).all()
        )

    def get_by_timezone(self, db: Session, timezone: str) -> List[UserPreferences]:
        """Получить настройки по часовому поясу"""
        return (
            db.query(UserPreferences).filter(UserPreferences.timezone == timezone).all()
        )

    def update_theme(self, db: Session, user_id: int, theme: str) -> bool:
        """Обновить тему пользователя"""
        preferences = self.get_by_user_id(db, user_id)
        if preferences:
            preferences.theme = theme
            db.commit()
            return True
        return False

    def update_language(self, db: Session, user_id: int, language: str) -> bool:
        """Обновить язык пользователя"""
        preferences = self.get_by_user_id(db, user_id)
        if preferences:
            preferences.language = language
            db.commit()
            return True
        return False

    def update_timezone(self, db: Session, user_id: int, timezone: str) -> bool:
        """Обновить часовой пояс пользователя"""
        preferences = self.get_by_user_id(db, user_id)
        if preferences:
            preferences.timezone = timezone
            db.commit()
            return True
        return False


class CRUDUserNotificationSettings(
    CRUDBase[
        UserNotificationSettings,
        UserNotificationSettingsCreate,
        UserNotificationSettingsUpdate,
    ]
):
    """CRUD операции для настроек уведомлений пользователей"""

    def get_by_user_id(
        self, db: Session, user_id: int
    ) -> Optional[UserNotificationSettings]:
        """Получить настройки уведомлений по ID пользователя"""
        return (
            db.query(UserNotificationSettings)
            .filter(UserNotificationSettings.user_id == user_id)
            .first()
        )

    def get_users_with_email_notifications(
        self, db: Session, notification_type: str
    ) -> List[UserNotificationSettings]:
        """Получить пользователей с включенными email уведомлениями"""
        return (
            db.query(UserNotificationSettings)
            .filter(
                getattr(UserNotificationSettings, f"email_{notification_type}") == True
            )
            .all()
        )

    def get_users_with_sms_notifications(
        self, db: Session, notification_type: str
    ) -> List[UserNotificationSettings]:
        """Получить пользователей с включенными SMS уведомлениями"""
        return (
            db.query(UserNotificationSettings)
            .filter(
                getattr(UserNotificationSettings, f"sms_{notification_type}") == True
            )
            .all()
        )

    def get_users_with_push_notifications(
        self, db: Session, notification_type: str
    ) -> List[UserNotificationSettings]:
        """Получить пользователей с включенными push уведомлениями"""
        return (
            db.query(UserNotificationSettings)
            .filter(
                getattr(UserNotificationSettings, f"push_{notification_type}") == True
            )
            .all()
        )

    def update_notification_setting(
        self, db: Session, user_id: int, setting_name: str, value: bool
    ) -> bool:
        """Обновить конкретную настройку уведомлений"""
        settings = self.get_by_user_id(db, user_id)
        if settings and hasattr(settings, setting_name):
            setattr(settings, setting_name, value)
            db.commit()
            return True
        return False


class CRUDUserRole(CRUDBase[Role, UserRoleCreate, UserRoleUpdate]):
    """CRUD операции для ролей пользователей"""

    def get_by_name(self, db: Session, name: str) -> Optional[Role]:
        """Получить роль по имени"""
        return db.query(Role).filter(Role.name == name).first()

    def get_active_roles(self, db: Session) -> List[Role]:
        """Получить активные роли"""
        return db.query(Role).filter(Role.is_active == True).all()

    def get_system_roles(self, db: Session) -> List[Role]:
        """Получить системные роли"""
        return db.query(Role).filter(Role.is_system == True).all()

    def get_users_by_role(self, db: Session, role_name: str) -> List[User]:
        """Получить пользователей по роли"""
        return db.query(User).filter(User.role == role_name).all()

    def add_permission(self, db: Session, role_id: int, permission_id: int) -> bool:
        """Добавить разрешение к роли"""
        # Временно отключено - нет таблицы role_permissions в role_permission.py
        return True

    def remove_permission(self, db: Session, role_id: int, permission_id: int) -> bool:
        """Удалить разрешение из роли"""
        # Временно отключено - нет таблицы role_permissions в role_permission.py
        return True

    def get_role_permissions(self, db: Session, role_id: int) -> List[Permission]:
        """Получить разрешения роли"""
        # Временно отключено - нет таблицы role_permissions в role_permission.py
        return []


class CRUDUserPermission(CRUDBase[Permission, None, None]):
    """CRUD операции для разрешений пользователей"""

    def get_by_name(self, db: Session, name: str) -> Optional[Permission]:
        """Получить разрешение по имени"""
        return db.query(Permission).filter(Permission.name == name).first()

    def get_by_category(self, db: Session, category: str) -> List[Permission]:
        """Получить разрешения по категории"""
        return db.query(Permission).filter(Permission.category == category).all()

    def get_active_permissions(self, db: Session) -> List[Permission]:
        """Получить активные разрешения"""
        return db.query(Permission).filter(Permission.is_active == True).all()

    def get_system_permissions(self, db: Session) -> List[Permission]:
        """Получить системные разрешения"""
        return db.query(Permission).filter(Permission.is_system == True).all()


class CRUDUserGroup(CRUDBase[UserGroup, UserGroupCreate, UserGroupUpdate]):
    """CRUD операции для групп пользователей"""

    def get_by_name(self, db: Session, name: str) -> Optional[UserGroup]:
        """Получить группу по имени"""
        return db.query(UserGroup).filter(UserGroup.name == name).first()

    def get_active_groups(self, db: Session) -> List[UserGroup]:
        """Получить активные группы"""
        return db.query(UserGroup).filter(UserGroup.is_active == True).all()

    def get_system_groups(self, db: Session) -> List[UserGroup]:
        """Получить системные группы"""
        return db.query(UserGroup).filter(UserGroup.is_system == True).all()

    def get_group_members(self, db: Session, group_id: int) -> List[User]:
        """Получить участников группы"""
        # Временно отключено - нет таблицы user_group_members в role_permission.py
        return []

    def add_member(
        self, db: Session, group_id: int, user_id: int, role: str = "member"
    ) -> bool:
        """Добавить участника в группу"""
        # Временно отключено - нет таблицы user_group_members в role_permission.py
        return True

    def remove_member(self, db: Session, group_id: int, user_id: int) -> bool:
        """Удалить участника из группы"""
        # Временно отключено - нет таблицы user_group_members в role_permission.py
        return True

    def update_member_role(
        self, db: Session, group_id: int, user_id: int, role: str
    ) -> bool:
        """Обновить роль участника в группе"""
        # Временно отключено - нет таблицы user_group_members в role_permission.py
        return True


# CRUDUserGroupMember временно отключен - нет модели UserGroupMember в role_permission.py
# class CRUDUserGroupMember(CRUDBase[UserGroupMember, UserGroupMemberCreate, None]):
#     """CRUD операции для участников групп"""
#     pass


class CRUDUserAuditLog(CRUDBase[UserAuditLog, None, None]):
    """CRUD операции для аудита пользователей"""

    def get_by_user_id(
        self, db: Session, user_id: int, limit: int = 100
    ) -> List[UserAuditLog]:
        """Получить аудит пользователя"""
        return (
            db.query(UserAuditLog)
            .filter(UserAuditLog.user_id == user_id)
            .order_by(desc(UserAuditLog.created_at))
            .limit(limit)
            .all()
        )

    def get_by_action(
        self, db: Session, action: str, limit: int = 100
    ) -> List[UserAuditLog]:
        """Получить аудит по действию"""
        return (
            db.query(UserAuditLog)
            .filter(UserAuditLog.action == action)
            .order_by(desc(UserAuditLog.created_at))
            .limit(limit)
            .all()
        )

    def get_by_resource(
        self, db: Session, resource_type: str, resource_id: int, limit: int = 100
    ) -> List[UserAuditLog]:
        """Получить аудит по ресурсу"""
        return (
            db.query(UserAuditLog)
            .filter(
                and_(
                    UserAuditLog.resource_type == resource_type,
                    UserAuditLog.resource_id == resource_id,
                )
            )
            .order_by(desc(UserAuditLog.created_at))
            .limit(limit)
            .all()
        )

    def get_recent_activity(
        self, db: Session, hours: int = 24, limit: int = 100
    ) -> List[UserAuditLog]:
        """Получить недавнюю активность"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            db.query(UserAuditLog)
            .filter(UserAuditLog.created_at >= since)
            .order_by(desc(UserAuditLog.created_at))
            .limit(limit)
            .all()
        )

    def get_user_activity_summary(
        self, db: Session, user_id: int, days: int = 30
    ) -> Dict[str, int]:
        """Получить сводку активности пользователя"""
        since = datetime.utcnow() - timedelta(days=days)

        # Подсчитываем действия по типам
        actions = (
            db.query(UserAuditLog.action, func.count(UserAuditLog.id).label('count'))
            .filter(
                and_(UserAuditLog.user_id == user_id, UserAuditLog.created_at >= since)
            )
            .group_by(UserAuditLog.action)
            .all()
        )

        return {action: count for action, count in actions}

    def cleanup_old_logs(self, db: Session, days: int = 365) -> int:
        """Очистить старые записи аудита"""
        since = datetime.utcnow() - timedelta(days=days)
        count = db.query(UserAuditLog).filter(UserAuditLog.created_at < since).delete()
        db.commit()
        return count


# Расширенный CRUD для пользователей
class CRUDUserExtended(CRUDBase[User, UserCreateRequest, UserUpdateRequest]):
    """Расширенные CRUD операции для пользователей"""

    def get_with_profile(self, db: Session, user_id: int) -> Optional[User]:
        """Получить пользователя с профилем"""
        return db.query(User).filter(User.id == user_id).first()

    def get_users_by_role(
        self, db: Session, role: str, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Получить пользователей по роли"""
        return db.query(User).filter(User.role == role).offset(skip).limit(limit).all()

    def get_active_users(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Получить активных пользователей"""
        return (
            db.query(User)
            .filter(User.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_superusers(self, db: Session) -> List[User]:
        """Получить суперпользователей"""
        return db.query(User).filter(User.is_superuser == True).all()

    def search_users(
        self, db: Session, query: str, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Поиск пользователей"""
        return (
            db.query(User)
            .filter(
                or_(User.username.ilike(f"%{query}%"), User.email.ilike(f"%{query}%"))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_user_statistics(self, db: Session) -> Dict[str, int]:
        """Получить статистику пользователей"""
        total = db.query(User).count()
        active = db.query(User).filter(User.is_active == True).count()
        superusers = db.query(User).filter(User.is_superuser == True).count()

        # Статистика по ролям
        roles_stats = {}
        for role in ["Admin", "Doctor", "Nurse", "Receptionist", "Patient"]:
            count = db.query(User).filter(User.role == role).count()
            roles_stats[role] = count

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "superusers": superusers,
            "by_role": roles_stats,
        }

    def deactivate_user(self, db: Session, user_id: int) -> bool:
        """Деактивировать пользователя"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = False
            if user.profile:
                user.profile.status = UserStatus.INACTIVE
            db.commit()
            return True
        return False

    def activate_user(self, db: Session, user_id: int) -> bool:
        """Активировать пользователя"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = True
            if user.profile:
                user.profile.status = UserStatus.ACTIVE
            db.commit()
            return True
        return False


# Создаем экземпляры CRUD классов
user_profile = CRUDUserProfile(UserProfile)
user_preferences = CRUDUserPreferences(UserPreferences)
user_notification_settings = CRUDUserNotificationSettings(UserNotificationSettings)
user_role = CRUDUserRole(Role)
user_permission = CRUDUserPermission(Permission)
user_group = CRUDUserGroup(UserGroup)
# user_group_member временно отключен
user_audit_log = CRUDUserAuditLog(UserAuditLog)
user_extended = CRUDUserExtended(User)
