"""
Telegram бот для системы клиники
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.webhook.aiohttp_server import setup_application, SimpleRequestHandler
from aiohttp import web

from ...core.config import settings
from ...models.user import User
from ...models.visit import Visit
from ..queue_service import QueueBusinessService

logger = logging.getLogger(__name__)


class ClinicTelegramBot:
    """Telegram бот клиники"""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram bot disabled.")
            self.bot = None
            self.dp = None
            return

        self.bot = Bot(token=self.token)
        self.dp = Dispatcher()
        self.queue_service = QueueBusinessService()
        self._setup_handlers()

    async def send_confirmation_invitation(
        self, chat_id: int, message: str, keyboard: list
    ) -> Dict[str, Any]:
        """Отправляет приглашение на подтверждение визита"""
        try:
            if not self.bot:
                return {"success": False, "error": "Telegram bot не инициализирован"}

            # Создаем inline клавиатуру
            inline_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=button["text"],
                            callback_data=button.get("callback_data"),
                            url=button.get("url"),
                        )
                        for button in row
                    ]
                    for row in keyboard
                ]
            )

            # Отправляем сообщение
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=inline_keyboard,
                parse_mode="Markdown",
            )

            return {
                "success": True,
                "message_id": sent_message.message_id,
                "chat_id": chat_id,
            }

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram приглашения: {e}")
            return {"success": False, "error": str(e)}

    def _setup_handlers(self):
        """Настройка обработчиков команд"""
        if not self.dp:
            return

        # Команда /start
        @self.dp.message(CommandStart())
        async def start_handler(message: types.Message):
            await self.handle_start(message)

        # Команда /queue - утренняя очередь
        @self.dp.message(Command("queue"))
        async def queue_handler(message: types.Message):
            await self.handle_queue(message)

        # Обработчик callback'ов для подтверждения визитов
        @self.dp.callback_query()
        async def callback_handler(callback: types.CallbackQuery):
            await self.handle_callback(callback)

        # Команда /appointment - запись на прием
        @self.dp.message(Command("appointment"))
        async def appointment_handler(message: types.Message):
            await self.handle_appointment(message)

        # Команда /help
        @self.dp.message(Command("help"))
        async def help_handler(message: types.Message):
            await self.handle_help(message)

        # Обработка callback query
        @self.dp.callback_query()
        async def callback_handler(callback: types.CallbackQuery):
            await self.handle_callback(callback)

    async def handle_start(self, message: types.Message):
        """Обработка команды /start"""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name

        # Создаем клавиатуру с основными функциями
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📱 Открыть веб-приложение",
                        web_app=WebAppInfo(url=f"{settings.FRONTEND_URL}/mobile"),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏥 Утренняя очередь", callback_data="queue"
                    ),
                    InlineKeyboardButton(
                        text="📅 Записаться на прием", callback_data="appointment"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📋 Мои записи", callback_data="my_appointments"
                    ),
                    InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
                ],
            ]
        )

        welcome_text = f"""
👋 Добро пожаловать в систему клиники!

Привет, {first_name}! 

Я помогу вам:
• 🏥 Встать в утреннюю очередь (с 07:00)
• 📅 Записаться на прием к врачу
• 📋 Посмотреть ваши записи
• 📄 Получить результаты анализов
• 💊 Получить рецепты в PDF

Выберите нужную функцию из меню ниже:
        """

        await message.answer(welcome_text, reply_markup=keyboard)

    async def handle_queue(self, message: types.Message):
        """Обработка команды /queue"""
        user_id = message.from_user.id

        # Проверяем время (07:00 - 08:00)
        current_time = datetime.now()
        if current_time.hour < 7 or current_time.hour >= 8:
            await message.answer(
                "⏰ Утренняя очередь доступна только с 07:00 до 08:00!\n"
                f"Сейчас: {current_time.strftime('%H:%M')}"
            )
            return

        # Показываем доступных специалистов
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👨‍⚕️ Терапевт", callback_data="queue_therapist"
                    ),
                    InlineKeyboardButton(
                        text="❤️ Кардиолог", callback_data="queue_cardiologist"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="👩‍⚕️ Дерматолог", callback_data="queue_dermatologist"
                    ),
                    InlineKeyboardButton(
                        text="🦷 Стоматолог", callback_data="queue_dentist"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔬 Лаборатория", callback_data="queue_lab"
                    )
                ],
            ]
        )

        await message.answer(
            "🏥 Выберите специалиста для утренней очереди:\n\n"
            "⚠️ Внимание: очередь закрывается в 08:00!",
            reply_markup=keyboard,
        )

    async def handle_appointment(self, message: types.Message):
        """Обработка команды /appointment"""
        # Открываем веб-приложение для записи
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📅 Записаться на прием",
                        web_app=WebAppInfo(url=f"{settings.FRONTEND_URL}/appointment"),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📋 Мои записи", callback_data="my_appointments"
                    )
                ],
            ]
        )

        await message.answer(
            "📅 Запись на прием\n\n" "Нажмите кнопку ниже, чтобы открыть форму записи:",
            reply_markup=keyboard,
        )

    async def handle_help(self, message: types.Message):
        """Обработка команды /help"""
        help_text = """
