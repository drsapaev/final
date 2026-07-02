"""
Сервис для работы с Telegram ботом
Основа: passport.md стр. 2064-2570, detail.md стр. 4283-4282
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    Application = None
    Update = None

from app.crud import telegram_config as crud_telegram
from app.db.session import SessionLocal
from app.models.telegram_config import (
    TelegramConfig,
)

# Настройка логирования для Telegram
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramService:
    """Сервис для работы с Telegram ботом"""

    def __init__(self):
        self.bot: Bot | None = None
        self.application: Application | None = None
        self.config: TelegramConfig | None = None
        self.db: Session | None = None

    async def initialize(self) -> bool:
        """Инициализация бота"""
        if not TELEGRAM_AVAILABLE:
            logger.error("python-telegram-bot не установлен")
            return False

        try:
            self.db = SessionLocal()

            # Получаем конфигурацию бота
            self.config = crud_telegram.get_telegram_config(self.db)

            if not self.config or not self.config.bot_token:
                logger.error("Токен Telegram бота не настроен")
                return False

            if not self.config.active:
                logger.error("Telegram бот отключен в настройках")
                return False

            # Создаем бота
            self.bot = Bot(token=self.config.bot_token)

            # Создаем приложение
            self.application = (
                Application.builder().token(self.config.bot_token).build()
            )

            # Регистрируем обработчики
            await self._register_handlers()

            logger.info("Telegram бот инициализирован успешно")
            return True

        except Exception as e:
            logger.error(f"Ошибка инициализации Telegram бота: {e}")
            return False

    async def _register_handlers(self):
        """Регистрация обработчиков команд"""
        if not self.application:
            return

        # Команды
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("queue", self._handle_queue))
        self.application.add_handler(
            CommandHandler("appointments", self._handle_appointments)
        )
        self.application.add_handler(CommandHandler("results", self._handle_results))
        self.application.add_handler(CommandHandler("cancel", self._handle_cancel))

        # Callback queries (inline кнопки)
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

        # Текстовые сообщения
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Контакты (для регистрации по номеру телефона)
        self.application.add_handler(
            MessageHandler(filters.CONTACT, self._handle_contact)
        )

    async def _handle_start(self, update, context) -> None:
        """Обработчик команды /start"""
        try:
            chat_id = update.effective_chat.id
            user = update.effective_user

            # Регистрируем пользователя
            await self._register_telegram_user(chat_id, user)

            # Получаем шаблон приветствия
            welcome_template = crud_telegram.get_template_by_key(
                self.db, "welcome_message", user.language_code or "ru"
            )

            if welcome_template:
                message_text = self._render_template(
                    welcome_template.message_text,
                    {
                        "user_name": user.first_name or "Пациент",
                        "clinic_name": "Медицинская клиника",
                    },
                )
            else:
                message_text = f"""
🏥 <b>Добро пожаловать в медицинскую клинику!</b>

Привет, {user.first_name or 'Пациент'}! 👋

Я помогу вам:
📅 Записаться на прием
📱 Получить QR код для очереди
🔔 Получать уведомления
📋 Просматривать результаты анализов

<b>Команды:</b>
/queue - Онлайн очередь
/appointments - Мои записи
/results - Результаты анализов
/help - Помощь
"""

            # Создаем клавиатуру
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📅 Записаться на прием", callback_data="book_appointment"
                    ),
                    InlineKeyboardButton("📱 QR очередь", callback_data="get_qr"),
                ],
                [
                    InlineKeyboardButton(
                        "📋 Мои записи", callback_data="my_appointments"
                    ),
                    InlineKeyboardButton("🧪 Результаты", callback_data="my_results"),
                ],
                [InlineKeyboardButton("ℹ️ Справка", callback_data="help")],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                message_text, parse_mode='HTML', reply_markup=reply_markup
            )

            # Логируем сообщение
            await self._log_message(chat_id, "start", message_text, "bot_to_user")

        except Exception as e:
            logger.error(f"Ошибка обработки /start: {e}")

    async def _handle_help(self, update, context) -> None:
        """Обработчик команды /help"""
        help_text = """
🤖 <b>Помощь по боту клиники</b>

<b>Доступные команды:</b>
/start - Главное меню
/queue - Онлайн очередь и QR коды
/appointments - Просмотр записей
/results - Результаты анализов
/cancel - Отмена текущего действия

<b>Функции:</b>
📱 <b>QR очередь</b> - получите QR код для записи в онлайн очередь
📅 <b>Записи</b> - просматривайте свои записи к врачам
🔔 <b>Уведомления</b> - получайте напоминания о приемах
🧪 <b>Результаты</b> - получайте готовые анализы

