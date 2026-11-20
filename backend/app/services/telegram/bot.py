"""
Telegram бот для системы клиники
"""

import logging
import re
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from starlette.concurrency import run_in_threadpool

from ...core.config import settings
from ...core.logging_config import protect_telegram_preview_logs
from ...db.session import SessionLocal
from ..appointment_rsvp import (
    apply_appointment_decision,
    make_appointment_callback,
    parse_appointment_callback,
    preview_appointment_decision,
)
from ..queue_service import QueueBusinessService

logger = logging.getLogger(__name__)


def _markdown_escape(value: object) -> str:
    """Escape dynamic fields for Telegram's legacy Markdown parse mode."""
    return re.sub(r"([\\_*\[\]()`])", r"\\\1", str(value))


def _private_callback_actor(callback: types.CallbackQuery) -> int | None:
    """Trust identity only from the authenticated Telegram private ingress."""
    message = callback.message
    chat = getattr(message, "chat", None)
    actor = getattr(callback.from_user, "id", None)
    chat_id = getattr(chat, "id", None)
    if (
        getattr(chat, "type", None) != "private"
        or isinstance(actor, bool)
        or not isinstance(actor, int)
        or actor <= 0
        or actor != chat_id
    ):
        return None
    return actor


def _run_appointment_decision(callback_data: str, chat_id: int) -> str:
    with SessionLocal() as db:
        return apply_appointment_decision(
            db, callback_data=callback_data, chat_id=chat_id
        )


def _run_appointment_preview(callback_data: str, chat_id: int) -> dict | None:
    with SessionLocal() as db:
        return preview_appointment_decision(db, callback_data=callback_data, chat_id=chat_id)


def _run_visit_preview(token: str, actor: int) -> dict | None:
    from ..visit_confirmation_service import VisitConfirmationService

    with SessionLocal() as db:
        try:
            return VisitConfirmationService(db).preview_by_telegram(token=token, telegram_user_id=str(actor))
        finally:
            db.rollback()


def _run_visit_decision(token: str, actor: int, confirm: bool) -> dict[str, Any]:
    # Called only after Telegram's webhook validation and private-chat check;
    # caller-supplied public JSON cannot assert a Telegram identity.
    from ..visit_confirmation_service import VisitConfirmationService

    with SessionLocal() as db:
        service = VisitConfirmationService(db)
        method = service.confirm_by_telegram if confirm else service.cancel_by_telegram
        return method(
            token=token, telegram_user_id=str(actor), source_ip=None, user_agent="telegram"
        )


