"""
Telegram Bot сервис для клиники
Полнофункциональный бот с обработкой команд и webhook
"""

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, UTC
from typing import Any

import httpx
import asyncio
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
MAX_TELEGRAM_DOCUMENT_BYTES = 20 * 1024 * 1024
TELEGRAM_CORRUPTED_TEXT_MARKERS: tuple[tuple[str, str], ...] = (
    ("replacement_character", "\ufffd"),
    ("cyrillic_mojibake_prefix", "\u0420\u045f"),
    ("cyrillic_mojibake_a", "\u0420\u0452"),
    ("cyrillic_mojibake_o", "\u0420\u045b"),
    ("cyrillic_mojibake_s", "\u0421\u0453"),
    ("quote_mojibake", "\u0432\u0402"),
    ("emoji_mojibake", "\u0440\u045f"),
    ("emoji_variation_mojibake", "\u043f\u0451"),
)
PATIENT_BOT_COMMANDS_RU = [
    {"command": "start", "description": "Начать"},
    {"command": "menu", "description": "Главное меню"},
    {"command": "book", "description": "Записаться на приём"},
    {"command": "queue", "description": "Моя очередь"},
    {"command": "visits", "description": "Мои визиты"},
    {"command": "payments", "description": "Оплаты и долг"},
    {"command": "results", "description": "Результаты"},
    {"command": "services", "description": "Онлайн-сервисы"},
    {"command": "forms", "description": "Анкеты пациента"},
    {"command": "documents", "description": "Документы и чеки"},
    {"command": "doctors", "description": "Расписание врачей"},
    {"command": "cabinet", "description": "Кабинет пациента"},
    {"command": "profile", "description": "Мой статус"},
    {"command": "settings", "description": "Язык и уведомления"},
    {"command": "support", "description": "Связаться с клиникой"},
    {"command": "help", "description": "Помощь"},
]
PATIENT_BOT_COMMANDS_UZ = [
    {"command": "start", "description": "Boshlash"},
    {"command": "menu", "description": "Asosiy menyu"},
    {"command": "book", "description": "Qabulga yozilish"},
    {"command": "queue", "description": "Mening navbatim"},
    {"command": "visits", "description": "Mening tashriflarim"},
    {"command": "payments", "description": "To'lovlar va qarz"},
    {"command": "results", "description": "Natijalar"},
    {"command": "services", "description": "Onlayn xizmatlar"},
    {"command": "forms", "description": "Bemor anketalari"},
    {"command": "documents", "description": "Hujjatlar va cheklar"},
    {"command": "doctors", "description": "Shifokorlar jadvali"},
    {"command": "cabinet", "description": "Bemor kabineti"},
    {"command": "profile", "description": "Mening holatim"},
    {"command": "settings", "description": "Til va xabarnomalar"},
    {"command": "support", "description": "Klinika bilan aloqa"},
    {"command": "help", "description": "Yordam"},
]
PATIENT_BOT_MENU_BUTTON = {"type": "commands"}
PATIENT_BOT_PROFILE_TEXTS = [
    {"method": "setMyName", "payload": {"name": "KosMed Clinic"}},
    {
        "method": "setMyDescription",
        "payload": {
            "description": (
                "KosMed Clinic: запись, очередь, оплаты, уведомления и готовые "
                "результаты для пациентов. В меню также видны будущие безопасные "
                "разделы: анкеты, документы, врачи и кабинет. Для привязки "
                "используйте QR с чека или кнопку телефона."
            )
        },
    },
    {
        "method": "setMyShortDescription",
        "payload": {
            "short_description": "Очередь, визиты, оплаты, результаты и сервисы KosMed Clinic."
        },
    },
    {
        "method": "setMyName",
        "payload": {"name": "KosMed Clinic", "language_code": "uz"},
    },
    {
        "method": "setMyDescription",
        "payload": {
            "description": (
                "KosMed Clinic: qabul, navbat, to'lovlar, xabarnomalar va tayyor "
                "natijalar. Menyuda kelajakdagi xavfsiz bo'limlar ham ko'rinadi: "
                "anketalar, hujjatlar, shifokorlar va kabinet. Bog'lash uchun "
                "chekdagi QR kod yoki telefon tugmasidan foydalaning."
            ),
            "language_code": "uz",
        },
    },
    {
        "method": "setMyShortDescription",
        "payload": {
            "short_description": (
                "KosMed Clinic navbat, tashriflar, to'lovlar, natijalar va servislar."
            ),
            "language_code": "uz",
        },
    },
]
STAFF_BOT_COMMANDS_DEFAULT = [
    {"command": "staff", "description": "Staff status"},
    {"command": "queue", "description": "Role queue"},
    {"command": "schedule", "description": "Schedule"},
    {"command": "payments", "description": "Payment statuses"},
    {"command": "reports", "description": "Report readiness"},
    {"command": "summary", "description": "Operational summary"},
    {"command": "help", "description": "Staff help"},
]