<b>Поддержка:</b> @clinic_support
"""

        await update.message.reply_text(help_text, parse_mode='HTML')

    async def _handle_queue(self, update, context) -> None:
        """Обработчик команды /queue"""
        try:
            _chat_id = update.effective_chat.id

            # Получаем доступные специальности для QR
            specialties = await self._get_available_specialties()

            if not specialties:
                await update.message.reply_text(
                    "❌ В данный момент QR коды недоступны.\nОбратитесь в регистратуру."
                )
                return

            # Создаем клавиатуру выбора специальности
            keyboard = []
            for specialty in specialties:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{specialty['icon']} {specialty['name']}",
                            callback_data=f"qr_{specialty['code']}",
                        )
                    ]
                )

            keyboard.append(
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
            )

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "📱 <b>Выберите специальность для получения QR кода:</b>",
                parse_mode='HTML',
                reply_markup=reply_markup,
            )

        except Exception as e:
            logger.error(f"Ошибка обработки /queue: {e}")

    async def _handle_callback(self, update, context) -> None:
        """Обработчик inline кнопок"""
        try:
            query = update.callback_query
            await query.answer()

            data = query.data
            _chat_id = query.message.chat_id

            if data == "get_qr":
                await self._handle_queue(update, context)
            elif data == "book_appointment":
                await self._handle_book_appointment(query)
            elif data == "my_appointments":
                await self._handle_my_appointments(query)
            elif data == "my_results":
                await self._handle_my_results(query)
            elif data.startswith("qr_"):
                specialty = data.replace("qr_", "")
                await self._generate_qr_code(query, specialty)
            elif data == "back_to_main":
                await self._handle_start(update, context)
            else:
                await query.edit_message_text("❌ Неизвестная команда")

        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")

    async def _handle_message(self, update, context) -> None:
        """Обработчик текстовых сообщений"""
        try:
            message_text = update.message.text
            _chat_id = update.effective_chat.id

            # Простая логика обработки
            if "запись" in message_text.lower() or "записаться" in message_text.lower():
                await update.message.reply_text(
                    "📅 Для записи на прием используйте кнопку в главном меню или команду /queue"
                )
            elif "очередь" in message_text.lower() or "qr" in message_text.lower():
                await self._handle_queue(update, context)
            elif (
                "результат" in message_text.lower() or "анализ" in message_text.lower()
            ):
                await update.message.reply_text(
                    "🧪 Для просмотра результатов используйте команду /results"
                )
            else:
                await update.message.reply_text(
                    "🤖 Не понимаю команду. Используйте /help для справки."
                )

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")

    async def _handle_contact(self, update, context) -> None:
        """Обработчик контактов (регистрация по телефону)"""
        try:
            contact = update.message.contact
            chat_id = update.effective_chat.id

            if contact.user_id == update.effective_user.id:
                # Пользователь поделился своим контактом
                phone = contact.phone_number

                # Ищем пациента по номеру телефона
                patient = await self._find_patient_by_phone(phone)

                if patient:
                    # Связываем Telegram аккаунт с пациентом
                    await self._link_patient_to_telegram(chat_id, patient['id'])

                    await update.message.reply_text(
                        f"✅ Аккаунт привязан к пациенту: {patient['full_name']}\n"
                        "Теперь вы можете получать уведомления о записях и результатах."
                    )
                else:
                    await update.message.reply_text(
                        "❌ Пациент с таким номером не найден.\n"
                        "Обратитесь в регистратуру для регистрации."
                    )

        except Exception as e:
            logger.error(f"Ошибка обработки контакта: {e}")

    async def _register_telegram_user(self, chat_id: int, user) -> None:
        """Регистрация пользователя Telegram"""
        try:
            existing = crud_telegram.get_telegram_user_by_chat_id(self.db, chat_id)

            if not existing:
                user_data = {
                    "chat_id": chat_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code or "ru",
                    "active": True,
                    "last_activity": datetime.utcnow(),
                }

                crud_telegram.create_telegram_user(self.db, user_data)
                logger.info(f"Зарегистрирован новый пользователь: {chat_id}")
            else:
                # Обновляем активность
                crud_telegram.update_telegram_user(
                    self.db,
                    existing.id,
                    {"last_activity": datetime.utcnow(), "active": True},
                )

        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")

    async def _get_available_specialties(self) -> list[dict[str, Any]]:
        """Получить доступные специальности для QR"""
        try:
            # Здесь будет интеграция с API онлайн-очереди
            specialties = [
                {"code": "cardiology", "name": "Кардиология", "icon": "❤️"},
                {"code": "dermatology", "name": "Дерматология", "icon": "🩺"},
                {"code": "stomatology", "name": "Стоматология", "icon": "🦷"},
                {"code": "therapy", "name": "Терапия", "icon": "👨‍⚕️"},
            ]

            return specialties

        except Exception as e:
            logger.error(f"Ошибка получения специальностей: {e}")
            return []

    async def _generate_qr_code(self, query, specialty: str) -> None:
        """Генерация QR кода для специальности"""
        try:
            # Интеграция с API онлайн-очереди
            from datetime import date


            tomorrow = (date.today() + timedelta(days=1)).isoformat()

            # Здесь будет реальный вызов API
            qr_data = {
                "success": True,
                "token": f"QR_{specialty}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "specialty": specialty,
                "date": tomorrow,
                "time_window": "07:00-09:00",
            }

            if qr_data["success"]:
                # Создаем сообщение с QR кодом
                message_text = f"""
