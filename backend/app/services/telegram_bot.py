"""
Telegram Bot сервис для клиники
Полнофункциональный бот с обработкой команд и webhook
"""

import json
import logging
from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.crud import (
    appointment as crud_appointment,
)
from app.crud import (
    telegram_config as crud_telegram,
)
from app.crud import (
    user as crud_user,
)

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(self):
        self.bot_token = None
        self.bot_username = None
        self.webhook_url = None
        self.active = False

    async def initialize(self, db: Session):
        """Инициализация бота"""
        try:
            config = crud_telegram.get_telegram_config(db)
            if config and config.bot_token:
                self.bot_token = config.bot_token
                self.bot_username = config.bot_username
                self.webhook_url = config.webhook_url
                self.active = config.active
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            return False

    async def process_webhook_update(self, update: dict[str, Any], db: Session):
        """Обработка webhook обновлений от Telegram"""
        try:
            if "message" in update:
                await self._handle_message(update["message"], db)
            elif "callback_query" in update:
                await self._handle_callback_query(update["callback_query"], db)
            elif "inline_query" in update:
                await self._handle_inline_query(update["inline_query"], db)
        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {e}")

    async def _handle_message(self, message: dict[str, Any], db: Session):
        """Обработка текстовых сообщений"""
        try:
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            user_id = message["from"]["id"]
            username = message["from"].get("username", "")
            first_name = message["from"].get("first_name", "")
            last_name = message["from"].get("last_name", "")
            language_code = message["from"].get("language_code", "ru")

            # Регистрируем или обновляем пользователя
            telegram_user = await self._register_telegram_user(
                db, user_id, username, first_name, last_name, language_code, chat_id
            )

            # Обрабатываем команды
            if text.startswith("/"):
                await self._handle_command(text, chat_id, telegram_user, db)
            else:
                await self._handle_text_message(text, chat_id, telegram_user, db)

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")

    async def _handle_callback_query(self, callback_query: dict[str, Any], db: Session):
        """Обработка callback запросов (кнопки)"""
        try:
            chat_id = callback_query["message"]["chat"]["id"]
            data = callback_query["data"]
            _user_id = callback_query["from"]["id"]

            # Обрабатываем callback данные
            if data.startswith("confirm_"):
                appointment_id = data.replace("confirm_", "")
                await self._handle_appointment_confirmation(chat_id, appointment_id, db)
            elif data.startswith("reschedule_"):
                appointment_id = data.replace("reschedule_", "")
                await self._handle_appointment_reschedule(chat_id, appointment_id, db)
            elif data.startswith("cancel_"):
                appointment_id = data.replace("cancel_", "")
                await self._handle_appointment_cancellation(chat_id, appointment_id, db)
            elif data.startswith("book_"):
                doctor_id = data.replace("book_", "")
                await self._handle_booking_request(chat_id, doctor_id, db)

            # Отвечаем на callback
            await self._answer_callback_query(callback_query["id"])

        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")

    async def _handle_inline_query(self, inline_query: dict[str, Any], db: Session):
        """Обработка inline запросов"""
        try:
            query_id = inline_query["id"]
            query_text = inline_query.get("query", "")
            user_id = inline_query["from"]["id"]

            # Поиск врачей или услуг
            if "врач" in query_text.lower() or "doctor" in query_text.lower():
                results = await self._search_doctors(query_text, db)
            elif "запись" in query_text.lower() or "appointment" in query_text.lower():
                results = await self._search_appointments(query_text, user_id, db)
            else:
                results = []

            await self._answer_inline_query(query_id, results)

        except Exception as e:
            logger.error(f"Ошибка обработки inline запроса: {e}")

    async def _handle_command(
        self, command: str, chat_id: int, telegram_user, db: Session
    ):
        """Обработка команд бота"""
        try:
            if command == "/start":
                await self._send_welcome_message(chat_id, telegram_user)
            elif command == "/help":
                await self._send_help_message(chat_id)
            elif command == "/appointments":
                await self._send_appointments_list(chat_id, telegram_user, db)
            elif command == "/book":
                await self._send_booking_menu(chat_id, db)
            elif command == "/profile":
                await self._send_profile_info(chat_id, telegram_user, db)
            elif command == "/settings":
                await self._send_settings_menu(chat_id, telegram_user)
            elif command == "/support":
                await self._send_support_info(chat_id)
            else:
                await self._send_unknown_command_message(chat_id)

        except Exception as e:
            logger.error(f"Ошибка обработки команды {command}: {e}")

    async def _handle_text_message(
        self, text: str, chat_id: int, telegram_user, db: Session
    ):
        """Обработка обычных текстовых сообщений"""
        try:
            # Простой AI-ассистент для ответов на вопросы
            if any(
                word in text.lower() for word in ["время", "работа", "часы", "открыт"]
            ):
                await self._send_working_hours(chat_id)
            elif any(
                word in text.lower()
                for word in ["адрес", "где", "найти", "расположение"]
            ):
                await self._send_clinic_address(chat_id)
            elif any(
                word in text.lower() for word in ["телефон", "звонок", "связаться"]
            ):
                await self._send_contact_info(chat_id)
            elif any(word in text.lower() for word in ["цена", "стоимость", "сколько"]):
                await self._send_pricing_info(chat_id)
            else:
                await self._send_general_response(chat_id, text)

        except Exception as e:
            logger.error(f"Ошибка обработки текстового сообщения: {e}")

    async def _register_telegram_user(
        self,
        db: Session,
        user_id: int,
        username: str,
        first_name: str,
        last_name: str,
        language_code: str,
        chat_id: int,
    ):
        """Регистрация или обновление пользователя Telegram"""
        try:
            telegram_user = crud_telegram.get_telegram_user_by_id(db, user_id)

            if not telegram_user:
                # Создаем нового пользователя
                telegram_user = crud_telegram.create_telegram_user(
                    db,
                    {
                        "user_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "language_code": language_code,
                        "chat_id": chat_id,
                        "active": True,
                        "notifications_enabled": True,
                    },
                )
            else:
                # Обновляем существующего пользователя
                crud_telegram.update_telegram_user(
                    db,
                    user_id,
                    {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "language_code": language_code,
                        "chat_id": chat_id,
                        "last_activity": datetime.utcnow(),
                    },
                )

            return telegram_user

        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")
            return None

    async def _send_welcome_message(self, chat_id: int, telegram_user):
        """Отправка приветственного сообщения"""
        message = f"""
🏥 <b>Добро пожаловать в Programma Clinic!</b>

Привет, {telegram_user.first_name}! 👋

Я ваш персональный помощник в клинике. Я могу помочь вам:

📅 <b>Записаться на прием</b> - выберите врача и время
📋 <b>Посмотреть записи</b> - ваши текущие записи
👤 <b>Профиль</b> - информация о вас
⚙️ <b>Настройки</b> - управление уведомлениями
❓ <b>Помощь</b> - список команд

Используйте кнопки ниже или команды для навигации.
        """

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📅 Записаться на прием", "callback_data": "book_menu"},
                    {"text": "📋 Мои записи", "callback_data": "my_appointments"},
                ],
                [
                    {"text": "👤 Профиль", "callback_data": "profile"},
                    {"text": "⚙️ Настройки", "callback_data": "settings"},
                ],
                [
                    {"text": "❓ Помощь", "callback_data": "help"},
                    {"text": "📞 Поддержка", "callback_data": "support"},
                ],
            ]
        }

        await self._send_message(chat_id, message, keyboard)

    async def _send_help_message(self, chat_id: int):
        """Отправка справочной информации"""
        message = """
❓ <b>Справка по командам</b>

<b>Основные команды:</b>
/start - Главное меню
/help - Эта справка
/appointments - Мои записи
/book - Записаться на прием
/profile - Мой профиль
/settings - Настройки
/support - Поддержка

<b>Как записаться на прием:</b>
1. Нажмите "📅 Записаться на прием"
2. Выберите специалиста
3. Выберите дату и время
4. Подтвердите запись

<b>Уведомления:</b>
Я буду напоминать вам о записях, результатах анализов и важных событиях.

<b>Поддержка:</b>
Если у вас есть вопросы, обратитесь к администратору или используйте команду /support
        """

        await self._send_message(chat_id, message)

    async def _send_appointments_list(self, chat_id: int, telegram_user, db: Session):
        """Отправка списка записей пациента"""
        try:
            if not telegram_user.patient_id:
                await self._send_message(
                    chat_id,
                    "❌ Ваш профиль не привязан к пациенту. Обратитесь к администратору.",
                )
                return

            appointments = crud_appointment.get_patient_appointments(
                db, telegram_user.patient_id, upcoming_only=True
            )

            if not appointments:
                message = (
                    "📅 У вас нет предстоящих записей.\n\nХотите записаться на прием?"
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📅 Записаться", "callback_data": "book_menu"}]
                    ]
                }
                await self._send_message(chat_id, message, keyboard)
                return

            message = "📅 <b>Ваши записи:</b>\n\n"
            for i, appointment in enumerate(appointments, 1):
                message += f"{i}. <b>{appointment.doctor_name}</b>\n"
                message += f"   📅 {appointment.date} в {appointment.time}\n"
                message += f"   🏥 {appointment.specialty}\n\n"

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📅 Новая запись", "callback_data": "book_menu"}],
                    [{"text": "🔄 Обновить", "callback_data": "my_appointments"}],
                ]
            }

            await self._send_message(chat_id, message, keyboard)

        except Exception as e:
            logger.error(f"Ошибка получения записей: {e}")
            await self._send_message(
                chat_id, "❌ Ошибка получения записей. Попробуйте позже."
            )

    async def _send_booking_menu(self, chat_id: int, db: Session):
        """Отправка меню записи на прием"""
        try:
            # Получаем список врачей
            doctors = crud_user.get_doctors(db, active_only=True)

            message = "👨‍⚕️ <b>Выберите специалиста:</b>\n\n"

            keyboard_buttons = []
            for doctor in doctors[:10]:  # Ограничиваем до 10 врачей
                button_text = f"👨‍⚕️ {doctor.full_name} ({doctor.specialty})"
                callback_data = f"book_{doctor.id}"
                keyboard_buttons.append(
                    [{"text": button_text, "callback_data": callback_data}]
                )

            keyboard = {"inline_keyboard": keyboard_buttons}

            await self._send_message(chat_id, message, keyboard)

        except Exception as e:
            logger.error(f"Ошибка получения врачей: {e}")
            await self._send_message(chat_id, "❌ Ошибка получения списка врачей.")

    async def _send_message(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ):
        """Отправка сообщения в Telegram"""
        try:
            if not self.bot_token:
                logger.error("Bot token не настроен")
                return False

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                return result.get("ok", False)
            else:
                logger.error(f"Ошибка отправки сообщения: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False

    async def _answer_callback_query(self, callback_query_id: str, text: str = ""):
        """Ответ на callback запрос"""
        try:
            if not self.bot_token:
                return False

            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"

            data = {"callback_query_id": callback_query_id, "text": text}

            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Ошибка ответа на callback: {e}")
            return False

    async def _answer_inline_query(self, query_id: str, results: list[dict]):
        """Ответ на inline запрос"""
        try:
            if not self.bot_token:
                return False

            url = f"https://api.telegram.org/bot{self.bot_token}/answerInlineQuery"

            data = {"inline_query_id": query_id, "results": json.dumps(results)}

            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Ошибка ответа на inline запрос: {e}")
            return False


# Глобальный экземпляр сервиса
telegram_bot_service = TelegramBotService()


async def get_telegram_bot_service() -> TelegramBotService:
    """Получить экземпляр Telegram Bot сервиса"""
    return telegram_bot_service
