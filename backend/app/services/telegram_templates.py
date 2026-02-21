"""
Сервис шаблонов сообщений для Telegram бота
Поддерживает многоязычность и персонализацию
"""

from typing import Any


class TelegramTemplatesService:
    def __init__(self):
        self.templates = self._load_default_templates()

    def _load_default_templates(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Загрузка базовых шаблонов сообщений"""
        return {
            "welcome": {
                "ru": {
                    "text": "🏥 <b>Добро пожаловать в Programma Clinic!</b>\n\nПривет, {first_name}! 👋\n\nЯ ваш персональный помощник в клинике. Я могу помочь вам:\n\n📅 <b>Записаться на прием</b> - выберите врача и время\n📋 <b>Посмотреть записи</b> - ваши текущие записи\n👤 <b>Профиль</b> - информация о вас\n⚙️ <b>Настройки</b> - управление уведомлениями\n❓ <b>Помощь</b> - список команд\n\nИспользуйте кнопки ниже или команды для навигации.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📅 Записаться на прием",
                                    "callback_data": "book_menu",
                                },
                                {
                                    "text": "📋 Мои записи",
                                    "callback_data": "my_appointments",
                                },
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
                    },
                },
                "uz": {
                    "text": "🏥 <b>Programma Clinic-ga xush kelibsiz!</b>\n\nSalom, {first_name}! 👋\n\nMen sizning shaxsiy yordamchingizman. Men sizga quyidagilarda yordam bera olaman:\n\n📅 <b>Qabulga yozilish</b> - shifokor va vaqtni tanlang\n📋 <b>Qabullarni ko'rish</b> - joriy qabullaringiz\n👤 <b>Profil</b> - siz haqingizda ma'lumot\n⚙️ <b>Sozlamalar</b> - bildirishnomalarni boshqarish\n❓ <b>Yordam</b> - buyruqlar ro'yxati\n\nNavigatsiya uchun quyidagi tugmalardan foydalaning.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📅 Qabulga yozilish",
                                    "callback_data": "book_menu",
                                },
                                {
                                    "text": "📋 Mening qabullarim",
                                    "callback_data": "my_appointments",
                                },
                            ],
                            [
                                {"text": "👤 Profil", "callback_data": "profile"},
                                {"text": "⚙️ Sozlamalar", "callback_data": "settings"},
                            ],
                            [
                                {"text": "❓ Yordam", "callback_data": "help"},
                                {
                                    "text": "📞 Qo'llab-quvvatlash",
                                    "callback_data": "support",
                                },
                            ],
                        ]
                    },
                },
            },
            "appointment_reminder": {
                "ru": {
                    "text": "🔔 <b>Напоминание о приеме</b>\n\nЗдравствуйте, {patient_name}!\n\nНапоминаем о приеме:\n📅 <b>Дата:</b> {appointment_date}\n🕐 <b>Время:</b> {appointment_time}\n👨‍⚕️ <b>Врач:</b> {doctor_name}\n🏥 <b>Специализация:</b> {specialty}\n🏢 <b>Кабинет:</b> {cabinet}\n\n📍 <b>Адрес:</b> {clinic_address}\n📞 <b>Телефон:</b> {clinic_phone}\n\nПодтвердите или выберите действие:",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "✅ Подтвердить",
                                    "callback_data": "confirm_{appointment_id}",
                                },
                                {
                                    "text": "🔁 Перенести",
                                    "callback_data": "reschedule_{appointment_id}",
                                },
                            ],
                            [
                                {
                                    "text": "❌ Отменить",
                                    "callback_data": "cancel_{appointment_id}",
                                },
                                {
                                    "text": "📍 Маршрут",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                        ]
                    },
                },
                "uz": {
                    "text": "🔔 <b>Qabul haqida eslatma</b>\n\nAssalomu alaykum, {patient_name}!\n\nQabul haqida eslatma:\n📅 <b>Sana:</b> {appointment_date}\n🕐 <b>Vaqt:</b> {appointment_time}\n👨‍⚕️ <b>Shifokor:</b> {doctor_name}\n🏥 <b>Mutaxassislik:</b> {specialty}\n🏢 <b>Xona:</b> {cabinet}\n\n📍 <b>Manzil:</b> {clinic_address}\n📞 <b>Telefon:</b> {clinic_phone}\n\nTasdiqlang yoki amalni tanlang:",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "✅ Tasdiqlash",
                                    "callback_data": "confirm_{appointment_id}",
                                },
                                {
                                    "text": "🔁 Ko'chirish",
                                    "callback_data": "reschedule_{appointment_id}",
                                },
                            ],
                            [
                                {
                                    "text": "❌ Bekor qilish",
                                    "callback_data": "cancel_{appointment_id}",
                                },
                                {
                                    "text": "📍 Yo'l",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                        ]
                    },
                },
            },
            "lab_results_ready": {
                "ru": {
                    "text": "🧪 <b>Результаты анализов готовы</b>\n\nЗдравствуйте, {patient_name}!\n\nГотовы результаты анализов:\n📋 <b>Тип исследования:</b> {test_type}\n📅 <b>Дата забора:</b> {collection_date}\n✅ <b>Готовность:</b> {ready_date}\n\n{abnormalities_text}\n\nВы можете получить их в клинике или скачать по ссылке ниже.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📄 Скачать результаты",
                                    "url": "{download_link}",
                                },
                                {
                                    "text": "📞 Связаться с врачом",
                                    "callback_data": "contact_doctor_{doctor_id}",
                                },
                            ],
                            [
                                {
                                    "text": "📅 Записаться на прием",
                                    "callback_data": "book_appointment",
                                },
                                {
                                    "text": "🏥 Прийти в клинику",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                        ]
                    },
                },
                "uz": {
                    "text": "🧪 <b>Tahlil natijalari tayyor</b>\n\nAssalomu alaykum, {patient_name}!\n\nTahlil natijalari tayyor:\n📋 <b>Tadqiqot turi:</b> {test_type}\n📅 <b>Olish sanasi:</b> {collection_date}\n✅ <b>Tayyorlik:</b> {ready_date}\n\n{abnormalities_text}\n\nUlarni klinikadan olishingiz yoki quyidagi havoladan yuklab olishingiz mumkin.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📄 Natijalarni yuklab olish",
                                    "url": "{download_link}",
                                },
                                {
                                    "text": "📞 Shifokor bilan bog'lanish",
                                    "callback_data": "contact_doctor_{doctor_id}",
                                },
                            ],
                            [
                                {
                                    "text": "📅 Qabulga yozilish",
                                    "callback_data": "book_appointment",
                                },
                                {
                                    "text": "🏥 Klinikaga kelish",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                        ]
                    },
                },
            },
            "payment_confirmation": {
                "ru": {
                    "text": "💳 <b>Платеж подтвержден</b>\n\nПлатеж на сумму <b>{amount} {currency}</b> успешно обработан.\n\n📋 <b>Детали платежа:</b>\n💳 <b>Способ оплаты:</b> {payment_method}\n📅 <b>Дата:</b> {payment_date}\n🆔 <b>Номер транзакции:</b> {transaction_id}\n\nСпасибо за оплату!\n\nЧек можете скачать по ссылке ниже.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {"text": "🧾 Скачать чек", "url": "{receipt_link}"},
                                {
                                    "text": "📋 История платежей",
                                    "callback_data": "payment_history",
                                },
                            ],
                            [
                                {
                                    "text": "📅 Мои записи",
                                    "callback_data": "my_appointments",
                                },
                                {
                                    "text": "🏠 Главное меню",
                                    "callback_data": "main_menu",
                                },
                            ],
                        ]
                    },
                },
                "uz": {
                    "text": "💳 <b>To'lov tasdiqlandi</b>\n\n<b>{amount} {currency}</b> miqdoridagi to'lov muvaffaqiyatli amalga oshirildi.\n\n📋 <b>To'lov tafsilotlari:</b>\n💳 <b>To'lov usuli:</b> {payment_method}\n📅 <b>Sana:</b> {payment_date}\n🆔 <b>Tranzaksiya raqami:</b> {transaction_id}\n\nTo'lov uchun rahmat!\n\nChekni quyidagi havoladan yuklab olishingiz mumkin.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "🧾 Chekni yuklab olish",
                                    "url": "{receipt_link}",
                                },
                                {
                                    "text": "📋 To'lovlar tarixi",
                                    "callback_data": "payment_history",
                                },
                            ],
                            [
                                {
                                    "text": "📅 Mening qabullarim",
                                    "callback_data": "my_appointments",
                                },
                                {
                                    "text": "🏠 Asosiy menyu",
                                    "callback_data": "main_menu",
                                },
                            ],
                        ]
                    },
                },
            },
            "qr_code_message": {
                "ru": {
                    "text": "📱 <b>QR код для онлайн-очереди</b>\n\n👨‍⚕️ <b>Врач:</b> {doctor_name}\n🏥 <b>Специализация:</b> {specialty}\n📅 <b>Дата:</b> {date}\n🕐 <b>Временное окно:</b> {time_window}\n\nОтсканируйте QR код или перейдите по ссылке для входа в очередь:\n\n🔗 <b>Ссылка:</b> {queue_url}?token={qr_token}\n\n⚠️ <b>Важно:</b> Приходите в указанное время. QR код действителен только в день приема.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📱 Открыть очередь",
                                    "url": "{queue_url}?token={qr_token}",
                                },
                                {
                                    "text": "📍 Маршрут",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                            [
                                {"text": "📞 Поддержка", "callback_data": "support"},
                                {
                                    "text": "🔄 Обновить",
                                    "callback_data": "refresh_qr_{appointment_id}",
                                },
                            ],
                        ]
                    },
                },
                "uz": {
                    "text": "📱 <b>Onlayn navbat uchun QR kod</b>\n\n👨‍⚕️ <b>Shifokor:</b> {doctor_name}\n🏥 <b>Mutaxassislik:</b> {specialty}\n📅 <b>Sana:</b> {date}\n🕐 <b>Vaqt oynasi:</b> {time_window}\n\nNavbatga kirish uchun QR kodni skanerlang yoki havolaga o'ting:\n\n🔗 <b>Havola:</b> {queue_url}?token={qr_token}\n\n⚠️ <b>Muhim:</b> Belgilangan vaqtda keling. QR kod faqat qabul kuni amal qiladi.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📱 Navbatni ochish",
                                    "url": "{queue_url}?token={qr_token}",
                                },
                                {
                                    "text": "📍 Yo'l",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                            [
                                {
                                    "text": "📞 Qo'llab-quvvatlash",
                                    "callback_data": "support",
                                },
                                {
                                    "text": "🔄 Yangilash",
                                    "callback_data": "refresh_qr_{appointment_id}",
                                },
                            ],
                        ]
                    },
                },
            },
            "appointment_confirmed": {
                "ru": {
                    "text": "✅ <b>Запись подтверждена</b>\n\nВаша запись успешно подтверждена:\n\n👨‍⚕️ <b>Врач:</b> {doctor_name}\n📅 <b>Дата:</b> {appointment_date}\n🕐 <b>Время:</b> {appointment_time}\n🏥 <b>Специализация:</b> {specialty}\n🏢 <b>Кабинет:</b> {cabinet}\n\n📍 <b>Адрес:</b> {clinic_address}\n📞 <b>Телефон:</b> {clinic_phone}\n\nСпасибо за подтверждение! Ждем вас на приеме.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📱 QR код",
                                    "callback_data": "get_qr_{appointment_id}",
                                },
                                {
                                    "text": "📍 Маршрут",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                            [
                                {
                                    "text": "📅 Мои записи",
                                    "callback_data": "my_appointments",
                                },
                                {
                                    "text": "🏠 Главное меню",
                                    "callback_data": "main_menu",
                                },
                            ],
                        ]
                    },
                },
                "uz": {
                    "text": "✅ <b>Qabul tasdiqlandi</b>\n\nQabullingiz muvaffaqiyatli tasdiqlandi:\n\n👨‍⚕️ <b>Shifokor:</b> {doctor_name}\n📅 <b>Sana:</b> {appointment_date}\n🕐 <b>Vaqt:</b> {appointment_time}\n🏥 <b>Mutaxassislik:</b> {specialty}\n🏢 <b>Xona:</b> {cabinet}\n\n📍 <b>Manzil:</b> {clinic_address}\n📞 <b>Telefon:</b> {clinic_phone}\n\nTasdiqlash uchun rahmat! Qabulda kutamiz.",
                    "keyboard": {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📱 QR kod",
                                    "callback_data": "get_qr_{appointment_id}",
                                },
                                {
                                    "text": "📍 Yo'l",
                                    "url": "https://maps.google.com/?q={clinic_address}",
                                },
                            ],
                            [
                                {
                                    "text": "📅 Mening qabullarim",
                                    "callback_data": "my_appointments",
                                },
                                {
                                    "text": "🏠 Asosiy menyu",
                                    "callback_data": "main_menu",
                                },
                            ],
                        ]
                    },
                },
            },
        }

    def get_template(
        self, template_key: str, language: str = "ru", data: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Получить шаблон сообщения с подстановкой данных"""
        try:
            template = self.templates.get(template_key, {}).get(language, {})

            if not template:
                # Fallback на русский язык
                template = self.templates.get(template_key, {}).get("ru", {})

            if not template:
                return {"text": "Шаблон не найден", "keyboard": None}

            # Копируем шаблон для модификации
            result = template.copy()

            if data:
                # Подставляем данные в текст
                if "text" in result:
                    result["text"] = result["text"].format(**data)

                # Подставляем данные в клавиатуру
                if "keyboard" in result and result["keyboard"]:
                    result["keyboard"] = self._format_keyboard(result["keyboard"], data)

            return result

        except Exception as e:
            return {
                "text": f"Ошибка форматирования шаблона: {str(e)}",
                "keyboard": None,
            }

    def _format_keyboard(
        self, keyboard: dict[str, Any], data: dict[str, Any]
    ) -> dict[str, Any]:
        """Форматирование клавиатуры с подстановкой данных"""
        try:
            if "inline_keyboard" in keyboard:
                formatted_buttons = []
                for row in keyboard["inline_keyboard"]:
                    formatted_row = []
                    for button in row:
                        formatted_button = button.copy()
                        if "text" in formatted_button:
                            formatted_button["text"] = formatted_button["text"].format(
                                **data
                            )
                        if "callback_data" in formatted_button:
                            formatted_button["callback_data"] = formatted_button[
                                "callback_data"
                            ].format(**data)
                        if "url" in formatted_button:
                            formatted_button["url"] = formatted_button["url"].format(
                                **data
                            )
                        formatted_row.append(formatted_button)
                    formatted_buttons.append(formatted_row)

                return {"inline_keyboard": formatted_buttons}

            return keyboard

        except Exception:
            return keyboard

    def get_supported_languages(self) -> list[str]:
        """Получить список поддерживаемых языков"""
        return ["ru", "uz", "en"]

    def get_template_keys(self) -> list[str]:
        """Получить список доступных шаблонов"""
        return list(self.templates.keys())

    def add_custom_template(
        self, template_key: str, language: str, template_data: dict[str, Any]
    ):
        """Добавить пользовательский шаблон"""
        if template_key not in self.templates:
            self.templates[template_key] = {}

        self.templates[template_key][language] = template_data

    def get_abnormalities_text(
        self, has_abnormalities: bool, language: str = "ru"
    ) -> str:
        """Получить текст о нарушениях в анализах"""
        if language == "uz":
            return (
                "⚠️ <b>E'tibor:</b> Natijalarda og'ishlar aniqlandi. Shifokor bilan maslahatlashingiz tavsiya etiladi."
                if has_abnormalities
                else "✅ Barcha ko'rsatkichlar normal doiralarda."
            )
        else:
            return (
                "⚠️ <b>Внимание:</b> В результатах выявлены отклонения. Рекомендуется консультация с врачом."
                if has_abnormalities
                else "✅ Все показатели в пределах нормы."
            )


# Глобальный экземпляр сервиса
telegram_templates_service = TelegramTemplatesService()


def get_telegram_templates_service() -> TelegramTemplatesService:
    """Получить экземпляр сервиса шаблонов"""
    return telegram_templates_service
