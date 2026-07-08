from __future__ import annotations

from app.api.v1.endpoints.admin_telegram._helpers import *  # noqa

from typing import Any
@router.get("/telegram/templates", response_model=dict[str, Any])
def get_telegram_templates(
    language: str = "ru",
    template_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить шаблоны сообщений"""
    try:
        # Здесь будет логика получения шаблонов из БД
        # Пока возвращаем базовые шаблоны

        base_templates = {
            "appointment_reminder": {
                "ru": {
                    "subject": "Напоминание о приеме",
                    "message_text": "Здравствуйте, {{patient_name}}!\n\nНапоминаем о приеме {{appointment_date}} в {{appointment_time}} у врача {{doctor_name}} ({{specialty}}).\n\nАдрес: {{clinic_address}}\nКабинет: {{cabinet}}\n\nПодтвердите или выберите действие:",
                    "buttons": [
                        {
                            "text": "✅ Подтвердить",
                            "callback_data": "confirm_{{appointment_id}}",
                        },
                        {
                            "text": "🔁 Перенести",
                            "callback_data": "reschedule_{{appointment_id}}",
                        },
                        {
                            "text": "❌ Отменить",
                            "callback_data": "cancel_{{appointment_id}}",
                        },
                    ],
                },
                "uz": {
                    "subject": "Qabul haqida eslatma",
                    "message_text": "Assalomu alaykum, {{patient_name}}!\n\n{{appointment_date}} kuni soat {{appointment_time}}da {{doctor_name}} shifokorining qabuliga eslatma ({{specialty}}).\n\nManzil: {{clinic_address}}\nXona: {{cabinet}}\n\nTasdiqlang yoki amalni tanlang:",
                    "buttons": [
                        {
                            "text": "✅ Tasdiqlash",
                            "callback_data": "confirm_{{appointment_id}}",
                        },
                        {
                            "text": "🔁 Ko'chirish",
                            "callback_data": "reschedule_{{appointment_id}}",
                        },
                        {
                            "text": "❌ Bekor qilish",
                            "callback_data": "cancel_{{appointment_id}}",
                        },
                    ],
                },
            },
            "lab_results_ready": {
                "ru": {
                    "subject": "Результаты анализов готовы",
                    "message_text": "Здравствуйте, {{patient_name}}!\n\nГотовы результаты анализов:\n{{lab_tests}}\n\nВы можете получить их в клинике или скачать по ссылке ниже.",
                    "buttons": [
                        {"text": "📄 Скачать результаты", "url": "{{download_link}}"}
                    ],
                },
                "uz": {
                    "subject": "Tahlil natijalari tayyor",
                    "message_text": "Assalomu alaykum, {{patient_name}}!\n\nTahlil natijalari tayyor:\n{{lab_tests}}\n\nUlarni klinikadan olishingiz yoki quyidagi havoladan yuklab olishingiz mumkin.",
                    "buttons": [
                        {
                            "text": "📄 Natijalarni yuklab olish",
                            "url": "{{download_link}}",
                        }
                    ],
                },
            },
            "payment_confirmation": {
                "ru": {
                    "subject": "Платеж подтвержден",
                    "message_text": "Платеж на сумму {{amount}} {{currency}} успешно обработан.\n\nСпасибо за оплату!\n\nЧек можете скачать по ссылке ниже.",
                    "buttons": [{"text": "🧾 Скачать чек", "url": "{{receipt_link}}"}],
                }
            },
        }

        if template_type:
            return base_templates.get(template_type, {}).get(language, {})

        # Возвращаем все шаблоны для языка
        result = {}
        for template_key, template_data in base_templates.items():
            if language in template_data:
                result[template_key] = template_data[language]

        return result

    except Exception as e:
        raise_admin_telegram_error(
            "templates",
            "Ошибка получения шаблонов",
            e,
        )


@router.post("/telegram/send-test-message", response_model=dict[str, Any])
def send_test_message(
    chat_id: int,
    message: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправить тестовое сообщение"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        # Отправляем сообщение
        response = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"🧪 Тестовое сообщение от Programma Clinic\n\n{message}\n\n⚙️ Отправлено из админ панели",
                "parse_mode": "HTML",
            },
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return {
                    "success": True,
                    "message": "Тестовое сообщение отправлено",
                    "message_id": result["result"]["message_id"],
                }
            else:
                raise Exception(f"Ошибка отправки: {result.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "send-test-message-request",
            "Ошибка отправки сообщения",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "send-test-message",
            "Ошибка отправки тестового сообщения",
            e,
        )


# ===================== СТАТИСТИКА TELEGRAM =====================


@router.get("/telegram/stats", response_model=dict[str, Any])
def get_telegram_stats(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin", "admin"])),
):
    """Получить статистику Telegram"""
    try:
        # Пока возвращаем заглушку, в будущем будет реальная статистика
        return {
            "total_users": 0,
            "active_users": 0,
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "by_message_type": {},
            "period_start": datetime.now(UTC) - timedelta(days=days_back),
            "period_end": datetime.now(UTC),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "stats",
            "Ошибка получения статистики Telegram",
            e,
        )


# ===================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====================


@router.get("/telegram/users", response_model=dict[str, Any])
def get_telegram_users(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin", "admin"])),
):
    """Получить список пользователей Telegram"""
    try:
        # Пока возвращаем заглушку
        return []
    except Exception as e:
        raise_admin_telegram_error(
            "users",
            "Ошибка получения пользователей Telegram",
            e,
        )


# ===================== ШИРОКОВЕЩАТЕЛЬНЫЕ СООБЩЕНИЯ =====================


@router.post("/telegram/broadcast", response_model=dict[str, Any])
def send_broadcast_message(
    message: str,
    target_groups: list[str],  # ["patients", "doctors", "admins"]
    language: str = "ru",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправить широковещательное сообщение"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        # Здесь будет логика отправки широковещательных сообщений
        # Пока возвращаем заглушку

        return {
            "success": True,
            "message": "Широковещательное сообщение поставлено в очередь",
            "target_groups": target_groups,
            "estimated_recipients": 0,  # Будет подсчитано из БД
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "broadcast",
            "Ошибка отправки сообщения",
            e,
        )