📱 <b>QR код для онлайн-очереди</b>

🏥 <b>Специальность:</b> {specialty.title()}
📅 <b>Дата:</b> {tomorrow}
⏰ <b>Окно записи:</b> {qr_data['time_window']}

<code>{qr_data['token']}</code>

<b>Как использовать:</b>
1. Сохраните этот код
2. Зайдите на сайт клиники в {qr_data['time_window']}
3. Введите код для получения номера в очереди

⚠️ <b>Важно:</b> Код действителен только в указанное время!
"""

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔗 Открыть сайт", url="https://clinic.example.com/queue"
                        )
                    ],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")],
                ]

                await query.edit_message_text(
                    message_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            else:
                await query.edit_message_text(
                    "❌ Не удалось создать QR код. Попробуйте позже."
                )

        except Exception as e:
            logger.error(f"Ошибка генерации QR кода: {e}")

    async def send_notification(
        self,
        chat_id: int,
        template_key: str,
        data: dict[str, Any],
        language: str = "ru",
    ) -> bool:
        """Отправка уведомления пользователю"""
        try:
            if not self.bot:
                return False

            # Получаем шаблон
            template = crud_telegram.get_template_by_key(
                self.db, template_key, language
            )

            if not template:
                logger.error(f"Шаблон {template_key} не найден")
                return False

            # Рендерим сообщение
            message_text = self._render_template(template.message_text, data)

            # Создаем клавиатуру если есть кнопки
            reply_markup = None
            if template.inline_buttons:
                keyboard = []
                for button in template.inline_buttons:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                button["text"], callback_data=button["callback_data"]
                            )
                        ]
                    )
                reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode=template.parse_mode,
                disable_web_page_preview=template.disable_web_page_preview,
                reply_markup=reply_markup,
            )

            # Логируем
            await self._log_message(chat_id, template_key, message_text, "bot_to_user")

            return True

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
            return False

    def _render_template(self, template_text: str, data: dict[str, Any]) -> str:
        """Рендеринг шаблона сообщения"""
        try:
            from jinja2 import Environment

            env = Environment()
            template = env.from_string(template_text)
            return template.render(**data)
        except Exception as e:
            logger.error(f"Ошибка рендеринга шаблона: {e}")
            return template_text

    async def _log_message(
        self, chat_id: int, message_type: str, content: str, direction: str
    ) -> None:
        """Логирование сообщений"""
        try:
            log_data = {
                "chat_id": chat_id,
                "message_type": message_type,
                "content": content[:1000],  # Ограничиваем размер
                "direction": direction,
                "status": "sent",
            }

            crud_telegram.create_message_log(self.db, log_data)

        except Exception as e:
            logger.error(f"Ошибка логирования сообщения: {e}")

    async def start_bot(self) -> None:
        """Запуск бота"""
        try:
            if not await self.initialize():
                logger.error("Не удалось инициализировать бота")
                return

            logger.info("Запуск Telegram бота...")
            await self.application.run_polling()

        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")

    async def stop_bot(self) -> None:
        """Остановка бота"""
        try:
            if self.application:
                await self.application.stop()
                logger.info("Telegram бот остановлен")

            if self.db:
                self.db.close()

        except Exception as e:
            logger.error(f"Ошибка остановки бота: {e}")


# Глобальный экземпляр сервиса
telegram_service: TelegramService | None = None


def get_telegram_service() -> TelegramService:
    """Получить экземпляр Telegram сервиса"""
    global telegram_service
    if telegram_service is None:
        telegram_service = TelegramService()
    return telegram_service


async def send_telegram_notification(
    chat_id: int, template_key: str, data: dict[str, Any], language: str = "ru"
) -> bool:
    """Быстрая отправка уведомления"""
    service = get_telegram_service()
    return await service.send_notification(chat_id, template_key, data, language)
