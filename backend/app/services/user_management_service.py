"""
Сервис для управления пользователями
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text

from app.models.user import User
from app.models.user_profile import (
    UserProfile, UserPreferences, UserNotificationSettings, 
    UserRole, UserPermission, UserGroup, UserGroupMember, UserAuditLog,
    UserStatus
)
from app.core.security import get_password_hash, verify_password
from app.schemas.user_management import (
    UserCreateRequest, UserUpdateRequest, UserProfileCreate, UserProfileUpdate,
    UserPreferencesCreate, UserPreferencesUpdate, UserNotificationSettingsCreate,
    UserNotificationSettingsUpdate, UserRoleCreate, UserRoleUpdate,
    UserGroupCreate, UserGroupUpdate, UserGroupMemberCreate,
    UserSearchRequest, UserBulkActionRequest, UserExportRequest
)
import logging

logger = logging.getLogger(__name__)


class UserManagementService:
    """Сервис для управления пользователями"""

    def __init__(self):
        self.default_permissions = {
            "Admin": ["*"],  # Все права
            "Doctor": [
                "patients:read", "patients:write",
                "appointments:read", "appointments:write",
                "emr:read", "emr:write",
                "prescriptions:read", "prescriptions:write",
                "schedules:read", "schedules:write"
            ],
            "Nurse": [
                "patients:read",
                "appointments:read",
                "emr:read",
                "schedules:read"
            ],
            "Receptionist": [
                "patients:read", "patients:write",
                "appointments:read", "appointments:write",
                "schedules:read", "schedules:write",
                "payments:read", "payments:write"
            ],
            "Patient": [
                "profile:read", "profile:write",
                "appointments:read",
                "payments:read"
            ]
        }

    def create_user(self, db: Session, user_data: UserCreateRequest, created_by: int) -> Tuple[bool, str, Optional[User]]:
        """Создает нового пользователя с профилем"""
        try:
            # Проверяем уникальность username и email
            existing_user = db.query(User).filter(
                or_(User.username == user_data.username, User.email == user_data.email)
            ).first()
            
            if existing_user:
                if existing_user.username == user_data.username:
                    return False, "Пользователь с таким именем уже существует", None
                else:
                    return False, "Пользователь с таким email уже существует", None
            
            # Создаем пользователя
            hashed_password = get_password_hash(user_data.password)
            user = User(
                username=user_data.username,
                email=user_data.email,
                hashed_password=hashed_password,
                role=user_data.role,
                is_active=user_data.is_active,
                is_superuser=user_data.is_superuser
            )
            db.add(user)
            db.flush()  # Получаем ID пользователя
            
            # Создаем профиль
            profile = UserProfile(
                user_id=user.id,
                full_name=user_data.full_name,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                phone=user_data.phone,
                status=UserStatus.ACTIVE if user_data.is_active else UserStatus.INACTIVE
            )
            db.add(profile)
            db.flush()  # Получаем ID профиля
            
            # Создаем настройки
            preferences = UserPreferences(
                user_id=user.id,
                profile_id=profile.id
            )
            db.add(preferences)
            
            # Создаем настройки уведомлений
            notification_settings = UserNotificationSettings(
                user_id=user.id,
                profile_id=profile.id
            )
            db.add(notification_settings)
            
            # Логируем создание
            self._log_user_action(db, user.id, "create", "Пользователь создан", created_by)
            
            db.commit()
            return True, "Пользователь успешно создан", user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            return False, f"Ошибка создания пользователя: {str(e)}", None

    def update_user(self, db: Session, user_id: int, user_data: UserUpdateRequest, updated_by: int) -> Tuple[bool, str]:
        """Обновляет пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"
            
            # Обновляем основные поля
            update_data = user_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)
            
            # Обновляем профиль, если есть данные
            if user.profile:
                profile_data = {k: v for k, v in update_data.items() 
                              if k in ['full_name', 'first_name', 'last_name', 'phone']}
                if profile_data:
                    for field, value in profile_data.items():
                        if hasattr(user.profile, field):
                            setattr(user.profile, field, value)
            
            # Логируем обновление
            self._log_user_action(db, user_id, "update", "Пользователь обновлен", updated_by)
            
            db.commit()
            return True, "Пользователь успешно обновлен"
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user: {e}")
            return False, f"Ошибка обновления пользователя: {str(e)}"

    def delete_user(self, db: Session, user_id: int, deleted_by: int, transfer_to: Optional[int] = None) -> Tuple[bool, str]:
        """Удаляет пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"
            
            # Проверяем, что не удаляем последнего администратора
            if user.role == "Admin" and user.is_superuser:
                admin_count = db.query(User).filter(
                    and_(User.role == "Admin", User.is_superuser == True, User.id != user_id)
                ).count()
                if admin_count == 0:
                    return False, "Нельзя удалить последнего администратора"
            
            # Если указан пользователь для передачи данных
            if transfer_to:
                transfer_user = db.query(User).filter(User.id == transfer_to).first()
                if not transfer_user:
                    return False, "Пользователь для передачи данных не найден"
                
                # TODO: Реализовать передачу данных (назначения, записи и т.д.)
                pass
            
            # Логируем удаление
            self._log_user_action(db, user_id, "delete", "Пользователь удален", deleted_by)
            
            # Удаляем пользователя (каскадное удаление)
            db.delete(user)
            db.commit()
            
            return True, "Пользователь успешно удален"
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting user: {e}")
            return False, f"Ошибка удаления пользователя: {str(e)}"

    def get_user_profile(self, db: Session, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает полный профиль пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            profile_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "created_at": user.created_at if hasattr(user, 'created_at') else None,
                "updated_at": user.updated_at if hasattr(user, 'updated_at') else None
            }
            
            # Добавляем данные профиля
            if user.profile:
                profile_data.update({
                    "full_name": user.profile.full_name,
                    "first_name": user.profile.first_name,
                    "last_name": user.profile.last_name,
                    "phone": user.profile.phone,
                    "phone_verified": user.profile.phone_verified,
                    "email_verified": user.profile.email_verified,
                    "date_of_birth": user.profile.date_of_birth,
                    "gender": user.profile.gender,
                    "nationality": user.profile.nationality,
                    "language": user.profile.language,
                    "timezone": user.profile.timezone,
                    "bio": user.profile.bio,
                    "website": user.profile.website,
                    "avatar_url": user.profile.avatar_url,
                    "social_links": user.profile.social_links,
                    "status": user.profile.status,
                    "last_login": user.profile.last_login,
                    "last_activity": user.profile.last_activity,
                    "login_count": user.profile.login_count,
                    "failed_login_attempts": user.profile.failed_login_attempts,
                    "locked_until": user.profile.locked_until
                })
            
            # Добавляем настройки
            if user.preferences:
                profile_data["preferences"] = {
                    "theme": user.preferences.theme,
                    "language": user.preferences.language,
                    "timezone": user.preferences.timezone,
                    "date_format": user.preferences.date_format,
                    "time_format": user.preferences.time_format,
                    "email_notifications": user.preferences.email_notifications,
                    "sms_notifications": user.preferences.sms_notifications,
                    "push_notifications": user.preferences.push_notifications,
                    "desktop_notifications": user.preferences.desktop_notifications,
                    "working_hours_start": user.preferences.working_hours_start,
                    "working_hours_end": user.preferences.working_hours_end,
                    "working_days": user.preferences.working_days,
                    "break_duration": user.preferences.break_duration,
                    "dashboard_layout": user.preferences.dashboard_layout,
                    "sidebar_collapsed": user.preferences.sidebar_collapsed,
                    "compact_mode": user.preferences.compact_mode,
                    "show_tooltips": user.preferences.show_tooltips,
                    "session_timeout": user.preferences.session_timeout,
                    "require_2fa": user.preferences.require_2fa,
                    "auto_logout": user.preferences.auto_logout
                }
            
            # Добавляем настройки уведомлений
            if user.notification_settings:
                profile_data["notification_settings"] = {
                    "email_appointment_reminder": user.notification_settings.email_appointment_reminder,
                    "email_appointment_cancellation": user.notification_settings.email_appointment_cancellation,
                    "email_appointment_confirmation": user.notification_settings.email_appointment_confirmation,
                    "email_payment_receipt": user.notification_settings.email_payment_receipt,
                    "email_payment_reminder": user.notification_settings.email_payment_reminder,
                    "email_system_updates": user.notification_settings.email_system_updates,
                    "email_security_alerts": user.notification_settings.email_security_alerts,
                    "email_newsletter": user.notification_settings.email_newsletter,
                    "sms_appointment_reminder": user.notification_settings.sms_appointment_reminder,
                    "sms_appointment_cancellation": user.notification_settings.sms_appointment_cancellation,
                    "sms_appointment_confirmation": user.notification_settings.sms_appointment_confirmation,
                    "sms_payment_receipt": user.notification_settings.sms_payment_receipt,
                    "sms_emergency": user.notification_settings.sms_emergency,
                    "push_appointment_reminder": user.notification_settings.push_appointment_reminder,
                    "push_appointment_cancellation": user.notification_settings.push_appointment_cancellation,
                    "push_appointment_confirmation": user.notification_settings.push_appointment_confirmation,
                    "push_payment_receipt": user.notification_settings.push_payment_receipt,
                    "push_system_updates": user.notification_settings.push_system_updates,
                    "push_security_alerts": user.notification_settings.push_security_alerts,
                    "reminder_time_before": user.notification_settings.reminder_time_before,
                    "quiet_hours_start": user.notification_settings.quiet_hours_start,
                    "quiet_hours_end": user.notification_settings.quiet_hours_end,
                    "weekend_notifications": user.notification_settings.weekend_notifications
                }
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    def search_users(self, db: Session, search_params: UserSearchRequest) -> Tuple[List[Dict[str, Any]], int]:
        """Поиск пользователей с фильтрацией"""
        try:
            query = db.query(User)
            
            # Фильтр по тексту
            if search_params.query:
                query = query.join(UserProfile, User.id == UserProfile.user_id, isouter=True).filter(
                    or_(
                        User.username.ilike(f"%{search_params.query}%"),
                        User.email.ilike(f"%{search_params.query}%"),
                        UserProfile.full_name.ilike(f"%{search_params.query}%"),
                        UserProfile.first_name.ilike(f"%{search_params.query}%"),
                        UserProfile.last_name.ilike(f"%{search_params.query}%")
                    )
                )
            
            # Фильтр по роли
            if search_params.role:
                query = query.filter(User.role == search_params.role)
            
            # Фильтр по статусу
            if search_params.status:
                query = query.join(UserProfile).filter(UserProfile.status == search_params.status)
            
            # Фильтр по активности
            if search_params.is_active is not None:
                query = query.filter(User.is_active == search_params.is_active)
            
            # Фильтр по суперпользователю
            if search_params.is_superuser is not None:
                query = query.filter(User.is_superuser == search_params.is_superuser)
            
            # Фильтр по дате создания
            if search_params.created_from:
                query = query.filter(User.created_at >= search_params.created_from)
            if search_params.created_to:
                query = query.filter(User.created_at <= search_params.created_to)
            
            # Фильтр по последнему входу
            if search_params.last_login_from:
                query = query.join(UserProfile).filter(UserProfile.last_login >= search_params.last_login_from)
            if search_params.last_login_to:
                query = query.join(UserProfile).filter(UserProfile.last_login <= search_params.last_login_to)
            
            # Подсчет общего количества
            total = query.count()
            
            # Пагинация
            offset = (search_params.page - 1) * search_params.per_page
            users = query.offset(offset).limit(search_params.per_page).all()
            
            # Формируем результат
            result = []
            for user in users:
                user_data = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser,
                    "created_at": user.created_at if hasattr(user, 'created_at') else None,
                    "updated_at": user.updated_at if hasattr(user, 'updated_at') else None
                }
                
                if user.profile:
                    user_data.update({
                        "full_name": user.profile.full_name,
                        "first_name": user.profile.first_name,
                        "last_name": user.profile.last_name,
                        "phone": user.profile.phone,
                        "status": user.profile.status,
                        "last_login": user.profile.last_login,
                        "last_activity": user.profile.last_activity
                    })
                
                result.append(user_data)
            
            return result, total
            
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return [], 0

    def get_user_stats(self, db: Session) -> Dict[str, Any]:
        """Получает статистику пользователей"""
        try:
            # Общая статистика
            total_users = db.query(User).count()
            active_users = db.query(User).filter(User.is_active == True).count()
            inactive_users = db.query(User).filter(User.is_active == False).count()
            
            # Статистика по статусам
            suspended_users = db.query(User).join(UserProfile).filter(
                UserProfile.status == UserStatus.SUSPENDED
            ).count()
            locked_users = db.query(User).join(UserProfile).filter(
                UserProfile.locked_until.isnot(None)
            ).count()
            
            # Статистика по ролям
            users_by_role = {}
            for role in ["Admin", "Doctor", "Nurse", "Receptionist", "Patient"]:
                count = db.query(User).filter(User.role == role).count()
                users_by_role[role] = count
            
            # Пользователи с профилями
            users_with_profiles = db.query(User).join(UserProfile).count()
            
            # Пользователи с 2FA
            users_with_2fa = db.query(User).filter(
                User.two_factor_auth.has(totp_enabled=True)
            ).count()
            
            # Недавние регистрации (30 дней)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_registrations = db.query(User).filter(
                User.created_at >= thirty_days_ago
            ).count()
            
            # Недавние входы (24 часа)
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            recent_logins = db.query(User).join(UserProfile).filter(
                UserProfile.last_login >= twenty_four_hours_ago
            ).count()
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": inactive_users,
                "suspended_users": suspended_users,
                "locked_users": locked_users,
                "users_by_role": users_by_role,
                "users_with_profiles": users_with_profiles,
                "users_with_2fa": users_with_2fa,
                "recent_registrations": recent_registrations,
                "recent_logins": recent_logins
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}

    def bulk_action_users(self, db: Session, action_data: UserBulkActionRequest, executed_by: int) -> Tuple[bool, str, Dict[str, Any]]:
        """Выполняет массовые действия с пользователями"""
        try:
            processed_count = 0
            failed_count = 0
            failed_users = []
            
            for user_id in action_data.user_ids:
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if not user:
                        failed_count += 1
                        failed_users.append({"user_id": user_id, "error": "Пользователь не найден"})
                        continue
                    
                    if action_data.action == "activate":
                        user.is_active = True
                        if user.profile:
                            user.profile.status = UserStatus.ACTIVE
                    elif action_data.action == "deactivate":
                        user.is_active = False
                        if user.profile:
                            user.profile.status = UserStatus.INACTIVE
                    elif action_data.action == "suspend":
                        if user.profile:
                            user.profile.status = UserStatus.SUSPENDED
                    elif action_data.action == "unsuspend":
                        if user.profile:
                            user.profile.status = UserStatus.ACTIVE
                    elif action_data.action == "change_role":
                        if action_data.role:
                            user.role = action_data.role
                    elif action_data.action == "delete":
                        # Проверяем, что не удаляем последнего администратора
                        if user.role == "Admin" and user.is_superuser:
                            admin_count = db.query(User).filter(
                                and_(User.role == "Admin", User.is_superuser == True, User.id != user_id)
                            ).count()
                            if admin_count == 0:
                                failed_count += 1
                                failed_users.append({"user_id": user_id, "error": "Нельзя удалить последнего администратора"})
                                continue
                        db.delete(user)
                    
                    # Логируем действие
                    self._log_user_action(db, user_id, action_data.action, 
                                        f"Массовое действие: {action_data.action}", executed_by)
                    
                    processed_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_users.append({"user_id": user_id, "error": str(e)})
            
            db.commit()
            
            return True, f"Обработано {processed_count} пользователей, ошибок: {failed_count}", {
                "processed_count": processed_count,
                "failed_count": failed_count,
                "failed_users": failed_users
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk action: {e}")
            return False, f"Ошибка массового действия: {str(e)}", {}

    def update_user_preferences(self, db: Session, user_id: int, preferences_data: UserPreferencesUpdate) -> Tuple[bool, str]:
        """Обновляет настройки пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"
            
            if not user.preferences:
                # Создаем настройки, если их нет
                user.preferences = UserPreferences(
                    user_id=user_id,
                    profile_id=user.profile.id if user.profile else None
                )
                db.add(user.preferences)
            
            # Обновляем настройки
            update_data = preferences_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(user.preferences, field):
                    setattr(user.preferences, field, value)
            
            # Логируем обновление
            self._log_user_action(db, user_id, "update_preferences", "Настройки обновлены", user_id)
            
            db.commit()
            return True, "Настройки успешно обновлены"
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user preferences: {e}")
            return False, f"Ошибка обновления настроек: {str(e)}"

    def update_notification_settings(self, db: Session, user_id: int, settings_data: UserNotificationSettingsUpdate) -> Tuple[bool, str]:
        """Обновляет настройки уведомлений пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"
            
            if not user.notification_settings:
                # Создаем настройки, если их нет
                user.notification_settings = UserNotificationSettings(
                    user_id=user_id,
                    profile_id=user.profile.id if user.profile else None
                )
                db.add(user.notification_settings)
            
            # Обновляем настройки
            update_data = settings_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(user.notification_settings, field):
                    setattr(user.notification_settings, field, value)
            
            # Логируем обновление
            self._log_user_action(db, user_id, "update_notifications", "Настройки уведомлений обновлены", user_id)
            
            db.commit()
            return True, "Настройки уведомлений успешно обновлены"
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating notification settings: {e}")
            return False, f"Ошибка обновления настроек уведомлений: {str(e)}"

    def _log_user_action(self, db: Session, user_id: int, action: str, description: str, executed_by: int, 
                        resource_type: str = None, resource_id: int = None, old_values: Dict = None, 
                        new_values: Dict = None, ip_address: str = None, user_agent: str = None):
        """Логирует действие пользователя"""
        try:
            audit_log = UserAuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                description=description,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(audit_log)
        except Exception as e:
            logger.error(f"Error logging user action: {e}")


# Глобальный экземпляр сервиса
user_management_service = UserManagementService()

def get_user_management_service() -> UserManagementService:
    """Получить экземпляр сервиса управления пользователями"""
    return user_management_service

