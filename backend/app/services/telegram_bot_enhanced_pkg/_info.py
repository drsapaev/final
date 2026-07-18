"""Info mixin for EnhancedTelegramBotService.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg._base import *  # noqa: F401, F403
from app.services.telegram_bot_enhanced_pkg._base import (
    EnhancedTelegramBotServiceMixinBase,
)


class InfoMixin(EnhancedTelegramBotServiceMixinBase):
    """Info methods for EnhancedTelegramBotService."""

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


