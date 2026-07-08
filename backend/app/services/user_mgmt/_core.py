"""Core mixin for UserManagementService. Split from user_management_service.py."""
from __future__ import annotations
from app.services.user_mgmt._base import *  # noqa: F401, F403
from app.services.user_mgmt._base import UserManagementServiceMixinBase


class CoreMixin(UserManagementServiceMixinBase):
    """Core methods."""

    def __init__(self):
        # TODO(DB_ROLES): Move permissions to role_permissions table in Phase 4
        self.default_permissions = {
            "Admin": ["*"],  # Все права
            "Doctor": [
                "patients:read",
                "patients:write",
                "appointments:read",
                "appointments:write",
                "emr:read",
                "emr:write",
                "prescriptions:read",
                "prescriptions:write",
                "schedules:read",
                "schedules:write",
            ],
            "Nurse": [
                "patients:read",
                "appointments:read",
                "emr:read",
                "schedules:read",
            ],
            "Receptionist": [
                "patients:read",
                "patients:write",
                "appointments:read",
                "appointments:write",
                "schedules:read",
                "schedules:write",
                "payments:read",
                "payments:write",
            ],
            "Cashier": [
                "payments:read",
                "payments:write",
                "patients:read",
                "appointments:read",
            ],
            "Lab": [
                "patients:read",
                "emr:read",
                "lab_results:read",
                "lab_results:write",
            ],
            "Patient": [
                "profile:read",
                "profile:write",
                "appointments:read",
                "payments:read",
            ],
        }


    def _count_other_active_admins(self, db: Session, exclude_user_id: int) -> int:
        return (
            db.query(User)
            .filter(
                and_(
                    User.role == "Admin",
                    User.is_active == True,
                    User.id != exclude_user_id,
                )
            )
            .count()
        )


    def _count_other_active_superadmins(self, db: Session, exclude_user_id: int) -> int:
        return (
            db.query(User)
            .filter(
                and_(
                    User.role == "Admin",
                    User.is_active == True,
                    User.is_superuser == True,
                    User.id != exclude_user_id,
                )
            )
            .count()
        )


    def ensure_user_support_records(
        self, db: Session, user_or_id: User | int
    ) -> tuple[UserProfile, UserPreferences, UserNotificationSettings]:
        """Создает профиль и настройки пользователя, если они отсутствуют."""
        user = user_or_id
        if isinstance(user_or_id, int):
            user = db.query(User).filter(User.id == user_or_id).first()

        if not user:
            raise ValueError("Пользователь не найден")

        changed = False
        target_status = UserStatus.ACTIVE if user.is_active else UserStatus.INACTIVE

        profile = user.profile
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                full_name=user.full_name,
                status=target_status,
            )
            db.add(profile)
            db.flush()
            changed = True
            logger.info(
                "[FIX:USER-BOOTSTRAP] Created missing user_profile for user_id=%s",
                user.id,
            )
        else:
            if not profile.full_name and user.full_name:
                profile.full_name = user.full_name
                changed = True
            if profile.status != target_status:
                profile.status = target_status
                changed = True

        preferences = user.preferences
        if not preferences:
            preferences = UserPreferences(
                user_id=user.id,
                profile_id=profile.id,
            )
            db.add(preferences)
            changed = True
            logger.info(
                "[FIX:USER-BOOTSTRAP] Created missing user_preferences for user_id=%s",
                user.id,
            )
        elif preferences.profile_id != profile.id:
            preferences.profile_id = profile.id
            changed = True

        notification_settings = user.notification_settings
        if not notification_settings:
            notification_settings = UserNotificationSettings(
                user_id=user.id,
                profile_id=profile.id,
            )
            db.add(notification_settings)
            changed = True
            logger.info(
                "[FIX:USER-BOOTSTRAP] Created missing user_notification_settings for user_id=%s",
                user.id,
            )
        elif notification_settings.profile_id != profile.id:
            notification_settings.profile_id = profile.id
            changed = True

        if changed:
            db.commit()
            db.refresh(user)
            profile = user.profile
            preferences = user.preferences
            notification_settings = user.notification_settings

        return profile, preferences, notification_settings


    def create_user(
        self, db: Session, user_data: UserCreateRequest, created_by: int
    ) -> tuple[bool, str, User | None]:
        """Создает нового пользователя с профилем"""
        try:
            # Проверяем уникальность username и email
            existing_user = (
                db.query(User)
                .filter(
                    or_(
                        User.username == user_data.username,
                        User.email == user_data.email,
                    )
                )
                .first()
            )

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
                is_superuser=user_data.is_superuser,
                must_change_password=getattr(user_data, 'must_change_password', False),
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
                status=(
                    UserStatus.ACTIVE if user_data.is_active else UserStatus.INACTIVE
                ),
            )
            db.add(profile)
            db.flush()  # Получаем ID профиля

            # Создаем настройки
            preferences = UserPreferences(user_id=user.id, profile_id=profile.id)
            db.add(preferences)

            # Создаем настройки уведомлений
            notification_settings = UserNotificationSettings(
                user_id=user.id, profile_id=profile.id
            )
            db.add(notification_settings)

            # Логируем создание
            self._log_user_action(
                db, user.id, "create", "Пользователь создан", created_by
            )

            db.commit()
            # Обновляем объекты, чтобы получить все поля (id, created_at, updated_at)
            db.refresh(user)
            db.refresh(profile)
            db.refresh(preferences)
            db.refresh(notification_settings)

            return True, "Пользователь успешно создан", user

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            return False, "Внутренняя ошибка", None


    def update_user(
        self, db: Session, user_id: int, user_data: UserUpdateRequest, updated_by: int
    ) -> tuple[bool, str]:
        """Обновляет пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"

            # Обновляем основные поля
            update_data = user_data.model_dump(exclude_unset=True)

            target_is_active = update_data.get("is_active", user.is_active)
            target_role = update_data.get("role", user.role)
            target_is_superuser = update_data.get("is_superuser", user.is_superuser)

            if updated_by == user_id and user.is_active and target_is_active is False:
                return (
                    False,
                    "Нельзя деактивировать текущую учётную запись из активной сессии. "
                    "Войдите под другим администратором и выполните это действие оттуда.",
                )

            if updated_by == user_id and user.role == "Admin" and target_role != "Admin":
                return (
                    False,
                    "Нельзя снять у текущей учётной записи роль администратора из активной сессии. "
                    "Сначала войдите под другим администратором.",
                )

            if updated_by == user_id and user.is_superuser and target_is_superuser is False:
                return (
                    False,
                    "Нельзя снять права суперпользователя у текущей учётной записи из активной сессии. "
                    "Сначала войдите под другим администратором.",
                )

            superadmin_privileges_removed = (
                user.role == "Admin"
                and user.is_superuser
                and user.is_active
                and (
                    target_is_active is False
                    or target_role != "Admin"
                    or target_is_superuser is False
                )
            )
            if (
                superadmin_privileges_removed
                and self._count_other_active_superadmins(db, user_id) == 0
            ):
                return (
                    False,
                    "Нельзя деактивировать или понизить последнего активного суперпользователя"
                )

            admin_privileges_removed = (
                user.role == "Admin"
                and user.is_active
                and (target_is_active is False or target_role != "Admin")
            )
            if admin_privileges_removed and self._count_other_active_admins(db, user_id) == 0:
                return False, "Нельзя деактивировать или понизить последнего активного администратора"

            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)

            # Обновляем профиль, если есть данные
            if user.profile:
                profile_data = {
                    k: v
                    for k, v in update_data.items()
                    if k in ['full_name', 'first_name', 'last_name', 'phone']
                }
                if profile_data:
                    for field, value in profile_data.items():
                        if hasattr(user.profile, field):
                            setattr(user.profile, field, value)

            # Логируем обновление
            self._log_user_action(
                db, user_id, "update", "Пользователь обновлен", updated_by
            )

            db.commit()
            return True, "Пользователь успешно обновлен"

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user: {e}")
            return False, "Внутренняя ошибка"


    def delete_user(
        self,
        db: Session,
        user_id: int,
        deleted_by: int,
        transfer_to: int | None = None,
    ) -> tuple[bool, str]:
        """Удаляет пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"

            if deleted_by == user_id:
                return (
                    False,
                    "Нельзя удалить текущую учётную запись из активной сессии. "
                    "Войдите под другим администратором и выполните это действие оттуда.",
                )

            if (
                user.role == "Admin"
                and user.is_superuser
                and user.is_active
                and self._count_other_active_superadmins(db, user_id) == 0
            ):
                return False, "Нельзя удалить последнего активного суперпользователя"

            if (
                user.role == "Admin"
                and user.is_active
                and self._count_other_active_admins(db, user_id) == 0
            ):
                return False, "Нельзя удалить последнего активного администратора"

            # Если указан пользователь для передачи данных
            if transfer_to:
                transfer_user = db.query(User).filter(User.id == transfer_to).first()
                if not transfer_user:
                    return False, "Пользователь для передачи данных не найден"

                # TODO: Реализовать передачу данных (назначения, записи и т.д.)
                pass

            # Логируем удаление
            self._log_user_action(
                db, user_id, "delete", "Пользователь удален", deleted_by
            )

            # Удаляем пользователя (каскадное удаление)
            db.delete(user)
            db.commit()

            return True, "Пользователь успешно удален"

        except IntegrityError:
            db.rollback()
            return False, "Невозможно удалить пользователя, так как существуют связанные данные (история действий, записи, платежи). Рекомендуется деактивировать пользователя вместо удаления."

        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting user: {e}")
            return False, "Внутренняя ошибка"


    def get_user_profile(self, db: Session, user_id: int) -> dict[str, Any] | None:
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
                "updated_at": user.updated_at if hasattr(user, 'updated_at') else None,
            }

            # Добавляем данные профиля
            if user.profile:
                profile_data.update(
                    {
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
                        "locked_until": user.profile.locked_until,
                    }
                )

            # Добавляем настройки
            if user.preferences:
                profile_data["preferences"] = {
                    "id": user.preferences.id,
                    "user_id": user.preferences.user_id,
                    "profile_id": user.preferences.profile_id,
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
                    "auto_logout": user.preferences.auto_logout,
                    "created_at": getattr(user.preferences, 'created_at', None),
                    "updated_at": getattr(user.preferences, 'updated_at', None),
                }

            # Добавляем настройки уведомлений
            if user.notification_settings:
                profile_data["notification_settings"] = {
                    "id": user.notification_settings.id,
                    "user_id": user.notification_settings.user_id,
                    "profile_id": user.notification_settings.profile_id,
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
                    "weekend_notifications": user.notification_settings.weekend_notifications,
                    "created_at": getattr(
                        user.notification_settings, 'created_at', None
                    ),
                    "updated_at": getattr(
                        user.notification_settings, 'updated_at', None
                    ),
                }

            return profile_data

        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None


    def search_users(
        self, db: Session, search_params: UserSearchRequest
    ) -> tuple[list[dict[str, Any]], int]:
        """Поиск пользователей с фильтрацией"""
        try:
            query = db.query(User)

            # Фильтр по тексту
            if search_params.query:
                query = query.join(
                    UserProfile, User.id == UserProfile.user_id, isouter=True
                ).filter(
                    or_(
                        User.username.ilike(f"%{search_params.query}%"),
                        User.email.ilike(f"%{search_params.query}%"),
                        UserProfile.full_name.ilike(f"%{search_params.query}%"),
                        UserProfile.first_name.ilike(f"%{search_params.query}%"),
                        UserProfile.last_name.ilike(f"%{search_params.query}%"),
                    )
                )

            # Фильтр по роли
            if search_params.role:
                query = query.filter(User.role == search_params.role)

            # Фильтр по статусу
            if search_params.status:
                query = query.join(UserProfile).filter(
                    UserProfile.status == search_params.status
                )

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
                query = query.join(UserProfile).filter(
                    UserProfile.last_login >= search_params.last_login_from
                )
            if search_params.last_login_to:
                query = query.join(UserProfile).filter(
                    UserProfile.last_login <= search_params.last_login_to
                )

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
                    "created_at": (
                        user.created_at if hasattr(user, 'created_at') else None
                    ),
                    "updated_at": (
                        user.updated_at if hasattr(user, 'updated_at') else None
                    ),
                }

                if user.profile:
                    # Безопасно сериализуем Enum и другие поля
                    status_value = None
                    try:
                        status_obj = getattr(user.profile, "status", None)
                        if status_obj is not None:
                            status_value = getattr(status_obj, "value", None) or str(
                                status_obj
                            )
                    except Exception:
                        status_value = None

                    user_data.update(
                        {
                            "full_name": user.profile.full_name,
                            "first_name": user.profile.first_name,
                            "last_name": user.profile.last_name,
                            "phone": user.profile.phone,
                            "status": status_value,
                            "last_login": user.profile.last_login,
                            "last_activity": user.profile.last_activity,
                        }
                    )

                result.append(user_data)

            return result, total

        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return [], 0


