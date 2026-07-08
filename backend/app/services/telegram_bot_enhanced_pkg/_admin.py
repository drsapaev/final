"""Admin mixin for EnhancedTelegramBotService.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg._base import *  # noqa: F401, F403
from app.services.telegram_bot_enhanced_pkg._base import EnhancedTelegramBotServiceMixinBase

class AdminMixin(EnhancedTelegramBotServiceMixinBase):
    """Admin methods for EnhancedTelegramBotService."""

    async def _handle_admin_stats(self, chat_id: int, telegram_user, db: Session):
        """Статистика клиники"""
        try:
            today = date.today()

            # Статистика за сегодня
            appointments_today = (
                db.query(Appointment)
                .filter(func.date(Appointment.appointment_date) == today)
                .count()
            )

            patients_today = (
                db.query(Patient).filter(func.date(Patient.created_at) == today).count()
            )

            # Статистика очередей
            active_queues = (
                db.query(DailyQueue)
                .filter(and_(DailyQueue.day == today, DailyQueue.active == True))
                .count()
            )

            # Общая статистика
            total_patients = db.query(Patient).count()
            total_appointments = db.query(Appointment).count()
            total_doctors = db.query(Doctor).count()
            total_services = db.query(Service).count()

            message = f"""📊 **Статистика клиники**

🗓 **Сегодня ({today.strftime('%d.%m.%Y')}):**
• Записей: {appointments_today}
• Новых пациентов: {patients_today}
• Активных очередей: {active_queues}

📈 **Общая статистика:**
• Всего пациентов: {total_patients}
• Всего записей: {total_appointments}
• Врачей: {total_doctors}
• Услуг: {total_services}

🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"""

            await self._send_message(chat_id, message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_queues(self, chat_id: int, telegram_user, db: Session):
        """Управление очередями"""
        try:
            today = date.today()

            queues = db.query(DailyQueue).filter(DailyQueue.day == today).all()

            if not queues:
                await self._send_message(chat_id, "📋 Сегодня нет активных очередей")
                return

            message = "📋 **Очереди на сегодня:**\\n\\n"

            for queue in queues:
                doctor_name = queue.doctor.full_name if queue.doctor else "Неизвестно"
                status = "🟢 Активна" if queue.active else "🔴 Закрыта"

                message += f"👨‍⚕️ **{doctor_name}**\\n"
                message += f"• Статус: {status}\\n"
                message += f"• Всего номеров: {queue.total_numbers}\\n"
                message += f"• Текущий номер: {queue.current_number}\\n"
                message += (
                    f"• В очереди: {queue.total_numbers - queue.current_number}\\n\\n"
                )

            # Добавляем кнопки управления
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔄 Обновить", "callback_data": "admin_queues_refresh"}],
                    [
                        {
                            "text": "⏸ Приостановить все",
                            "callback_data": "admin_queues_pause",
                        }
                    ],
                    [
                        {
                            "text": "▶️ Запустить все",
                            "callback_data": "admin_queues_resume",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка получения очередей: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_patients(self, chat_id: int, telegram_user, db: Session):
        """Управление пациентами"""
        try:
            today = date.today()

            # Новые пациенты за сегодня
            new_patients = (
                db.query(Patient)
                .filter(func.date(Patient.created_at) == today)
                .limit(10)
                .all()
            )

            message = f"👥 **Новые пациенты за сегодня ({len(new_patients)}):**\\n\\n"

            if new_patients:
                for patient in new_patients:
                    created_time = patient.created_at.strftime('%H:%M')
                    message += f"• {patient.full_name} ({created_time})\\n"
                    if patient.phone:
                        message += f"  📞 {patient.phone}\\n"
                    message += "\\n"
            else:
                message += "Сегодня новых пациентов нет"

            # Кнопки управления
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔍 Поиск пациента",
                            "callback_data": "admin_patient_search",
                        }
                    ],
                    [
                        {
                            "text": "📊 Статистика пациентов",
                            "callback_data": "admin_patient_stats",
                        }
                    ],
                    [
                        {
                            "text": "📋 Экспорт данных",
                            "callback_data": "admin_patient_export",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка получения пациентов: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_appointments(
        self, chat_id: int, telegram_user, db: Session
    ):
        """Управление записями"""
        try:
            today = date.today()

            # Записи на сегодня
            appointments_today = (
                db.query(Appointment)
                .filter(func.date(Appointment.appointment_date) == today)
                .all()
            )

            # Группируем по статусам
            status_counts = {}
            for appointment in appointments_today:
                status = appointment.status or "pending"
                status_counts[status] = status_counts.get(status, 0) + 1

            message = f"📅 **Записи на сегодня ({len(appointments_today)}):**\\n\\n"

            status_icons = {
                "pending": "⏳",
                "confirmed": "✅",
                "completed": "✅",
                "cancelled": "❌",
                "no_show": "👻",
            }

            status_names = {
                "pending": "Ожидают",
                "confirmed": "Подтверждены",
                "completed": "Завершены",
                "cancelled": "Отменены",
                "no_show": "Не явились",
            }

            for status, count in status_counts.items():
                icon = status_icons.get(status, "📋")
                name = status_names.get(status, status)
                message += f"{icon} {name}: {count}\\n"

            # Кнопки управления
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📋 Список записей",
                            "callback_data": "admin_appointments_list",
                        }
                    ],
                    [
                        {
                            "text": "📊 Статистика",
                            "callback_data": "admin_appointments_stats",
                        }
                    ],
                    [
                        {
                            "text": "📞 Напомнить пациентам",
                            "callback_data": "admin_appointments_remind",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка получения записей: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_notifications(
        self, chat_id: int, telegram_user, db: Session
    ):
        """Управление уведомлениями"""
        try:
            message = """📢 **Управление уведомлениями**

