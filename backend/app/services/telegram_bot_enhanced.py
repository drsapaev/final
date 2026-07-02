"""
Расширенный Telegram Bot с дополнительными командами и интеграцией с админ-панелью
"""

import asyncio
import json
import logging
from datetime import date, datetime

import httpx
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.crud import (
    clinic as crud_doctor,
)
from app.crud import (
    service as crud_service,
)
from app.crud import (
    user as crud_user,
)
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.services.telegram_bot import TelegramBotService

logger = logging.getLogger(__name__)


class EnhancedTelegramBotService(TelegramBotService):
    """Расширенный Telegram бот с дополнительными командами"""

    def __init__(self):
        super().__init__()
        self.admin_commands = {
            "/admin_stats": self._handle_admin_stats,
            "/admin_queues": self._handle_admin_queues,
            "/admin_patients": self._handle_admin_patients,
            "/admin_appointments": self._handle_admin_appointments,
            "/admin_doctors": self._handle_admin_doctors,
            "/admin_services": self._handle_admin_services,
            "/admin_notifications": self._handle_admin_notifications,
            "/admin_reports": self._handle_admin_reports,
            "/admin_backup": self._handle_admin_backup,
            "/admin_settings": self._handle_admin_settings,
        }

        self.user_commands = {
            "/start": self._handle_start,
            "/help": self._handle_help,
            "/menu": self._handle_menu,
            "/appointments": self._handle_appointments,
            "/book": self._handle_book,
            "/cancel": self._handle_cancel,
            "/reschedule": self._handle_reschedule,
            "/profile": self._handle_profile,
            "/doctors": self._handle_doctors,
            "/services": self._handle_services,
            "/queue": self._handle_queue,
            "/status": self._handle_status,
            "/feedback": self._handle_feedback,
            "/emergency": self._handle_emergency,
            "/language": self._handle_language,
            "/notifications": self._handle_notifications_settings,
        }

    async def _handle_command(
        self, command: str, chat_id: int, telegram_user, db: Session, max_retries: int = 2
    ):
        """
        Расширенная обработка команд с retry логикой

        ✅ SECURITY: Implements error handling and retry for command processing
        """
        for attempt in range(max_retries):
            try:
                # Проверяем права администратора
                is_admin = await self._check_admin_rights(telegram_user, db)

                # Обрабатываем админские команды
                if command in self.admin_commands and is_admin:
                    await self.admin_commands[command](chat_id, telegram_user, db)
                    return  # Success
                # Обрабатываем пользовательские команды
                elif command in self.user_commands:
                    await self.user_commands[command](chat_id, telegram_user, db)
                    return  # Success
                else:
                    await self._send_unknown_command_message(chat_id)
                    return  # Unknown command, no retry needed

            except Exception as e:
                logger.error(f"Ошибка обработки команды {command} (попытка {attempt + 1}/{max_retries}): {e}", exc_info=True)

                # Don't retry on certain errors
                if isinstance(e, ValueError | KeyError | AttributeError):
                    await self._send_error_message(chat_id)
                    return

                # Retry on transient errors
                if attempt < max_retries - 1:
                    wait_time = 1 * (attempt + 1)  # Linear backoff: 1s, 2s
                    logger.warning(f"Retrying command {command} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed
                    await self._send_error_message(chat_id)
                    return

    async def _check_admin_rights(self, telegram_user, db: Session) -> bool:
        """Проверка прав администратора"""
        try:
            if not telegram_user or not telegram_user.linked_user_id:
                return False

            user = crud_user.get(db, id=telegram_user.linked_user_id)
            return user and user.role in ["Admin", "SuperAdmin"]
        except Exception:
            return False

    # ==================== АДМИНСКИЕ КОМАНДЫ ====================

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

    async def _handle_start(self, chat_id: int, telegram_user, db: Session):
        """Расширенное приветствие"""
        try:
            user_name = telegram_user.first_name or "Пользователь"

            message = f"""👋 Добро пожаловать, {user_name}!

🏥 Я бот клиники, который поможет вам:
• 📅 Записаться на прием
• 👀 Посмотреть ваши записи
• 🔄 Перенести или отменить запись
• 📋 Узнать очередь к врачу
• 👨‍⚕️ Найти информацию о врачах
• 💊 Узнать о наших услугах

Используйте /menu для просмотра всех команд или нажмите на кнопки ниже:"""

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📅 Мои записи", "callback_data": "my_appointments"}],
                    [{"text": "📝 Записаться", "callback_data": "book_appointment"}],
                    [{"text": "👨‍⚕️ Врачи", "callback_data": "doctors_list"}],
                    [{"text": "📋 Очередь", "callback_data": "queue_status"}],
                    [{"text": "ℹ️ Помощь", "callback_data": "help_menu"}],
                ]
            }

            await self._send_message(chat_id, message, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Ошибка команды start: {e}")
            await self._send_error_message(chat_id)

    async def _handle_menu(self, chat_id: int, telegram_user, db: Session):
        """Главное меню"""
        try:
            is_admin = await self._check_admin_rights(telegram_user, db)

            message = "📋 **Главное меню**\\n\\nВыберите нужное действие:"

            user_buttons = [
                [{"text": "📅 Мои записи", "callback_data": "my_appointments"}],
                [
                    {
                        "text": "📝 Записаться на прием",
                        "callback_data": "book_appointment",
                    }
                ],
                [{"text": "👨‍⚕️ Наши врачи", "callback_data": "doctors_list"}],
                [{"text": "💊 Наши услуги", "callback_data": "services_list"}],
                [{"text": "📋 Очередь", "callback_data": "queue_status"}],
                [{"text": "👤 Мой профиль", "callback_data": "my_profile"}],
                [{"text": "⚙️ Настройки", "callback_data": "user_settings"}],
                [{"text": "🆘 Экстренная помощь", "callback_data": "emergency_help"}],
            ]

            if is_admin:
                user_buttons.extend(
                    [[{"text": "🔧 Админ-панель", "callback_data": "admin_panel"}]]
                )

            keyboard = {"inline_keyboard": user_buttons}

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды menu: {e}")
            await self._send_error_message(chat_id)

    async def _handle_queue(self, chat_id: int, telegram_user, db: Session):
        """Информация об очередях"""
        try:
            today = date.today()

            active_queues = (
                db.query(DailyQueue)
                .filter(and_(DailyQueue.day == today, DailyQueue.active == True))
                .all()
            )

            if not active_queues:
                message = "📋 Сегодня нет активных очередей"
            else:
                message = "📋 **Текущие очереди:**\\n\\n"

                for queue in active_queues:
                    doctor_name = (
                        queue.doctor.full_name if queue.doctor else "Неизвестно"
                    )
                    waiting = queue.total_numbers - queue.current_number

                    message += f"👨‍⚕️ **{doctor_name}**\\n"
                    message += f"• Текущий номер: {queue.current_number}\\n"
                    message += f"• В очереди: {waiting}\\n"

                    if waiting > 0:
                        estimated_time = waiting * 15  # примерно 15 минут на пациента
                        message += (
                            f"• Примерное время ожидания: {estimated_time} мин\\n"
                        )

                    message += "\\n"

            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔄 Обновить", "callback_data": "queue_refresh"}],
                    [
                        {
                            "text": "📱 Уведомить о подходе",
                            "callback_data": "queue_notify",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды queue: {e}")
            await self._send_error_message(chat_id)

    async def _handle_emergency(self, chat_id: int, telegram_user, db: Session):
        """Экстренная помощь"""
        try:
            message = """🆘 **ЭКСТРЕННАЯ ПОМОЩЬ**

⚠️ **При угрозе жизни немедленно вызывайте:**
• 🚑 Скорая помощь: 103
• 🚒 Пожарная служба: 101
• 🚔 Полиция: 102
• 📞 Единая служба экстренных вызовов: 112

🏥 **Наша клиника:**
• 📞 Регистратура: +998 XX XXX-XX-XX
• 🕐 Круглосуточная линия: +998 XX XXX-XX-XX
• 📍 Адрес: [Адрес клиники]

💊 **Дежурный врач:**
• Доступен 24/7 для консультаций
• Нажмите кнопку ниже для связи"""

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📞 Связаться с дежурным врачом",
                            "callback_data": "emergency_doctor",
                        }
                    ],
                    [{"text": "🚑 Вызвать скорую", "url": "tel:103"}],
                    [
                        {
                            "text": "📍 Показать маршрут",
                            "callback_data": "clinic_location",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды emergency: {e}")
            await self._send_error_message(chat_id)

    async def _handle_feedback(self, chat_id: int, telegram_user, db: Session):
        """Обратная связь"""
        try:
            message = """💬 **Обратная связь**

Мы ценим ваше мнение! Выберите тип обращения:"""

            keyboard = {
                "inline_keyboard": [
                    [{"text": "⭐ Оставить отзыв", "callback_data": "feedback_review"}],
                    [
                        {
                            "text": "💡 Предложение",
                            "callback_data": "feedback_suggestion",
                        }
                    ],
                    [{"text": "❗ Жалоба", "callback_data": "feedback_complaint"}],
                    [{"text": "❓ Вопрос", "callback_data": "feedback_question"}],
                    [
                        {
                            "text": "📞 Связаться с администрацией",
                            "callback_data": "feedback_admin",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды feedback: {e}")
            await self._send_error_message(chat_id)

    async def _handle_help(self, chat_id: int, telegram_user, db: Session):
        """Справка по командам"""
        try:
            message = """ℹ️ **Справка по командам**

**Основные команды:**
• /start - Начать работу с ботом
• /menu - Главное меню
• /help - Эта справка

**Записи:**
• /appointments - Мои записи
• /book - Записаться на прием
• /cancel - Отменить запись
• /reschedule - Перенести запись

**Информация:**
• /doctors - Список врачей
• /services - Наши услуги
• /queue - Текущие очереди
• /status - Статус записи

**Профиль:**
• /profile - Мой профиль
• /notifications - Настройки уведомлений
• /language - Смена языка

**Экстренная помощь:**
• /emergency - Экстренная помощь
• /feedback - Обратная связь

Для получения подробной информации используйте /menu"""

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📋 Главное меню", "callback_data": "main_menu"}],
                    [{"text": "📞 Техподдержка", "callback_data": "support"}],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды help: {e}")
            await self._send_error_message(chat_id)

    async def _handle_appointments(self, chat_id: int, telegram_user, db: Session):
        """Мои записи"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем записи пользователя
                appointments = (
                    db.query(Appointment)
                    .filter(Appointment.patient_id == user.id)
                    .order_by(Appointment.appointment_date.desc())
                    .limit(10)
                    .all()
                )

                if appointments:
                    message = f"📅 **Ваши записи ({len(appointments)}):**\\n\\n"

                    for appointment in appointments:
                        date_str = appointment.appointment_date.strftime('%d.%m.%Y')
                        time_str = (
                            appointment.appointment_time.strftime('%H:%M')
                            if appointment.appointment_time
                            else 'Время не указано'
                        )

                        status_icons = {
                            "pending": "⏳",
                            "confirmed": "✅",
                            "completed": "✅",
                            "cancelled": "❌",
                            "no_show": "👻",
                        }

                        status = appointment.status or "pending"
                        icon = status_icons.get(status, "📋")

                        message += f"{icon} **{date_str} в {time_str}**\\n"
                        message += (
                            f"👨‍⚕️ {appointment.doctor_name or 'Врач не указан'}\\n"
                        )
                        message += f"📋 Статус: {status}\\n\\n"
                else:
                    message = "📅 У вас пока нет записей\\n\\nИспользуйте /book для записи на прием"

                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "📝 Записаться",
                                "callback_data": "book_appointment",
                            }
                        ],
                        [
                            {
                                "text": "🔄 Обновить",
                                "callback_data": "refresh_appointments",
                            }
                        ],
                    ]
                }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды appointments: {e}")
            await self._send_error_message(chat_id)

    async def _handle_book(self, chat_id: int, telegram_user, db: Session):
        """Записаться на прием"""
        try:
            message = """📝 **Запись на прием**

Выберите тип записи:"""

            keyboard = {
                "inline_keyboard": [
                    [{"text": "👨‍⚕️ К врачу", "callback_data": "book_doctor"}],
                    [{"text": "💊 На процедуру", "callback_data": "book_procedure"}],
                    [{"text": "🔬 В лабораторию", "callback_data": "book_lab"}],
                    [{"text": "📋 В очередь", "callback_data": "book_queue"}],
                    [
                        {
                            "text": "📞 Позвонить в регистратуру",
                            "callback_data": "call_registry",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды book: {e}")
            await self._send_error_message(chat_id)

    async def _handle_cancel(self, chat_id: int, telegram_user, db: Session):
        """Отменить запись"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем активные записи пользователя
                appointments = (
                    db.query(Appointment)
                    .filter(
                        and_(
                            Appointment.patient_id == user.id,
                            Appointment.status.in_(["pending", "confirmed"]),
                        )
                    )
                    .order_by(Appointment.appointment_date.asc())
                    .limit(5)
                    .all()
                )

                if appointments:
                    message = "❌ **Отмена записи**\\n\\nВыберите запись для отмены:"

                    keyboard_buttons = []
                    for appointment in appointments:
                        date_str = appointment.appointment_date.strftime('%d.%m.%Y')
                        time_str = (
                            appointment.appointment_time.strftime('%H:%M')
                            if appointment.appointment_time
                            else 'Время не указано'
                        )

                        button_text = f"📅 {date_str} {time_str}"
                        callback_data = f"cancel_appointment_{appointment.id}"
                        keyboard_buttons.append(
                            [{"text": button_text, "callback_data": callback_data}]
                        )

                    keyboard = {"inline_keyboard": keyboard_buttons}
                else:
                    message = "📅 У вас нет активных записей для отмены"
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📝 Записаться",
                                    "callback_data": "book_appointment",
                                }
                            ]
                        ]
                    }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды cancel: {e}")
            await self._send_error_message(chat_id)

    async def _handle_reschedule(self, chat_id: int, telegram_user, db: Session):
        """Перенести запись"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем активные записи пользователя
                appointments = (
                    db.query(Appointment)
                    .filter(
                        and_(
                            Appointment.patient_id == user.id,
                            Appointment.status.in_(["pending", "confirmed"]),
                        )
                    )
                    .order_by(Appointment.appointment_date.asc())
                    .limit(5)
                    .all()
                )

                if appointments:
                    message = "🔄 **Перенос записи**\\n\\nВыберите запись для переноса:"

                    keyboard_buttons = []
                    for appointment in appointments:
                        date_str = appointment.appointment_date.strftime('%d.%m.%Y')
                        time_str = (
                            appointment.appointment_time.strftime('%H:%M')
                            if appointment.appointment_time
                            else 'Время не указано'
                        )

                        button_text = f"📅 {date_str} {time_str}"
                        callback_data = f"reschedule_appointment_{appointment.id}"
                        keyboard_buttons.append(
                            [{"text": button_text, "callback_data": callback_data}]
                        )

                    keyboard = {"inline_keyboard": keyboard_buttons}
                else:
                    message = "📅 У вас нет активных записей для переноса"
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📝 Записаться",
                                    "callback_data": "book_appointment",
                                }
                            ]
                        ]
                    }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды reschedule: {e}")
            await self._send_error_message(chat_id)

    async def _handle_profile(self, chat_id: int, telegram_user, db: Session):
        """Мой профиль"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                message = f"""👤 **Мой профиль**

**Основная информация:**
• Имя: {user.full_name or 'Не указано'}
• Телефон: {user.phone or 'Не указан'}
• Email: {user.email or 'Не указан'}
• Роль: {user.role or 'Пользователь'}

**Статистика:**
• Записей: {db.query(Appointment).filter(Appointment.patient_id == user.id).count()}
• Последний визит: {user.last_login.strftime('%d.%m.%Y %H:%M') if user.last_login else 'Не указан'}

**Настройки:**
• Уведомления: {'Включены' if user.notifications_enabled else 'Отключены'}
• Язык: {user.language or 'Русский'}"""

                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "✏️ Редактировать профиль",
                                "callback_data": "edit_profile",
                            }
                        ],
                        [{"text": "⚙️ Настройки", "callback_data": "profile_settings"}],
                        [{"text": "📊 Статистика", "callback_data": "profile_stats"}],
                    ]
                }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды profile: {e}")
            await self._send_error_message(chat_id)

    async def _handle_doctors(self, chat_id: int, telegram_user, db: Session):
        """Список врачей"""
        try:
            # Получаем всех активных врачей
            doctors = crud_doctor.get_doctors(db, active_only=True)

            if doctors:
                message = f"👨‍⚕️ **Наши врачи ({len(doctors)}):**\\n\\n"

                for doctor in doctors[:10]:  # Показываем первых 10
                    message += f"• **{doctor.full_name}**\\n"
                    message += f"  {doctor.specialty or 'Специальность не указана'}\\n"
                    if doctor.phone:
                        message += f"  📞 {doctor.phone}\\n"
                    message += "\\n"

                if len(doctors) > 10:
                    message += f"... и еще {len(doctors) - 10} врачей\\n"
            else:
                message = "👨‍⚕️ Врачи не найдены"

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📝 Записаться к врачу", "callback_data": "book_doctor"}],
                    [{"text": "📋 Расписание", "callback_data": "doctor_schedule"}],
                    [{"text": "🔄 Обновить", "callback_data": "refresh_doctors"}],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды doctors: {e}")
            await self._send_error_message(chat_id)

    async def _handle_services(self, chat_id: int, telegram_user, db: Session):
        """Наши услуги"""
        try:
            # Получаем все активные услуги
            services = crud_service.get_services(db, active_only=True)

            if services:
                message = f"💊 **Наши услуги ({len(services)}):**\\n\\n"

                for service in services[:10]:  # Показываем первых 10
                    message += f"• **{service.name}**\\n"
                    message += f"  💰 {service.price:,} сум\\n"
                    if service.description:
                        message += f"  📝 {service.description[:50]}...\\n"
                    message += "\\n"

                if len(services) > 10:
                    message += f"... и еще {len(services) - 10} услуг\\n"
            else:
                message = "💊 Услуги не найдены"

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📝 Записаться на услугу",
                            "callback_data": "book_service",
                        }
                    ],
                    [{"text": "📋 Категории", "callback_data": "service_categories"}],
                    [{"text": "🔄 Обновить", "callback_data": "refresh_services"}],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды services: {e}")
            await self._send_error_message(chat_id)

    async def _handle_status(self, chat_id: int, telegram_user, db: Session):
        """Статус записи"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем последнюю запись пользователя
                last_appointment = (
                    db.query(Appointment)
                    .filter(Appointment.patient_id == user.id)
                    .order_by(Appointment.appointment_date.desc())
                    .first()
                )

                if last_appointment:
                    date_str = last_appointment.appointment_date.strftime('%d.%m.%Y')
                    time_str = (
                        last_appointment.appointment_time.strftime('%H:%M')
                        if last_appointment.appointment_time
                        else 'Время не указано'
                    )

                    status_icons = {
                        "pending": "⏳ Ожидает подтверждения",
                        "confirmed": "✅ Подтверждена",
                        "completed": "✅ Завершена",
                        "cancelled": "❌ Отменена",
                        "no_show": "👻 Не явился",
                    }

                    status = last_appointment.status or "pending"
                    status_text = status_icons.get(status, f"📋 {status}")

                    message = f"""📋 **Статус записи**

**Последняя запись:**
• Дата: {date_str}
• Время: {time_str}
• Врач: {last_appointment.doctor_name or 'Не указан'}
• Статус: {status_text}

**Детали:**
• Номер записи: #{last_appointment.id}
• Создана: {last_appointment.created_at.strftime('%d.%m.%Y %H:%M')}"""
                else:
                    message = "📅 У вас пока нет записей\\n\\nИспользуйте /book для записи на прием"

                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📅 Все записи", "callback_data": "my_appointments"}],
                        [
                            {
                                "text": "📝 Новая запись",
                                "callback_data": "book_appointment",
                            }
                        ],
                    ]
                }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды status: {e}")
            await self._send_error_message(chat_id)

    async def _handle_language(self, chat_id: int, telegram_user, db: Session):
        """Смена языка"""
        try:
            message = """🌐 **Выбор языка**

Выберите язык интерфейса:"""

            keyboard = {
                "inline_keyboard": [
                    [{"text": "🇷🇺 Русский", "callback_data": "lang_ru"}],
                    [{"text": "🇺🇿 O'zbek", "callback_data": "lang_uz"}],
                    [{"text": "🇬🇧 English", "callback_data": "lang_en"}],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды language: {e}")
            await self._send_error_message(chat_id)

    async def _handle_notifications_settings(
        self, chat_id: int, telegram_user, db: Session
    ):
        """Настройки уведомлений"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                message = f"""🔔 **Настройки уведомлений**

**Текущие настройки:**
• SMS уведомления: {'Включены' if user.sms_notifications else 'Отключены'}
• Email уведомления: {'Включены' if user.email_notifications else 'Отключены'}
• Telegram уведомления: {'Включены' if user.telegram_notifications else 'Отключены'}

**Типы уведомлений:**
• Напоминания о записи
• Изменения в расписании
• Результаты анализов
• Новости клиники"""

                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📱 SMS", "callback_data": "toggle_sms"}],
                        [{"text": "📧 Email", "callback_data": "toggle_email"}],
                        [{"text": "🤖 Telegram", "callback_data": "toggle_telegram"}],
                        [
                            {
                                "text": "⚙️ Детальные настройки",
                                "callback_data": "notification_details",
                            }
                        ],
                    ]
                }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды notifications: {e}")
            await self._send_error_message(chat_id)

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    async def _send_error_message(self, chat_id: int):
        """Отправка сообщения об ошибке"""
        message = """❌ Произошла ошибка при выполнении команды.

Попробуйте позже или обратитесь в техподдержку."""

        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 Попробовать снова", "callback_data": "retry"}],
                [{"text": "📞 Техподдержка", "callback_data": "support"}],
            ]
        }

        await self._send_message(chat_id, message, reply_markup=keyboard)

    async def _send_message(
        self, chat_id: int, text: str, parse_mode: str = None, reply_markup: dict = None, max_retries: int = 3
    ):
        """
        Отправка сообщения через Telegram API с retry логикой

        ✅ SECURITY: Implements exponential backoff retry for reliability
        ✅ BUGFIX: Uses async HTTP client (httpx) instead of blocking requests
        """
        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": text}

        if parse_mode:
            data["parse_mode"] = parse_mode

        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        # ✅ BUGFIX: Use async HTTP client to avoid blocking event loop
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Retry logic with exponential backoff
            for attempt in range(max_retries):
                try:
                    response = await client.post(url, json=data)

                    # Check for rate limiting (429)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()

                    result = response.json()
                    if result.get("ok"):
                        return True
                    else:
                        error = result.get("description", "Unknown error")
                        logger.error(f"Telegram API error: {error}")

                        # Don't retry on certain errors (bad request, forbidden, etc.)
                        if response.status_code in (400, 401, 403, 404):
                            return False

                        # Retry on server errors (500, 502, 503, 504)
                        if response.status_code >= 500 and attempt < max_retries - 1:
                            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                            logger.warning(f"Server error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue

                        return False

                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("Request timeout after all retries")
                        return False

                except httpx.NetworkError:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("Connection error after all retries")
                        return False

                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    return False

                except Exception as e:
                    logger.error(f"Unexpected error sending message: {e}")
                    return False

        return False

    async def send_admin_notification(self, message: str, db: Session):
        """
        Отправка уведомления всем администраторам с error handling

        ✅ SECURITY: Implements comprehensive error handling
        """
        try:
            # Получаем всех администраторов с Telegram
            admins = (
                db.query(User)
                .filter(
                    and_(
                        User.role.in_(["Admin", "SuperAdmin"]),
                        User.telegram_chat_id.isnot(None),
                    )
                )
                .all()
            )

            if not admins:
                logger.warning("No admins with Telegram chat ID found")
                return

            success_count = 0
            for admin in admins:
                try:
                    success = await self._send_message(
                        admin.telegram_chat_id,
                        f"🔔 **Уведомление администратора**\\n\\n{message}",
                        parse_mode="Markdown",
                    )
                    if success:
                        success_count += 1
                    else:
                        logger.warning(f"Failed to send notification to admin {admin.id}")
                except Exception as e:
                    logger.error(f"Error sending to admin {admin.id}: {e}")

            logger.info(f"Admin notification sent to {success_count}/{len(admins)} admins")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администраторам: {e}", exc_info=True)

    async def send_bulk_notification(
        self, message: str, user_ids: list[int], db: Session, batch_size: int = 10
    ):
        """
        Массовая отправка уведомлений с retry логикой

        ✅ SECURITY: Implements batch processing and error recovery
        """
        try:
            success_count = 0
            failed_count = 0
            failed_users = []

            # Process in batches to avoid rate limiting
            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i:i + batch_size]

                for user_id in batch:
                    try:
                        user = crud_user.get(db, id=user_id)
                        if user and user.telegram_chat_id:
                            success = await self._send_message(user.telegram_chat_id, message)
                            if success:
                                success_count += 1
                            else:
                                failed_count += 1
                                failed_users.append(user_id)
                        else:
                            logger.warning(f"User {user_id} has no Telegram chat ID")
                            failed_count += 1

                        # Небольшая задержка между отправками
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"Error sending to user {user_id}: {e}")
                        failed_count += 1
                        failed_users.append(user_id)

                # Longer delay between batches to respect rate limits
                if i + batch_size < len(user_ids):
                    await asyncio.sleep(1)

            # Retry failed users once
            if failed_users:
                logger.info(f"Retrying {len(failed_users)} failed notifications...")
                await asyncio.sleep(5)  # Wait before retry

                for user_id in failed_users[:]:
                    try:
                        user = crud_user.get(db, id=user_id)
                        if user and user.telegram_chat_id:
                            success = await self._send_message(user.telegram_chat_id, message)
                            if success:
                                success_count += 1
                                failed_users.remove(user_id)
                                failed_count -= 1
                    except Exception as e:
                        logger.error(f"Retry failed for user {user_id}: {e}")

            logger.info(f"Bulk notification: {success_count} sent, {failed_count} failed")
            return success_count

        except Exception as e:
            logger.error(f"Ошибка массовой отправки: {e}", exc_info=True)
            return success_count  # Return partial success count


# Глобальный экземпляр расширенного бота
enhanced_telegram_bot = EnhancedTelegramBotService()


def get_enhanced_telegram_bot() -> EnhancedTelegramBotService:
    """Получить экземпляр расширенного Telegram бота"""
    return enhanced_telegram_bot