"""P1-18: This is the PATIENT bot (aiogram-based, env-var token).
Use services/telegram_bot.py:TelegramBotService for the STAFF bot
(httpx-based, DB-stored token). Do not confuse the two.
"""
class ClinicTelegramBot:
    """Telegram бот клиники"""

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
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
    ) -> dict[str, Any]:
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
            logger.error("Telegram invitation failed error_type=%s", type(e).__name__)
            return {"success": False, "error": "Telegram delivery failed"}

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

    async def handle_start(self, message: types.Message):
        """Обработка команды /start"""
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
        if not data:
            await callback.answer("Пустая команда", show_alert=True)
            return

        try:
            if data.startswith("view_visit:"):
                await self._handle_visit_preview(callback, data.split(":", 1)[1])
                return

            if data.startswith("confirm_visit:") or data.startswith("cancel_visit:"):
                if _private_callback_actor(callback) is None:
                    await callback.answer("Действие недоступно", show_alert=True)
                    return
                confirm = data.startswith("confirm_visit:")
                token = data.split(":", 1)[1]
                answered = await self._handle_visit_confirmation(
                    callback, token, confirm
                )
                if not answered:
                    await callback.answer()
                return

            if data.startswith("ar:"):
                await self._handle_appointment_decision(callback, data)
                return

            if data.startswith("confirm_") or data.startswith("cancel_"):
                # Previous buttons were unbound to a specific occurrence.
                await callback.answer("Напоминание устарело; запросите новое", show_alert=True)
                return

            if data.startswith("queue_"):
                await self._handle_queue_callback(callback, data)
            elif data == "appointment":
                await self.handle_appointment(callback.message)
            elif data == "my_appointments":
                await self._handle_my_appointments(callback)
            elif data == "help":
                await self.handle_help(callback.message)
            else:
                await callback.answer("Неизвестная команда", show_alert=True)
                return

            await callback.answer()

        except Exception as e:
            logger.error("Telegram callback failed error_type=%s", type(e).__name__)
            try:
                await callback.answer("Произошла ошибка", show_alert=True)
            except Exception:
                pass

    async def _handle_appointment_decision(self, callback: types.CallbackQuery, data: str) -> None:
        """Persist one authenticated RSVP, then acknowledge exactly once."""
        actor = _private_callback_actor(callback)
        parsed = parse_appointment_callback(data) if actor is not None else None
        if parsed is not None and parsed[0] == "v":
            await self._handle_appointment_preview(callback, data, actor)
            return
        result = "unavailable"
        if parsed is not None:
            try:
                result = await run_in_threadpool(
                    _run_appointment_decision, data, actor
                )
            except Exception as exc:
                logger.error("Appointment callback failed error_type=%s", type(exc).__name__)
        if result in {"confirmed", "already_confirmed", "cancelled"}:
            message = {
                "confirmed": "✅ Запись подтверждена",
                "already_confirmed": "✅ Запись уже подтверждена",
                "cancelled": "✅ Запись отменена",
            }[result]
            try:
                previous = getattr(callback.message, "text", None) or ""
                await callback.message.edit_text(text=f"{previous}\n\n{message}")
            except Exception as exc:
                # The commit already happened; do not misreport a UI edit as
                # a failed decision or retry the mutation.
                logger.warning("Appointment callback edit failed error_type=%s", type(exc).__name__)
            try:
                await callback.answer(message)
            except Exception:
                logger.warning("Appointment callback acknowledgement failed")
            return
        message = "Напоминание устарело; запросите новое" if result == "stale" else "Действие недоступно"
        try:
            await callback.answer(message, show_alert=True)
        except Exception:
            logger.warning("Appointment callback acknowledgement failed")

    async def _handle_appointment_preview(self, callback, data: str, actor: int) -> None:
        try:
            preview = await run_in_threadpool(_run_appointment_preview, data, actor)
            if not preview:
                await callback.answer("Запись недоступна", show_alert=True)
                return
            buttons = [InlineKeyboardButton(text="✅ Подтвердить", callback_data=preview["confirm_data"])]
            if preview["cancel_data"]:
                buttons.append(InlineKeyboardButton(text="❌ Отменить", callback_data=preview["cancel_data"]))
            await callback.message.answer(
                text=preview["text"], parse_mode=None,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]),
            )
            await callback.answer()
        except Exception as exc:
            logger.error("Appointment preview failed error_type=%s", type(exc).__name__)
            await callback.answer("Не удалось показать запись", show_alert=True)

    async def _handle_visit_preview(self, callback, token: str) -> None:
        actor = _private_callback_actor(callback)
        if actor is None:
            await callback.answer("Действие недоступно", show_alert=True)
            return
        try:
            preview = await run_in_threadpool(_run_visit_preview, token, actor)
            if not preview:
                await callback.answer("Визит недоступен", show_alert=True)
                return
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Открыть визит", url=preview["view_url"])],
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_visit:{preview['action_token']}"),
                 InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_visit:{preview['action_token']}")],
            ])
            with protect_telegram_preview_logs():
                await callback.message.answer(text=preview["text"], parse_mode=None, reply_markup=keyboard)
            await callback.answer()
        except Exception as exc:
            logger.error("Visit preview failed error_type=%s", type(exc).__name__)
            await callback.answer("Не удалось показать визит", show_alert=True)

    async def _handle_queue_callback(self, callback: types.CallbackQuery, data: str):
        """Обработка выбора специалиста для очереди"""
        specialist_map = {
            # P3: hardcoded specialist IDs — should query DB (Specialty table)
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

        except Exception:
            logger.error("Internal error")
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
        keyboard: InlineKeyboardMarkup | None = None,
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
            logger.error("Telegram delivery failed error_type=%s", type(e).__name__)
            return False

    async def send_appointment_reminder(
        self, user_id: int, appointment_data: dict[str, Any]
    ):
        """Отправка напоминания о визите"""
        try:
            appointment_id = appointment_data["id"]
            revision = appointment_data["occurrence_revision"]
            link_id = appointment_data["telegram_link_id"]
            link_epoch = appointment_data["patient_link_epoch"]
            view_data = make_appointment_callback("v", appointment_id, revision, user_id, link_id, link_epoch)
        except (KeyError, TypeError, ValueError):
            logger.warning("Appointment reminder missing a valid occurrence")
            return False

        message = "У вас новое уведомление. Откройте его в личном чате."

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Просмотреть", callback_data=view_data),
                ]
            ]
        )

        return await self.send_notification(user_id, message, keyboard)

    async def send_lab_results_ready(self, user_id: int, results_info: dict[str, Any]):
        """Уведомление о готовности результатов"""
        message = f"""
🔬 *Результаты анализов готовы*

📋 Исследование: {_markdown_escape(results_info.get('test_name') or 'Анализы')}
📅 Дата: {_markdown_escape(results_info.get('date') or 'не указана')}

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

        return await self.send_notification(user_id, message, keyboard)

    async def setup_webhook(self, webhook_url: str, secret_token: str | None = None):
        """Настройка webhook"""
        if not self.bot:
            return False

        try:
            webhook_kwargs = {}
            if secret_token:
                webhook_kwargs["secret_token"] = secret_token
            await self.bot.set_webhook(webhook_url, **webhook_kwargs)
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

    def get_webhook_handler(self, secret_token: str | None = None):
        """Получить обработчик webhook для aiohttp"""
        if not self.bot or not self.dp or not secret_token:
            return None

        return SimpleRequestHandler(dispatcher=self.dp, bot=self.bot, secret_token=secret_token)

    async def _handle_visit_confirmation(
        self, callback: types.CallbackQuery, token: str, confirm: bool
    ) -> bool:
        """Обрабатывает подтверждение или отмену визита.

        Возвращает True, если callback уже был подтвержден/обработан через answer().
        """
        if _private_callback_actor(callback) is None:
            try:
                await callback.answer("Действие недоступно", show_alert=True)
            except Exception:
                pass
            return True

        # TGCONFIRM-BE-002/BE-003: если серверная операция (подтверждение
        # или отмена) уже закоммичена, падение рендера/редактирования НЕ
        # должно повторять операцию и не должно показывать generic-ошибку
        # на коммитнутый успех. committed хранит тип операции.
        committed: str | None = None
        try:
            if confirm:
                # Подтверждаем визит через API
                result = await self._confirm_visit_via_api(token, callback.from_user.id)

                if result.get("success"):
                    committed = "confirm"
                    message = "✅ Визит успешно подтвержден!"
                    queue_entries = result.get("queue_numbers") or []
                    if queue_entries:
                        # TGCONFIRM-BE-002: authoritative VisitConfirmationService
                        # отдаёт queue_tag/number/queue_id БЕЗ queue_name.
                        # Форматируем безопасно: queue_name -> queue_tag ->
                        # queue_id, неизвестное — честный fallback, не KeyError.
                        def _queue_label(q: dict) -> str:
                            return (
                                q.get("queue_name")
                                or q.get("queue_tag")
                                or f"Очередь #{q.get('queue_id', '?')}"
                            )

                        queue_info = ", ".join(
                            [
                                f"{_queue_label(q)}: №{q.get('number', '?')}"
                                for q in queue_entries
                                if isinstance(q, dict)
                            ]
                        )
                        if queue_info:
                            message += f"\n\n🎫 Ваши номера в очередях:\n{queue_info}"

                    await callback.message.edit_text(
                        text=f"{callback.message.text}\n\n{message}",
                    )
                    return False

                await callback.answer("Не удалось подтвердить визит", show_alert=True)
                return True

            # Отменяем визит через API (TGCONFIRM-BE-003): отмена должна
            # реально сохраниться и инвалидировать токен — не только
            # редактировать сообщение. Честный отказ, если API не отменил.
            result = await self._cancel_visit_via_api(token, callback.from_user.id)

            if result.get("success"):
                committed = "cancel"
                await callback.message.edit_text(
                    text=f"{callback.message.text}\n\n❌ Визит отменен",
                )
                return False

            await callback.answer("Не удалось отменить визит", show_alert=True)
            return True

        except Exception as e:
            logger.error("Visit callback failed error_type=%s", type(e).__name__)
            try:
                if committed == "confirm":
                    # TGCONFIRM-BE-002: подтверждение уже закоммичено —
                    # сообщаем об успехе операции, а не о generic-ошибке.
                    await callback.answer(
                        "✅ Визит подтвержден; не удалось обновить сообщение — номера в очереди уточните у регистратуры",
                        show_alert=True,
                    )
                elif committed == "cancel":
                    # TGCONFIRM-BE-003: отмена уже закоммичена на бэкенде.
                    await callback.answer(
                        "✅ Визит отменен; не удалось обновить сообщение",
                        show_alert=True,
                    )
                else:
                    await callback.answer(
                        "Произошла ошибка при подтверждении", show_alert=True
                    )
            except Exception:
                pass
            return True

    async def _confirm_visit_via_api(
        self, token: str, telegram_user_id: int
    ) -> dict[str, Any]:
        """Use the internal service, not an unauthenticated identity claim."""
        try:
            return await run_in_threadpool(_run_visit_decision, token, telegram_user_id, True)
        except Exception as e:
            logger.error("Visit confirmation failed error_type=%s", type(e).__name__)
            return {"success": False, "message": "Подтверждение временно недоступно"}

    async def _cancel_visit_via_api(
        self, token: str, telegram_user_id: int
    ) -> dict[str, Any]:
        """Use the internal service with a Telegram-authenticated identity."""
        try:
            return await run_in_threadpool(_run_visit_decision, token, telegram_user_id, False)
        except Exception as e:
            logger.error("Visit cancellation failed error_type=%s", type(e).__name__)
            return {"success": False, "message": "Отмена временно недоступна"}


# Глобальный экземпляр бота
telegram_bot = ClinicTelegramBot()


class TelegramBotService:
    """Сервис для работы с Telegram ботом"""

    def __init__(self):
        self.bot = telegram_bot

    async def send_confirmation_invitation(
        self, chat_id: int, message: str, keyboard: list
    ) -> dict[str, Any]:
        """Отправляет приглашение на подтверждение визита"""
        if not self.bot or not self.bot.bot:
            return {"success": False, "error": "Telegram bot не доступен"}

        return await self.bot.send_confirmation_invitation(chat_id, message, keyboard)