Выберите тип уведомления:"""

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📱 SMS уведомления",
                            "callback_data": "admin_notify_sms",
                        }
                    ],
                    [
                        {
                            "text": "📧 Email уведомления",
                            "callback_data": "admin_notify_email",
                        }
                    ],
                    [
                        {
                            "text": "🤖 Telegram уведомления",
                            "callback_data": "admin_notify_telegram",
                        }
                    ],
                    [
                        {
                            "text": "📊 Статистика отправок",
                            "callback_data": "admin_notify_stats",
                        }
                    ],
                    [{"text": "⚙️ Настройки", "callback_data": "admin_notify_settings"}],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка управления уведомлениями: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_doctors(self, chat_id: int, telegram_user, db: Session):
        """Управление врачами"""
        try:
            # Получаем всех врачей
            doctors = crud_doctor.get_doctors(db, active_only=True)

            message = f"👨‍⚕️ **Управление врачами ({len(doctors)}):**\\n\\n"

            if doctors:
                for doctor in doctors[:10]:  # Показываем первых 10
                    status = "🟢 Активен" if doctor.is_active else "🔴 Неактивен"
                    message += f"• **{doctor.full_name}**\\n"
                    message += f"  {status} | {doctor.specialty or 'Специальность не указана'}\\n"
                    if doctor.phone:
                        message += f"  📞 {doctor.phone}\\n"
                    message += "\\n"

                if len(doctors) > 10:
                    message += f"... и еще {len(doctors) - 10} врачей\\n"
            else:
                message += "Врачи не найдены"

            # Кнопки управления
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "👨‍⚕️ Добавить врача",
                            "callback_data": "admin_doctor_add",
                        }
                    ],
                    [
                        {
                            "text": "📊 Статистика врачей",
                            "callback_data": "admin_doctor_stats",
                        }
                    ],
                    [
                        {
                            "text": "📋 Расписание",
                            "callback_data": "admin_doctor_schedule",
                        }
                    ],
                    [
                        {
                            "text": "📞 Связаться с врачами",
                            "callback_data": "admin_doctor_contact",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка получения врачей: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_services(self, chat_id: int, telegram_user, db: Session):
        """Управление услугами"""
        try:
            # Получаем все услуги
            services = crud_service.get_services(db, active_only=True)

            message = f"💊 **Управление услугами ({len(services)}):**\\n\\n"

            if services:
                for service in services[:10]:  # Показываем первых 10
                    status = "🟢 Активна" if service.is_active else "🔴 Неактивна"
                    message += f"• **{service.name}**\\n"
                    message += f"  {status} | {service.price:,} сум\\n"
                    if service.description:
                        message += f"  📝 {service.description[:50]}...\\n"
                    message += "\\n"

                if len(services) > 10:
                    message += f"... и еще {len(services) - 10} услуг\\n"
            else:
                message += "Услуги не найдены"

            # Кнопки управления
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "💊 Добавить услугу",
                            "callback_data": "admin_service_add",
                        }
                    ],
                    [
                        {
                            "text": "📊 Статистика услуг",
                            "callback_data": "admin_service_stats",
                        }
                    ],
                    [
                        {
                            "text": "💰 Управление ценами",
                            "callback_data": "admin_service_prices",
                        }
                    ],
                    [
                        {
                            "text": "📋 Категории",
                            "callback_data": "admin_service_categories",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка получения услуг: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_reports(self, chat_id: int, telegram_user, db: Session):
        """Управление отчетами"""
        try:
            message = """📊 **Управление отчетами**

