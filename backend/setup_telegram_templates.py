"""
Создание шаблонов сообщений Telegram
Основа: passport.md стр. 2064-2570
"""
import os


def _require_setup_telegram_templates_confirmation() -> None:
    if os.getenv("CONFIRM_SETUP_TELEGRAM_TEMPLATES") != "1":
        raise SystemExit(
            "Set CONFIRM_SETUP_TELEGRAM_TEMPLATES=1 before creating Telegram config/templates."
        )


def _require_postgres_database_url() -> None:
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before creating Telegram templates.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError(
            "setup_telegram_templates.py requires PostgreSQL; SQLite is not allowed."
        )


_require_setup_telegram_templates_confirmation()
_require_postgres_database_url()

from app.db.session import SessionLocal
from app.models.telegram_config import TelegramConfig, TelegramTemplate
from app.crud import telegram_config as crud_telegram

def create_telegram_config():
    """Создать базовую конфигурацию Telegram"""
    print('📱 Создание конфигурации Telegram бота...')

    db = SessionLocal()
    try:
        # Проверяем есть ли уже конфигурация
        existing = crud_telegram.get_telegram_config(db)
        
        if not existing:
            config_data = {
                "bot_token": None,  # Будет настроен в админ панели
                "webhook_url": None,
                "webhook_secret": None,
                "bot_username": "clinic_bot",
                "bot_name": "Медицинская клиника - Бот",
                "admin_chat_ids": [],
                "notifications_enabled": True,
                "appointment_reminders": True,
                "lab_results_notifications": True,
                "payment_notifications": True,
                "default_language": "ru",
                "supported_languages": ["ru", "uz", "en"],
                "active": False  # Будет активирован после настройки токена
            }
            
            config = TelegramConfig(**config_data)
            db.add(config)
            db.commit()
            print("✅ Создана базовая конфигурация Telegram")
        else:
            print("✅ Конфигурация Telegram уже существует")

    finally:
        db.close()