ℹ️ **Помощь по боту клиники**

**Доступные команды:**
• `/start` - Главное меню
• `/queue` - Утренняя очередь (07:00-08:00)
• `/appointment` - Запись на прием
• `/help` - Эта справка

**Функции бота:**
🏥 **Утренняя очередь**
- Доступна с 07:00 до 08:00
- Выберите специалиста
- Получите номер очереди

📅 **Запись на прием**
- Выберите врача и время
- Подтвердите запись
- Получите напоминание

📋 **Уведомления**
- Напоминания о визитах
- Готовность результатов
- Изменения в расписании

**Поддержка:** @clinic_support
        """

        await message.answer(help_text, parse_mode="Markdown")

    async def handle_callback(self, callback: types.CallbackQuery):
        """Обработка callback запросов"""
        data = callback.data
        user_id = callback.from_user.id

        if data.startswith("queue_"):
            await self._handle_queue_callback(callback, data)
        elif data == "appointment":
            await self.handle_appointment(callback.message)
        elif data == "my_appointments":
            await self._handle_my_appointments(callback)
        elif data == "help":
            await self.handle_help(callback.message)

        await callback.answer()

    async def _handle_queue_callback(self, callback: types.CallbackQuery, data: str):
        """Обработка выбора специалиста для очереди"""
        specialist_map = {
            "queue_therapist": {"name": "Терапевт", "id": 1},
            "queue_cardiologist": {"name": "Кардиолог", "id": 2},
            "queue_dermatologist": {"name": "Дерматолог", "id": 3},
            "queue_dentist": {"name": "Стоматолог", "id": 4},
            "queue_lab": {"name": "Лаборатория", "id": 5},
        }

        specialist = specialist_map.get(data)
        if not specialist:
            await callback.message.answer("❌ Неизвестный специалист")
            return

        user_id = callback.from_user.id
        phone = callback.from_user.username or str(user_id)

        try:
            # Пытаемся встать в очередь
            result = await self.queue_service.join_queue(
                specialist_id=specialist["id"],
                phone=phone,
                telegram_id=user_id,
                patient_name=callback.from_user.first_name,
            )

            if result.get("success"):
                queue_number = result.get("queue_number", "?")
                estimated_time = result.get("estimated_time", "неизвестно")

                await callback.message.answer(
                    f"✅ Вы записаны в очередь!\n\n"
                    f"👨‍⚕️ Специалист: {specialist['name']}\n"
                    f"🎫 Ваш номер: {queue_number}\n"
                    f"⏰ Примерное время: {estimated_time}\n\n"
                    f"📱 Следите за очередью в приложении или ждите уведомления."
                )
            else:
                error_msg = result.get("message", "Неизвестная ошибка")
                await callback.message.answer(
                    f"❌ Не удалось встать в очередь:\n{error_msg}"
                )

        except Exception as e:
            logger.error(f"Error joining queue: {str(e)}")
            await callback.message.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def _handle_my_appointments(self, callback: types.CallbackQuery):
        """Показать записи пользователя"""
        # В реальном приложении здесь будет запрос к БД
        await callback.message.answer(
            "📋 Ваши записи:\n\n"
            "🔄 Загрузка данных...\n\n"
            "Для полной информации используйте веб-приложение.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📱 Открыть приложение",
                            web_app=WebAppInfo(
                                url=f"{settings.FRONTEND_URL}/appointments"
                            ),
                        )
                    ]
                ]
            ),
        )

    async def send_notification(
        self,
        user_id: int,
        message: str,
        keyboard: Optional[InlineKeyboardMarkup] = None,
    ):
        """Отправка уведомления пользователю"""
        if not self.bot:
            return False

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {str(e)}")
            return False

    async def send_appointment_reminder(
        self, user_id: int, appointment_data: Dict[str, Any]
    ):
        """Отправка напоминания о визите"""
        doctor = appointment_data.get("doctor", "Врач")
        time = appointment_data.get("time", "время не указано")
        date = appointment_data.get("date", "дата не указана")

        message = f"""
📅 **Напоминание о визите**

👨‍⚕️ Врач: {doctor}
📅 Дата: {date}
⏰ Время: {time}

