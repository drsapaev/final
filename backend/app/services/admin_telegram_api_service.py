"""
API endpoints для управления Telegram в админ панели
"""

from datetime import datetime, timedelta
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic
from app.models.user import User

router = APIRouter()

# ===================== НАСТРОЙКИ TELEGRAM =====================


@router.get("/telegram/settings")
def get_telegram_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки Telegram"""
    try:
        telegram_settings = crud_clinic.get_settings_by_category(db, "telegram")

        result = {
            "bot_token": "",
            "webhook_url": "",
            "admin_chat_ids": [],
            "notifications_enabled": True,
            "appointment_reminders": True,
            "lab_results_notifications": True,
            "payment_notifications": True,
            "default_language": "ru",
            "supported_languages": ["ru", "uz", "en"],
        }

        # Применяем сохраненные настройки
        for setting in telegram_settings:
            if setting.key in result:
                result[setting.key] = setting.value

        # Скрываем токен бота в ответе
        if result["bot_token"]:
            result["bot_token_masked"] = result["bot_token"][:10] + "***скрыт***"
            result["bot_token"] = "***скрыт***"

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек Telegram: {str(e)}",
        )


@router.put("/telegram/settings")
def update_telegram_settings(
    settings: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки Telegram"""
    try:
        # Обновляем настройки в категории "telegram"
        updated_settings = crud_clinic.update_settings_batch(
            db, "telegram", settings, current_user.id
        )

        return {
            "success": True,
            "message": "Настройки Telegram обновлены",
            "updated_count": len(updated_settings),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек Telegram: {str(e)}",
        )


@router.post("/telegram/test-bot")
def test_telegram_bot(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Тестировать подключение к Telegram боту"""
    try:
        # Получаем токен бота
        bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
        if not bot_token_setting or not bot_token_setting.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        bot_token = bot_token_setting.value

        # Тестируем подключение к API Telegram
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10
        )

        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get("ok"):
                bot_data = bot_info["result"]

                # Сохраняем информацию о боте
                crud_clinic.update_settings_batch(
                    db,
                    "telegram",
                    {
                        "bot_username": bot_data.get("username"),
                        "bot_name": bot_data.get("first_name"),
                    },
                    current_user.id,
                )

                return {
                    "success": True,
                    "message": "Подключение к боту успешно",
                    "bot_info": {
                        "id": bot_data.get("id"),
                        "username": bot_data.get("username"),
                        "first_name": bot_data.get("first_name"),
                        "can_join_groups": bot_data.get("can_join_groups"),
                        "can_read_all_group_messages": bot_data.get(
                            "can_read_all_group_messages"
                        ),
                    },
                }
            else:
                raise Exception(f"Ошибка API Telegram: {bot_info.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка подключения к Telegram API: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования бота: {str(e)}",
        )


@router.post("/telegram/set-webhook")
def set_telegram_webhook(
    webhook_url: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Установить webhook для Telegram бота"""
    try:
        # Получаем токен бота
        bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
        if not bot_token_setting or not bot_token_setting.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        bot_token = bot_token_setting.value

        # Устанавливаем webhook
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                # Сохраняем URL webhook
                crud_clinic.update_setting(
                    db, "webhook_url", {"value": webhook_url}, current_user.id
                )

                return {
                    "success": True,
                    "message": "Webhook установлен успешно",
                    "webhook_url": webhook_url,
                }
            else:
                raise Exception(
                    f"Ошибка установки webhook: {result.get('description')}"
                )
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка установки webhook: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка установки webhook: {str(e)}",
        )


@router.get("/telegram/webhook-info")
def get_telegram_webhook_info(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить информацию о webhook"""
    try:
        # Получаем токен бота
        bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
        if not bot_token_setting or not bot_token_setting.value:
            return {"webhook_set": False, "message": "Токен бота не настроен"}

        bot_token = bot_token_setting.value

        # Получаем информацию о webhook
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                webhook_info = result["result"]
                return {
                    "webhook_set": bool(webhook_info.get("url")),
                    "webhook_info": webhook_info,
                }
            else:
                raise Exception(f"Ошибка API: {result.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return {"webhook_set": False, "error": f"Ошибка подключения: {str(e)}"}
    except Exception as e:
        return {"webhook_set": False, "error": str(e)}


# ===================== ШАБЛОНЫ СООБЩЕНИЙ =====================


@router.get("/telegram/templates")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения шаблонов: {str(e)}",
        )


@router.post("/telegram/send-test-message")
def send_test_message(
    chat_id: int,
    message: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправить тестовое сообщение"""
    try:
        # Получаем токен бота
        bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
        if not bot_token_setting or not bot_token_setting.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        bot_token = bot_token_setting.value

        # Отправляем сообщение
        response = requests.post(
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка отправки сообщения: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки тестового сообщения: {str(e)}",
        )


# ===================== СТАТИСТИКА TELEGRAM =====================


@router.get("/telegram/stats")
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
            "period_start": datetime.utcnow() - timedelta(days=days_back),
            "period_end": datetime.utcnow(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики Telegram: {str(e)}",
        )


# ===================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====================


@router.get("/telegram/users")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения пользователей Telegram: {str(e)}",
        )


# ===================== ШИРОКОВЕЩАТЕЛЬНЫЕ СООБЩЕНИЯ =====================


@router.post("/telegram/broadcast")
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
        bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
        if not bot_token_setting or not bot_token_setting.value:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки сообщения: {str(e)}",
        )