def create_message_templates():
    """Создать шаблоны сообщений"""
    print('\n📝 Создание шаблонов сообщений...')

    db = SessionLocal()
    try:
        templates = [
            # Приветственное сообщение
            {
                "template_key": "welcome_message",
                "template_type": "notification",
                "language": "ru",
                "subject": "Добро пожаловать!",
                "message_text": """🏥 <b>Добро пожаловать в {{ clinic_name }}!</b>

Привет, {{ user_name }}! 👋

Я помогу вам:
📅 Записаться на прием
📱 Получить QR код для очереди
🔔 Получать уведомления
📋 Просматривать результаты анализов

Используйте кнопки ниже или команды:
/queue - Онлайн очередь
/appointments - Мои записи
/results - Результаты анализов""",
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "inline_buttons": [
                    {"text": "📅 Записаться", "callback_data": "book_appointment"},
                    {"text": "📱 QR очередь", "callback_data": "get_qr"}
                ],
                "active": True
            },
            
            # Напоминание о записи
            {
                "template_key": "appointment_reminder",
                "template_type": "reminder",
                "language": "ru",
                "subject": "Напоминание о записи",
                "message_text": """⏰ <b>Напоминание о записи</b>

👋 {{ patient_name }}, напоминаем о вашей записи:

👨‍⚕️ <b>Врач:</b> {{ doctor_name }}
🏥 <b>Специальность:</b> {{ specialty }}
📅 <b>Дата:</b> {{ appointment_date }}
🕐 <b>Время:</b> {{ appointment_time }}
🚪 <b>Кабинет:</b> {{ cabinet }}

📍 <b>Адрес:</b> {{ clinic_address }}
📞 <b>Телефон:</b> {{ clinic_phone }}

<b>Что взять с собой:</b>
• Документ удостоверяющий личность
• Предыдущие результаты обследований (если есть)

⚠️ <b>Просьба прийти за 15 минут до приема</b>""",
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "inline_buttons": [
                    {"text": "✅ Подтвердить", "callback_data": "confirm_appointment"},
                    {"text": "❌ Отменить", "callback_data": "cancel_appointment"}
                ],
                "active": True
            },
            
            # Уведомление о готовности результатов
            {
                "template_key": "lab_results_ready",
                "template_type": "notification",
                "language": "ru",
                "subject": "Результаты анализов готовы",
                "message_text": """🧪 <b>Результаты анализов готовы!</b>

{{ patient_name }}, ваши анализы готовы:

📋 <b>Тип исследования:</b> {{ test_type }}
📅 <b>Дата сдачи:</b> {{ collection_date }}
✅ <b>Дата готовности:</b> {{ ready_date }}

{% if has_abnormalities %}
⚠️ <b>Обнаружены отклонения от нормы</b>
Рекомендуется консультация врача
{% else %}
✅ <b>Все показатели в норме</b>
{% endif %}

Результаты можно получить:
• В электронном виде через бота
• В регистратуре клиники""",
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "inline_buttons": [
                    {"text": "📄 Посмотреть результаты", "callback_data": "view_results"},
                    {"text": "📅 Записаться к врачу", "callback_data": "book_consultation"}
                ],
                "active": True
            },
            
            # Подтверждение оплаты
            {
                "template_key": "payment_confirmation",
                "template_type": "notification",
                "language": "ru",
                "subject": "Оплата подтверждена",
                "message_text": """💳 <b>Оплата успешно проведена</b>

{{ patient_name }}, ваш платеж подтвержден:

🧾 <b>Номер чека:</b> {{ payment_number }}
💰 <b>Сумма:</b> {{ amount }} {{ currency }}
💳 <b>Способ оплаты:</b> {{ payment_method }}
📅 <b>Дата:</b> {{ payment_date }}

<b>Оплаченные услуги:</b>
{% for service in services %}
• {{ service.name }} - {{ service.price }} {{ service.currency }}
{% endfor %}

👨‍⚕️ <b>Врач:</b> {{ doctor_name }}
📅 <b>Дата приема:</b> {{ appointment_date }}

Чек отправлен на email: {{ patient_email }}""",
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "inline_buttons": [
                    {"text": "📄 Скачать чек", "callback_data": "download_receipt"}
                ],
                "active": True
            },
            
            # QR код для очереди
            {
                "template_key": "qr_code_message",
                "template_type": "notification",
                "language": "ru",
                "subject": "QR код для очереди",
                "message_text": """📱 <b>Ваш QR код для онлайн-очереди</b>

🏥 <b>Врач:</b> {{ doctor_name }}
🩺 <b>Специальность:</b> {{ specialty }}
📅 <b>Дата:</b> {{ date }}
⏰ <b>Время записи:</b> {{ time_window }}

<b>QR код:</b>
<code>{{ qr_token }}</code>

<b>Инструкция:</b>
1. Зайдите на сайт в указанное время
2. Отсканируйте QR код или введите код вручную
3. Получите номер в очереди
4. Ожидайте вызова

⚠️ <b>Код действителен только в день приема!</b>""",
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "inline_buttons": [
                    {"text": "🌐 Открыть очередь", "url": "{{ queue_url }}"}
                ],
                "active": True
            }
        ]

        # Создаем шаблоны
        created_count = 0
        for template_data in templates:
            existing = db.query(TelegramTemplate).filter(
                TelegramTemplate.template_key == template_data["template_key"],
                TelegramTemplate.language == template_data["language"]
            ).first()
            
            if not existing:
                template = TelegramTemplate(**template_data)
                db.add(template)
                created_count += 1

        if created_count > 0:
            db.commit()
            print(f"✅ Создано {created_count} новых шаблонов")
        else:
            print("✅ Все шаблоны уже существуют")

        # Получаем все шаблоны
        all_templates = crud_telegram.get_telegram_templates(db)
        print(f"✅ Всего шаблонов Telegram: {len(all_templates)}")
        
        for template in all_templates:
            print(f"   • {template.template_key} ({template.language})")

    finally:
        db.close()

def main():
    """Основная функция настройки"""
    print("📱 НАСТРОЙКА TELEGRAM БОТА")
    print("=" * 50)
    
    try:
        # 1. Создаем конфигурацию
        create_telegram_config()
        
        # 2. Создаем шаблоны
        create_message_templates()
        
        print("\n" + "=" * 50)
        print("🎉 TELEGRAM БОТ НАСТРОЕН!")
        print("\n✅ Созданные компоненты:")
        print("   • Базовая конфигурация бота")
        print("   • 5 шаблонов сообщений")
        print("   • Поддержка уведомлений")
        print("   • Интеграция с онлайн-очередью")
        
        print("\n🔧 Следующие шаги:")
        print("   1. Добавить токен бота в админ панели")
        print("   2. Активировать бота")
        print("   3. Настроить webhook (опционально)")
        print("   4. Протестировать команды")
        
    except Exception as e:
        print(f"\n❌ Ошибка настройки Telegram: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
