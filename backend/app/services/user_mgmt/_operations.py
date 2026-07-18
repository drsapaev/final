"""Operations mixin for UserManagementService. Split from user_management_service.py."""
from __future__ import annotations

from app.services.user_mgmt._base import *  # noqa: F401, F403
from app.services.user_mgmt._base import UserManagementServiceMixinBase


class OperationsMixin(UserManagementServiceMixinBase):
    """Operations methods."""

    def get_user_stats(self, db: Session) -> dict[str, Any]:
        """Получает статистику пользователей"""
        try:
            # Общая статистика
            total_users = db.query(User).count()
            active_users = db.query(User).filter(User.is_active == True).count()
            inactive_users = db.query(User).filter(User.is_active == False).count()

            # Статистика по статусам
            suspended_users = (
                db.query(User)
                .join(UserProfile)
                .filter(UserProfile.status == UserStatus.SUSPENDED)
                .count()
            )
            locked_users = (
                db.query(User)
                .join(UserProfile)
                .filter(UserProfile.locked_until.isnot(None))
                .count()
            )

            # Статистика по ролям
            users_by_role = {}
            for role in ["Admin", "Doctor", "Nurse", "Receptionist", "Patient"]:
                count = db.query(User).filter(User.role == role).count()
                users_by_role[role] = count

            # Пользователи с профилями
            users_with_profiles = db.query(User).join(UserProfile).count()

            # Пользователи с 2FA
            users_with_2fa = (
                db.query(User)
                .filter(User.two_factor_auth.has(totp_enabled=True))
                .count()
            )

            # Недавние регистрации (30 дней)
            thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
            recent_registrations = (
                db.query(User).filter(User.created_at >= thirty_days_ago).count()
            )

            # Недавние входы (24 часа)
            twenty_four_hours_ago = datetime.now(UTC) - timedelta(hours=24)
            recent_logins = (
                db.query(User)
                .join(UserProfile)
                .filter(UserProfile.last_login >= twenty_four_hours_ago)
                .count()
            )

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
                "recent_logins": recent_logins,
            }

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}


    def bulk_action_users(
        self, db: Session, action_data: UserBulkActionRequest, executed_by: int
    ) -> tuple[bool, str, dict[str, Any]]:
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
                        failed_users.append(
                            {"user_id": user_id, "error": "Пользователь не найден"}
                        )
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
                            admin_count = (
                                db.query(User)
                                .filter(
                                    and_(
                                        User.role == "Admin",
                                        User.is_superuser == True,
                                        User.id != user_id,
                                    )
                                )
                                .count()
                            )
                            if admin_count == 0:
                                failed_count += 1
                                failed_users.append(
                                    {
                                        "user_id": user_id,
                                        "error": "Нельзя удалить последнего администратора",
                                    }
                                )
                                continue
                        db.delete(user)

                    # Логируем действие
                    self._log_user_action(
                        db,
                        user_id,
                        action_data.action,
                        f"Массовое действие: {action_data.action}",
                        executed_by,
                    )

                    processed_count += 1

                except Exception as e:
                    failed_count += 1
                    failed_users.append({"user_id": user_id, "error": str(e)})

            db.commit()

            return (
                True,
                f"Обработано {processed_count} пользователей, ошибок: {failed_count}",
                {
                    "processed_count": processed_count,
                    "failed_count": failed_count,
                    "failed_users": failed_users,
                },
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk action: {e}")
            return False, "Внутренняя ошибка", {}


    def update_user_preferences(
        self, db: Session, user_id: int, preferences_data: UserPreferencesUpdate
    ) -> tuple[bool, str]:
        """Обновляет настройки пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"

            _, preferences, _ = self.ensure_user_support_records(db, user)

            # Обновляем настройки
            update_data = preferences_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(preferences, field):
                    setattr(preferences, field, value)

            # Логируем обновление
            self._log_user_action(
                db, user_id, "update_preferences", "Настройки обновлены", user_id
            )

            db.commit()
            return True, "Настройки успешно обновлены"

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user preferences: {e}")
            return False, "Внутренняя ошибка"


    def update_notification_settings(
        self, db: Session, user_id: int, settings_data: UserNotificationSettingsUpdate
    ) -> tuple[bool, str]:
        """Обновляет настройки уведомлений пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "Пользователь не найден"

            _, _, notification_settings = self.ensure_user_support_records(db, user)

            # Обновляем настройки
            update_data = settings_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(notification_settings, field):
                    setattr(notification_settings, field, value)

            # Логируем обновление
            self._log_user_action(
                db,
                user_id,
                "update_notifications",
                "Настройки уведомлений обновлены",
                user_id,
            )

            db.commit()
            return True, "Настройки уведомлений успешно обновлены"

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating notification settings: {e}")
            return False, "Внутренняя ошибка"


    def _log_user_action(
        self,
        db: Session,
        user_id: int,
        action: str,
        description: str,
        executed_by: int,
        resource_type: str = None,
        resource_id: int = None,
        old_values: dict = None,
        new_values: dict = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
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
                user_agent=user_agent,
            )
            db.add(audit_log)
        except Exception as e:
            logger.error(f"Error logging user action: {e}")

    # ===================== ЭКСПОРТ ПОЛЬЗОВАТЕЛЕЙ =====================


    def export_users_background(
        self,
        users: list[User],
        export_data: UserExportRequest,
        current_user_id: int,
        db: Session,
    ):
        """
        Фоновый экспорт пользователей в различных форматах
        """
        try:
            from datetime import datetime
            from pathlib import Path

            # Создаем директорию для экспорта если её нет
            export_dir = Path("exports/users")
            export_dir.mkdir(parents=True, exist_ok=True)

            # Генерируем имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_base = f"users_export_{timestamp}"

            # Подготавливаем данные для экспорта
            export_users_data = []

            for user in users:
                user_data = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                    "updated_at": (
                        user.updated_at.isoformat() if user.updated_at else None
                    ),
                    "last_login": (
                        user.last_login.isoformat() if user.last_login else None
                    ),
                }

                # Добавляем профиль если запрошен
                if (
                    export_data.include_profile
                    and hasattr(user, 'profile')
                    and user.profile
                ):
                    user_data.update(
                        {
                            "full_name": user.profile.full_name,
                            "first_name": user.profile.first_name,
                            "last_name": user.profile.last_name,
                            "phone": user.profile.phone,
                            "birth_date": (
                                user.profile.birth_date.isoformat()
                                if user.profile.birth_date
                                else None
                            ),
                            "gender": user.profile.gender,
                            "address": user.profile.address,
                            "emergency_contact": user.profile.emergency_contact,
                        }
                    )

                # Добавляем настройки если запрошены
                if (
                    export_data.include_preferences
                    and hasattr(user, 'preferences')
                    and user.preferences
                ):
                    user_data.update(
                        {
                            "language": user.preferences.language,
                            "timezone": user.preferences.timezone,
                            "theme": user.preferences.theme,
                            "date_format": user.preferences.date_format,
                            "time_format": user.preferences.time_format,
                        }
                    )

                # Фильтруем поля если указаны
                if export_data.fields:
                    user_data = {
                        k: v for k, v in user_data.items() if k in export_data.fields
                    }

                export_users_data.append(user_data)

            # Экспортируем в зависимости от формата
            file_path = None

            if export_data.format == "csv":
                file_path = export_dir / f"{filename_base}.csv"
                self._export_to_csv(export_users_data, file_path)

            elif export_data.format == "excel":
                file_path = export_dir / f"{filename_base}.xlsx"
                self._export_to_excel(export_users_data, file_path)

            elif export_data.format == "json":
                file_path = export_dir / f"{filename_base}.json"
                self._export_to_json(export_users_data, file_path)

            elif export_data.format == "pdf":
                file_path = export_dir / f"{filename_base}.pdf"
                self._export_to_pdf(export_users_data, file_path)

            # Логируем экспорт
            self._log_user_action(
                db,
                current_user_id,
                "export_users",
                "user_export",
                None,
                f"Экспорт {len(users)} пользователей в формате {export_data.format}",
                metadata={
                    "format": export_data.format,
                    "record_count": len(users),
                    "file_path": str(file_path) if file_path else None,
                    "file_size": (
                        file_path.stat().st_size
                        if file_path and file_path.exists()
                        else 0
                    ),
                },
            )

            logger.info(f"Экспорт пользователей завершен: {file_path}")

        except Exception as e:
            logger.error(f"Ошибка экспорта пользователей: {e}")
            # Логируем ошибку
            self._log_user_action(
                db,
                current_user_id,
                "export_users_error",
                "user_export",
                None,
                "Внутренняя ошибка",
            )


    def _export_to_csv(self, data: list[dict], file_path: Path):
        """Экспорт в CSV формат"""
        if not data:
            return

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)


    def _export_to_json(self, data: list[dict], file_path: Path):
        """Экспорт в JSON формат"""
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(
                {
                    "export_info": {
                        "timestamp": datetime.now().isoformat(),
                        "record_count": len(data),
                        "format": "json",
                    },
                    "users": data,
                },
                jsonfile,
                indent=2,
                ensure_ascii=False,
                default=str,
            )


    def _export_to_excel(self, data: list[dict], file_path: Path):
        """Экспорт в Excel формат"""
        try:
            import pandas as pd

            # Создаем DataFrame
            df = pd.DataFrame(data)

            # Экспортируем в Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Users', index=False)

                # Добавляем информационный лист
                info_df = pd.DataFrame(
                    {
                        'Параметр': ['Дата экспорта', 'Количество записей', 'Формат'],
                        'Значение': [
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            len(data),
                            'Excel',
                        ],
                    }
                )
                info_df.to_excel(writer, sheet_name='Export Info', index=False)

        except ImportError:
            # Если pandas не установлен, используем альтернативный метод
            logger.warning(
                "pandas не установлен, используем альтернативный метод для Excel"
            )
            self._export_to_csv(data, file_path.with_suffix('.csv'))


    def _export_to_pdf(self, data: list[dict], file_path: Path):
        """Экспорт в PDF формат"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            # Создаем PDF документ
            doc = SimpleDocTemplate(str(file_path), pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()

            # Заголовок
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,  # Центрирование
            )
            title = Paragraph("Экспорт пользователей", title_style)
            elements.append(title)

            # Информация об экспорте
            info_style = styles['Normal']
            info = Paragraph(
                f"Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}<br/>Количество записей: {len(data)}",
                info_style,
            )
            elements.append(info)
            elements.append(Spacer(1, 20))

            # Подготавливаем данные для таблицы
            if data:
                # Заголовки
                headers = list(data[0].keys())
                table_data = [headers]

                # Данные (ограничиваем количество для PDF)
                for row in data[:50]:  # Максимум 50 записей для PDF
                    table_data.append([str(row.get(header, '')) for header in headers])

                # Создаем таблицу
                table = Table(table_data)
                table.setStyle(
                    TableStyle(
                        [
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('FONTSIZE', (0, 1), (-1, -1), 8),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )

                elements.append(table)

                if len(data) > 50:
                    note = Paragraph(
                        f"<i>Примечание: Показаны первые 50 записей из {len(data)}</i>",
                        styles['Normal'],
                    )
                    elements.append(Spacer(1, 10))
                    elements.append(note)

            # Генерируем PDF
            doc.build(elements)

        except ImportError:
            logger.warning(
                "reportlab не установлен, используем альтернативный метод для PDF"
            )
            # Создаем простой текстовый файл вместо PDF
            with open(file_path.with_suffix('.txt'), 'w', encoding='utf-8') as f:
                f.write("Экспорт пользователей\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write(f"Количество записей: {len(data)}\n\n")

                for i, user in enumerate(data, 1):
                    f.write(
                        f"{i}. {user.get('username', 'N/A')} ({user.get('email', 'N/A')})\n"
                    )
                    f.write(f"   Роль: {user.get('role', 'N/A')}\n")
                    f.write(f"   Активен: {'Да' if user.get('is_active') else 'Нет'}\n")
                    f.write(f"   Создан: {user.get('created_at', 'N/A')}\n\n")


# Глобальный экземпляр сервиса

_user_management_service: UserManagementService | None = None


def get_user_management_service() -> UserManagementService:
    """Получить экземпляр сервиса управления пользователями"""
    global _user_management_service
    if _user_management_service is None:
        from app.services.user_mgmt import UserManagementService
        _user_management_service = UserManagementService()
    return _user_management_service


