"""Patient mixin for EnhancedTelegramBotService.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg._base import *  # noqa: F401, F403
from app.services.telegram_bot_enhanced_pkg._base import EnhancedTelegramBotServiceMixinBase

class PatientMixin(EnhancedTelegramBotServiceMixinBase):
    """Patient methods for EnhancedTelegramBotService."""

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