Не забудьте прийти за 15 минут до назначенного времени.
        """

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"confirm_{appointment_data.get('id')}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отменить",
                        callback_data=f"cancel_{appointment_data.get('id')}",
                    ),
                ]
            ]
        )

        await self.send_notification(user_id, message, keyboard)

    async def send_lab_results_ready(self, user_id: int, results_info: Dict[str, Any]):
        """Уведомление о готовности результатов"""
        message = f"""
🔬 **Результаты анализов готовы**

📋 Исследование: {results_info.get('test_name', 'Анализы')}
📅 Дата: {results_info.get('date', 'не указана')}

Результаты доступны в приложении.
        """

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📄 Посмотреть результаты",
                        web_app=WebAppInfo(url=f"{settings.FRONTEND_URL}/lab-results"),
                    )
                ]
            ]
        )

        await self.send_notification(user_id, message, keyboard)

    async def setup_webhook(self, webhook_url: str):
        """Настройка webhook"""
        if not self.bot:
            return False

        try:
            await self.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to set webhook: {str(e)}")
            return False

    async def remove_webhook(self):
        """Удаление webhook"""
        if not self.bot:
            return False

        try:
            await self.bot.delete_webhook()
            logger.info("Webhook removed")
            return True
        except Exception as e:
            logger.error(f"Failed to remove webhook: {str(e)}")
            return False

    def get_webhook_handler(self):
        """Получить обработчик webhook для aiohttp"""
        if not self.bot or not self.dp:
            return None

        return SimpleRequestHandler(dispatcher=self.dp, bot=self.bot)

    async def handle_callback(self, callback: types.CallbackQuery):
        """Обработчик callback'ов для подтверждения визитов"""
        try:
            callback_data = callback.data

            if callback_data.startswith("confirm_visit:"):
                # Подтверждение визита
                token = callback_data.split(":", 1)[1]
                await self._handle_visit_confirmation(callback, token, True)

            elif callback_data.startswith("cancel_visit:"):
                # Отмена визита
                token = callback_data.split(":", 1)[1]
                await self._handle_visit_confirmation(callback, token, False)

            else:
                # Неизвестный callback
                await callback.answer("Неизвестная команда", show_alert=True)

        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

    async def _handle_visit_confirmation(
        self, callback: types.CallbackQuery, token: str, confirm: bool
    ):
        """Обрабатывает подтверждение или отмену визита"""
        try:
            if confirm:
                # Подтверждаем визит через API
                result = await self._confirm_visit_via_api(token, callback.from_user.id)

                if result.get("success"):
                    message = "✅ Визит успешно подтвержден!"
                    if result.get("queue_numbers"):
                        queue_info = ", ".join(
                            [
                                f"{q['queue_name']}: №{q['number']}"
                                for q in result["queue_numbers"]
                            ]
                        )
                        message += f"\n\n🎫 Ваши номера в очередях:\n{queue_info}"

                    await callback.message.edit_text(
                        text=f"{callback.message.text}\n\n{message}",
                        parse_mode="Markdown",
                    )
                else:
                    await callback.answer(
                        f"Ошибка подтверждения: {result.get('message', 'Неизвестная ошибка')}",
                        show_alert=True,
                    )
            else:
                # Отменяем визит
                await callback.message.edit_text(
                    text=f"{callback.message.text}\n\n❌ Визит отменен",
                    parse_mode="Markdown",
                )

            await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка подтверждения визита: {e}")
            await callback.answer("Произошла ошибка при подтверждении", show_alert=True)

    async def _confirm_visit_via_api(
        self, token: str, telegram_user_id: int
    ) -> Dict[str, Any]:
        """Подтверждает визит через API"""
        try:
            # Здесь должен быть вызов API подтверждения
            # Пока возвращаем заглушку
            import requests

            response = requests.post(
                f"{settings.API_BASE_URL}/telegram/visits/confirm",
                json={"token": token, "channel": "telegram"},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "message": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Ошибка API подтверждения: {e}")
            return {"success": False, "message": str(e)}


# Глобальный экземпляр бота
telegram_bot = ClinicTelegramBot()


class TelegramBotService:
    """Сервис для работы с Telegram ботом"""

    def __init__(self):
        self.bot = telegram_bot

    async def send_confirmation_invitation(
        self, chat_id: int, message: str, keyboard: list
    ) -> Dict[str, Any]:
        """Отправляет приглашение на подтверждение визита"""
        if not self.bot or not self.bot.bot:
            return {"success": False, "error": "Telegram bot не доступен"}

        return await self.bot.send_confirmation_invitation(chat_id, message, keyboard)