def telegram_text_corruption_reason(text: Any) -> str | None:
    """Return a safe reason when outgoing Telegram text is visibly corrupted."""
    value = str(text or "")
    if "????" in value:
        return "question_mark_run"

    for reason, marker in TELEGRAM_CORRUPTED_TEXT_MARKERS:
        if marker in value:
            return reason

    return None


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
                self.bot_token = config.decrypted_bot_token  # TG-AUDIT-28 P1: decrypt
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

    async def process_patient_bot_update(
        self,
        update: dict[str, Any],
        db: Session,
        *,
        staff_start_handler: Callable[..., Awaitable[bool]],
        ticket_start_handler: Callable[..., Awaitable[bool]],
        contact_handler: Callable[..., Awaitable[bool]],
        start_handler: Callable[[int, dict[str, Any]], Awaitable[None]],
        command_handlers: Mapping[str, Callable[[int], Awaitable[None]]],
        text_handlers: Mapping[str, Callable[[int], Awaitable[None]]],
        staff_menu_handler: Callable[..., Awaitable[bool]] | None = None,
    ) -> bool:
        """Dispatch clinic patient bot updates above webhook/polling transports."""
        if await staff_start_handler(update, db, self):
            return True

        if staff_menu_handler and await staff_menu_handler(update, db, self):
            return True

        if await ticket_start_handler(update, db, self):
            return True

        message = update.get("message") or {}
        if not message:
            return False

        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return False
        chat_id = int(chat_id)

        if await contact_handler(message, db, self):
            return True

        text = str(message.get("text") or "").strip()
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
        normalized_text = text.lower()

        if command == "/start":
            await start_handler(chat_id, message)
            return True

        handler = command_handlers.get(command) or text_handlers.get(normalized_text)
        if handler:
            await handler(chat_id)
            return True

        return False

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
                        "last_activity": datetime.now(UTC),
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

    async def _httpx_post(self, url: str, **kwargs) -> dict:
        """HTTPX-AUDIT: async POST replacing sync requests.post."""
        async with httpx.AsyncClient() as client:
            response = await client.post(url, **kwargs)
            return response

    async def _httpx_get(self, url: str, **kwargs) -> dict:
        """HTTPX-AUDIT: async GET replacing sync requests.get."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, **kwargs)
            return response

    async def _send_message(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ):
        """Отправка сообщения в Telegram"""
        try:
            corruption_reason = telegram_text_corruption_reason(text)
            if corruption_reason:
                logger.warning(
                    "Blocked Telegram sendMessage with corrupted text reason=%s text_length=%s",
                    corruption_reason,
                    len(str(text or "")),
                )
                return False

            if not self.bot_token:
                logger.error("Bot token не настроен")
                return False

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            response = await self._httpx_post(url, json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                return result.get("ok", False)
            else:
                logger.error(f"Ошибка отправки сообщения: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False

    async def _send_document(
        self,
        chat_id: int,
        filename: str,
        document_bytes: bytes,
        caption: str = "",
    ) -> tuple[bool, int | None, str | None]:
        """Send a PDF/document to Telegram without logging document contents."""
        if not self.bot_token:
            logger.error("Bot token is not configured for Telegram document send")
            return False, None, "bot_token_not_configured"

        if len(document_bytes) > MAX_TELEGRAM_DOCUMENT_BYTES:
            return False, None, "document_too_large"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        files = {"document": (filename, document_bytes, "application/pdf")}
        try:
            response = await self._httpx_post(url, data=data, files=files, timeout=20)
        except requests.RequestException as exc:
            logger.warning(
                "Telegram document send request failed error_type=%s",
                type(exc).__name__,
            )
            return False, None, type(exc).__name__

        if response.status_code != 200:
            logger.warning(
                "Telegram document send failed status_code=%s",
                response.status_code,
            )
            return False, None, f"telegram_http_{response.status_code}"

        try:
            payload = response.json()
        except ValueError:
            logger.warning("Telegram document send returned invalid json")
            return False, None, "telegram_invalid_json"

        if not payload.get("ok"):
            logger.warning("Telegram document send returned not ok")
            return False, None, "telegram_api_error"

        message_id = (payload.get("result") or {}).get("message_id")
        return True, int(message_id) if message_id is not None else None, None

    async def _set_bot_commands(
        self, bot_token: str | None, payloads: list[dict[str, Any]]
    ) -> tuple[bool, str | None]:
        if not bot_token:
            logger.error("Bot token is not configured for Telegram command registration")
            return False, "bot_token_not_configured"

        url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
        for payload in payloads:
            try:
                response = await self._httpx_post(url, json=payload, timeout=10)
            except requests.RequestException as exc:
                logger.warning(
                    "Telegram command registration request failed error_type=%s",
                    type(exc).__name__,
                )
                return False, type(exc).__name__

            if response.status_code != 200:
                logger.warning(
                    "Telegram command registration failed status_code=%s",
                    response.status_code,
                )
                return False, f"telegram_http_{response.status_code}"

            try:
                result = response.json()
            except ValueError:
                logger.warning("Telegram command registration returned invalid json")
                return False, "telegram_invalid_json"

            if not result.get("ok"):
                logger.warning("Telegram command registration returned not ok")
                return False, "telegram_api_error"

        return True, None

    async def _set_chat_menu_button(
        self, bot_token: str | None, menu_button: dict[str, Any]
    ) -> tuple[bool, str | None]:
        if not bot_token:
            logger.error("Bot token is not configured for Telegram menu button setup")
            return False, "bot_token_not_configured"

        url = f"https://api.telegram.org/bot{bot_token}/setChatMenuButton"
        try:
            response = await self._httpx_post(url, json={"menu_button": menu_button}, timeout=10)
        except requests.RequestException as exc:
            logger.warning(
                "Telegram menu button setup request failed error_type=%s",
                type(exc).__name__,
            )
            return False, type(exc).__name__

        if response.status_code != 200:
            logger.warning(
                "Telegram menu button setup failed status_code=%s",
                response.status_code,
            )
            return False, f"telegram_http_{response.status_code}"

        try:
            result = response.json()
        except ValueError:
            logger.warning("Telegram menu button setup returned invalid json")
            return False, "telegram_invalid_json"

        if not result.get("ok"):
            logger.warning("Telegram menu button setup returned not ok")
            return False, "telegram_api_error"

        return True, None

    async def _set_bot_profile_texts(
        self, bot_token: str | None, profile_texts: list[dict[str, Any]]
    ) -> tuple[bool, str | None]:
        if not bot_token:
            logger.error("Bot token is not configured for Telegram profile setup")
            return False, "bot_token_not_configured"

        for item in profile_texts:
            method = str(item.get("method") or "").strip()
            payload = item.get("payload") or {}
            if not method or not isinstance(payload, dict):
                return False, "telegram_profile_payload_invalid"

            url = f"https://api.telegram.org/bot{bot_token}/{method}"
            try:
                response = await self._httpx_post(url, json=payload, timeout=10)
            except requests.RequestException as exc:
                logger.warning(
                    "Telegram profile setup request failed method=%s error_type=%s",
                    method,
                    type(exc).__name__,
                )
                return False, type(exc).__name__

            if response.status_code != 200:
                logger.warning(
                    "Telegram profile setup failed method=%s status_code=%s",
                    method,
                    response.status_code,
                )
                return False, f"telegram_http_{response.status_code}"

            try:
                result = response.json()
            except ValueError:
                logger.warning(
                    "Telegram profile setup returned invalid json method=%s", method
                )
                return False, "telegram_invalid_json"

            if not result.get("ok"):
                logger.warning(
                    "Telegram profile setup returned not ok method=%s", method
                )
                return False, "telegram_api_error"

        return True, None

    async def set_patient_bot_commands(self) -> tuple[bool, str | None]:
        """Register patient bot command menu in Telegram."""
        ok, error = await self._set_bot_commands(
            self.bot_token,
            [
                {"commands": PATIENT_BOT_COMMANDS_RU},
                # Telegram Bot API rejects "uz-Latn" here; keep app storage canonical
                # as "uz-Latn", but register the command menu with Telegram's "uz".
                {"commands": PATIENT_BOT_COMMANDS_UZ, "language_code": "uz"},
            ],
        )
        if not ok:
            return ok, error
        ok, error = await self._set_chat_menu_button(
            self.bot_token, PATIENT_BOT_MENU_BUTTON
        )
        if not ok:
            return ok, error
        return await self._set_bot_profile_texts(
            self.bot_token, PATIENT_BOT_PROFILE_TEXTS
        )

    async def set_staff_bot_commands(
        self,
        staff_bot_token: str | None,
        commands: list[dict[str, str]] | None = None,
    ) -> tuple[bool, str | None]:
        """Register read-only staff bot commands with the dedicated staff bot."""
        return await self._set_bot_commands(
            staff_bot_token,
            [{"commands": commands or STAFF_BOT_COMMANDS_DEFAULT}],
        )

    async def _answer_callback_query(self, callback_query_id: str, text: str = ""):
        """Ответ на callback запрос"""
        try:
            if not self.bot_token:
                return False

            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"

            data = {"callback_query_id": callback_query_id, "text": text}

            response = await self._httpx_post(url, json=data, timeout=10)
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

            response = await self._httpx_post(url, json=data, timeout=10)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Ошибка ответа на inline запрос: {e}")
            return False


# Глобальный экземпляр сервиса
telegram_bot_service = TelegramBotService()


async def get_telegram_bot_service() -> TelegramBotService:
    """Получить экземпляр Telegram Bot сервиса"""
    return telegram_bot_service