Выберите тип отчета:"""

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📅 Ежедневный отчет",
                            "callback_data": "admin_report_daily",
                        }
                    ],
                    [
                        {
                            "text": "📆 Недельный отчет",
                            "callback_data": "admin_report_weekly",
                        }
                    ],
                    [
                        {
                            "text": "📈 Месячный отчет",
                            "callback_data": "admin_report_monthly",
                        }
                    ],
                    [
                        {
                            "text": "💰 Финансовый отчет",
                            "callback_data": "admin_report_financial",
                        }
                    ],
                    [
                        {
                            "text": "👥 Отчет по пациентам",
                            "callback_data": "admin_report_patients",
                        }
                    ],
                    [
                        {
                            "text": "👨‍⚕️ Отчет по врачам",
                            "callback_data": "admin_report_doctors",
                        }
                    ],
                    [
                        {
                            "text": "📋 Экспорт данных",
                            "callback_data": "admin_report_export",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка управления отчетами: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_backup(self, chat_id: int, telegram_user, db: Session):
        """Управление резервными копиями"""
        try:
            message = """💾 **Управление резервными копиями**

Выберите действие:"""

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "💾 Создать резервную копию",
                            "callback_data": "admin_backup_create",
                        }
                    ],
                    [{"text": "📋 Список копий", "callback_data": "admin_backup_list"}],
                    [
                        {
                            "text": "🔄 Восстановить из копии",
                            "callback_data": "admin_backup_restore",
                        }
                    ],
                    [
                        {
                            "text": "🗑️ Удалить старые копии",
                            "callback_data": "admin_backup_cleanup",
                        }
                    ],
                    [
                        {
                            "text": "⚙️ Настройки резервирования",
                            "callback_data": "admin_backup_settings",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка управления резервными копиями: {e}")
            await self._send_error_message(chat_id)


    async def _handle_admin_settings(self, chat_id: int, telegram_user, db: Session):
        """Управление настройками"""
        try:
            message = """⚙️ **Управление настройками**

Выберите категорию настроек:"""

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🏥 Настройки клиники",
                            "callback_data": "admin_settings_clinic",
                        }
                    ],
                    [
                        {
                            "text": "📱 Уведомления",
                            "callback_data": "admin_settings_notifications",
                        }
                    ],
                    [
                        {
                            "text": "💰 Платежи",
                            "callback_data": "admin_settings_payments",
                        }
                    ],
                    [{"text": "📋 Очереди", "callback_data": "admin_settings_queues"}],
                    [
                        {
                            "text": "🤖 Telegram бот",
                            "callback_data": "admin_settings_telegram",
                        }
                    ],
                    [
                        {
                            "text": "🔐 Безопасность",
                            "callback_data": "admin_settings_security",
                        }
                    ],
                    [
                        {
                            "text": "📊 Интеграции",
                            "callback_data": "admin_settings_integrations",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка управления настройками: {e}")
            await self._send_error_message(chat_id)

    # ==================== ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ ====================


