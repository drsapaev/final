"""
API endpoints для управления Telegram в админ панели
"""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, NoReturn, Optional

import requests
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic, telegram_config as crud_telegram
from app.models.user import User
from app.services.telegram_bot import (
    PATIENT_BOT_COMMANDS_RU,
    PATIENT_BOT_COMMANDS_UZ,
    get_telegram_bot_service,
)

router = APIRouter()
logger = logging.getLogger(__name__)

STAFF_BOT_SUPPORTED_ROLES = [
    "registrar",
    "doctor",
    "cashier",
    "lab",
    "admin",
    "owner",
]

STAFF_BOT_READINESS = [
    {
        "key": "role_based_staff_linking",
        "label": "Ролевая привязка сотрудников",
        "ready": False,
    },
    {
        "key": "server_side_authorization",
        "label": "Проверка ролей на backend",
        "ready": False,
    },
    {
        "key": "audit_logging",
        "label": "Аудит действий сотрудников",
        "ready": False,
    },
    {
        "key": "state_change_confirmations",
        "label": "Подтверждения для операций",
        "ready": False,
    },
]

STAFF_BOT_READ_ONLY_MENU_CONTRACT = [
    {
        "role": "registrar",
        "label": "Регистратор",
        "items": [
            {"key": "queue_overview", "label": "Очередь", "intent": "read_only"},
            {"key": "next_patient", "label": "Следующий пациент", "intent": "read_only"},
            {"key": "payment_status", "label": "Статус оплаты", "intent": "read_only"},
        ],
    },
    {
        "role": "doctor",
        "label": "Врач",
        "items": [
            {"key": "today_schedule", "label": "Расписание на сегодня", "intent": "read_only"},
            {"key": "next_patient", "label": "Следующий пациент", "intent": "read_only"},
            {"key": "emr_reminders", "label": "Напоминания ЭМК", "intent": "read_only"},
        ],
    },
    {
        "role": "cashier",
        "label": "Кассир",
        "items": [
            {"key": "unpaid_invoices", "label": "Неоплаченные счета", "intent": "read_only"},
            {"key": "paid_invoices", "label": "Оплаченные счета", "intent": "read_only"},
            {"key": "reconciliation_alerts", "label": "Сверка оплат", "intent": "read_only"},
        ],
    },
    {
        "role": "lab",
        "label": "Лаборатория",
        "items": [
            {"key": "ready_reports", "label": "Готовые результаты", "intent": "read_only"},
            {"key": "pending_reports", "label": "Ожидающие результаты", "intent": "read_only"},
            {"key": "delivery_status", "label": "Статус доставки", "intent": "read_only"},
        ],
    },
    {
        "role": "admin",
        "label": "Администратор",
        "items": [
            {"key": "daily_summary", "label": "Дневная сводка", "intent": "read_only"},
            {"key": "integration_errors", "label": "Ошибки интеграций", "intent": "read_only"},
            {"key": "staff_readiness", "label": "Готовность staff bot", "intent": "read_only"},
        ],
    },
    {
        "role": "owner",
        "label": "Владелец",
        "items": [
            {"key": "daily_summary", "label": "Дневная сводка", "intent": "read_only"},
            {"key": "revenue_summary", "label": "Сводка выручки", "intent": "read_only"},
            {"key": "integration_errors", "label": "Ошибки интеграций", "intent": "read_only"},
        ],
    },
]

STAFF_BOT_GUARDRAILS = [
    "server_side_authorization",
    "audit_logging",
    "explicit_confirmation_for_state_changes",
    "no_queue_fairness_mutation_without_domain_service",
]

STAFF_BOT_LINKING_CONTRACT = {
    "contract_version": "staff-linking-v1",
    "enabled": False,
    "required_before_enablement": True,
    "identity_rule": "telegram_user_id_is_not_application_identity",
    "accepted_methods": [
        {
            "key": "admin_verified_staff_link",
            "label": "Администратор подтверждает сотрудника",
            "status": "planned",
        },
        {
            "key": "one_time_signed_staff_token",
            "label": "Одноразовый подписанный токен",
            "status": "planned",
        },
    ],
    "required_server_checks": [
        "active_application_user",
        "allowed_staff_role",
        "telegram_user_not_linked_to_another_staff_user",
        "token_not_expired",
        "token_not_reused",
    ],
    "enablement_gate": [
        "role_based_staff_linking",
        "server_side_authorization",
        "audit_logging",
        "state_change_confirmations",
    ],
    "state_changing_actions_allowed_after_link": False,
}


def _build_staff_bot_status(webhook_set: bool) -> Dict[str, Any]:
    return {
        "version": "planning",
        "contract_version": "staff-menu-read-only-v1",
        "enabled": False,
        "contract_published": True,
        "status": "requires_role_linking_audit_and_confirmations",
        "transport": "polling" if not webhook_set else "webhook",
        "supported_languages": [
            {"code": "ru", "label": "Русский"},
        ],
        "supported_roles": STAFF_BOT_SUPPORTED_ROLES,
        "role_linking": {
            "enabled": False,
            "required_before_enablement": True,
            "accepted_methods": [
                "admin_verified_staff_link",
                "one_time_signed_staff_token",
            ],
        },
        "linking_contract": STAFF_BOT_LINKING_CONTRACT,
        "authorization": {
            "source": "application_rbac",
            "server_side_required": True,
            "ready": False,
        },
        "audit": {
            "required": True,
            "ready": False,
        },
        "state_changing_actions_enabled": False,
        "readiness": STAFF_BOT_READINESS,
        "read_only_menu_contract": STAFF_BOT_READ_ONLY_MENU_CONTRACT,
        "guardrails": STAFF_BOT_GUARDRAILS,
        "next_slice": "role_linking_and_read_only_staff_menu_contract",
    }


def raise_admin_telegram_error(
    action: str,
    public_detail: str,
    exc: Exception,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> NoReturn:
    logger.warning(
        "Admin Telegram endpoint failed action=%s status_code=%s error_type=%s",
        action,
        status_code,
        type(exc).__name__,
    )
    raise HTTPException(status_code=status_code, detail=public_detail)


def webhook_info_error_response(
    action: str, public_error: str, exc: Exception
) -> Dict[str, Any]:
    logger.warning(
        "Admin Telegram webhook info failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    return {"webhook_set": False, "error": public_error}


class TelegramWebhookRequest(BaseModel):
    webhook_url: Optional[str] = None


def _get_configured_bot_token(db: Session) -> str | None:
    config = crud_telegram.get_telegram_config(db)
    if config and config.bot_token:
        return config.bot_token

    bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
    return getattr(bot_token_setting, "value", None) if bot_token_setting else None


def _get_configured_bot_username(db: Session) -> str | None:
    config = crud_telegram.get_telegram_config(db)
    if config and config.bot_username:
        return config.bot_username

    bot_username_setting = crud_clinic.get_setting_by_key(db, "bot_username")
    return (
        getattr(bot_username_setting, "value", None) if bot_username_setting else None
    )


def _fetch_telegram_webhook_info(bot_token: str) -> Dict[str, Any]:
    response = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description") or "Telegram API error")
    return result["result"]

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
            "supported_languages": ["ru", "uz-Latn"],
        }

        # Применяем сохраненные настройки
        for setting in telegram_settings:
            if setting.key in result:
                result[setting.key] = setting.value

        # Скрываем токен бота в ответе
        if result["bot_token"]:
            result["bot_token_masked"] = "***скрыт***"
            result["bot_token_length"] = len(result["bot_token"])
            result["bot_token"] = "***скрыт***"

        return result
    except Exception as e:
        raise_admin_telegram_error(
            "settings-read",
            "Ошибка получения настроек Telegram",
            e,
        )


@router.put("/telegram/settings")
def update_telegram_settings(
    settings: Dict[str, Any],
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
        raise_admin_telegram_error(
            "settings-update",
            "Ошибка обновления настроек Telegram",
            e,
        )


@router.post("/telegram/test-bot")
def test_telegram_bot(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Тестировать подключение к Telegram боту"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

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
                config_payload = {
                    "bot_token": bot_token,
                    "bot_username": bot_data.get("username"),
                    "bot_name": bot_data.get("first_name"),
                    "active": True,
                }
                if crud_telegram.get_telegram_config(db):
                    crud_telegram.update_telegram_config(db, config_payload)
                else:
                    crud_telegram.create_telegram_config(db, config_payload)

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
        raise_admin_telegram_error(
            "test-bot-request",
            "Ошибка подключения к Telegram API",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "test-bot",
            "Ошибка тестирования бота",
            e,
        )


@router.post("/telegram/register-patient-commands")
async def register_patient_bot_commands(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Register patient bot commands in Telegram via the configured bot token."""
    try:
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bot token is not configured",
            )

        bot_service = await get_telegram_bot_service()
        bot_service.bot_token = bot_token
        ok, error = await bot_service.set_patient_bot_commands()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Telegram patient bot commands were not registered",
                    "error": error,
                },
            )

        return {
            "success": True,
            "message": "Telegram patient bot commands registered",
            "registered_languages": ["ru", "uz"],
            "commands": {
                "ru": PATIENT_BOT_COMMANDS_RU,
                "uz": PATIENT_BOT_COMMANDS_UZ,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "register-patient-commands",
            "Telegram patient bot command registration failed",
            e,
        )


@router.post("/telegram/set-webhook")
def set_telegram_webhook(
    payload: Optional[TelegramWebhookRequest] = Body(default=None),
    webhook_url: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Установить webhook для Telegram бота"""
    try:
        selected_webhook_url = (payload.webhook_url if payload else None) or webhook_url
        if not selected_webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="webhook_url is required",
            )

        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        secret_token = secrets.token_urlsafe(32)

        # Устанавливаем webhook
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": selected_webhook_url, "secret_token": secret_token},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                # Сохраняем URL webhook
                crud_clinic.update_setting(
                    db, "webhook_url", {"value": selected_webhook_url}, current_user.id
                )
                config_payload = {
                    "bot_token": bot_token,
                    "bot_username": _get_configured_bot_username(db),
                    "webhook_url": selected_webhook_url,
                    "webhook_secret": secret_token,
                    "active": True,
                }
                if crud_telegram.get_telegram_config(db):
                    crud_telegram.update_telegram_config(db, config_payload)
                else:
                    crud_telegram.create_telegram_config(db, config_payload)

                return {
                    "success": True,
                    "message": "Webhook установлен успешно",
                    "webhook_url": selected_webhook_url,
                    "webhook_secret_configured": True,
                }
            else:
                raise Exception(
                    f"Ошибка установки webhook: {result.get('description')}"
                )
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "set-webhook-request",
            "Ошибка установки webhook",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "set-webhook",
            "Ошибка установки webhook",
            e,
        )


@router.get("/telegram/webhook-info")
def get_telegram_webhook_info(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить информацию о webhook"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            return {"webhook_set": False, "message": "Токен бота не настроен"}

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
        return webhook_info_error_response(
            "webhook-info-request",
            "Ошибка подключения",
            e,
        )
    except Exception as e:
        return webhook_info_error_response(
            "webhook-info",
            "Ошибка получения информации о webhook",
            e,
        )


# ===================== ШАБЛОНЫ СООБЩЕНИЙ =====================


@router.get("/telegram/integration-status")
def get_telegram_integration_status(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Return app-facing Telegram integration status without exposing secrets."""
    try:
        config = crud_telegram.get_telegram_config(db)
        bot_token = _get_configured_bot_token(db)
        bot_username = _get_configured_bot_username(db)
        telegram_users = crud_telegram.get_telegram_users(
            db, active_only=False, limit=100000
        )
        linked_users = [user for user in telegram_users if user.patient_id]

        webhook_info = None
        webhook_error = None
        if bot_token:
            try:
                webhook_info = _fetch_telegram_webhook_info(bot_token)
            except requests.RequestException as exc:
                webhook_error = "Telegram API unavailable"
                logger.warning(
                    "Admin Telegram integration status request failed error_type=%s",
                    type(exc).__name__,
                )
            except Exception as exc:
                webhook_error = "Telegram webhook status unavailable"
                logger.warning(
                    "Admin Telegram integration status failed error_type=%s",
                    type(exc).__name__,
                )

        webhook_set = bool(webhook_info and webhook_info.get("url"))
        webhook_url = (
            webhook_info.get("url")
            if webhook_info
            else getattr(config, "webhook_url", None)
        )

        return {
            "configured": bool(bot_token),
            "active": bool(getattr(config, "active", False) or bot_token),
            "bot_username": bot_username,
            "mode": "webhook" if webhook_set else "polling",
            "polling_ready": bool(bot_token and not webhook_set),
            "polling_command": "python -m app.scripts.telegram_polling_worker",
            "polling_task_name": "KosmedTelegramPollingWorker",
            "webhook_set": webhook_set,
            "webhook_url": webhook_url,
            "webhook_error": webhook_error,
            "pending_update_count": (
                webhook_info.get("pending_update_count") if webhook_info else None
            ),
            "qr_linking_enabled": bool(bot_username),
            "contact_linking_enabled": bool(bot_token),
            "linked_users": len(linked_users),
            "total_users": len(telegram_users),
            "supported_functions": [
                "ticket_qr_link",
                "contact_phone_link",
                "patient_queue",
                "patient_payments_debt",
                "patient_status",
                "lab_results_pdf",
            ],
            "planned_functions": [
                "staff_read_only_menu_contract",
                "staff_role_linking_contract",
                "staff_role_menus",
                "staff_action_confirmations",
                "staff_audit_logging",
                "admin_notifications",
            ],
            "patient_bot": {
                "version": "v1",
                "transport": "polling" if not webhook_set else "webhook",
                "supported_languages": [
                    {"code": "ru", "label": "Русский"},
                    {"code": "uz-Latn", "label": "O'zbekcha"},
                ],
                "default_language": "ru",
                "onboarding": "language_choice_then_contact_link",
                "commands": [
                    {"command": "/queue", "label": "Моя очередь"},
                    {"command": "/payments", "label": "Оплаты и долг"},
                    {"command": "/results", "label": "PDF-результаты"},
                    {"command": "/profile", "label": "Мой статус"},
                    {"command": "/help", "label": "Помощь"},
                ],
                "features": [
                    {
                        "key": "ticket_qr_link",
                        "label": "Привязка через QR чека",
                        "enabled": bool(bot_username),
                    },
                    {
                        "key": "contact_phone_link",
                        "label": "Привязка через номер телефона",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_queue",
                        "label": "Очередь пациента на сегодня",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_payments_debt",
                        "label": "Оплаты и долг по визиту",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "lab_results_pdf",
                        "label": "PDF-результаты лаборатории",
                        "enabled": bool(bot_token),
                    },
                ],
                "results_delivery": "telegram_pdf",
                "max_pdf_reports_per_request": 3,
            },
            "staff_bot": _build_staff_bot_status(webhook_set),
            "transition_path": (
                "Set webhook when a public HTTPS backend URL is available; "
                "stop polling before webhook is enabled."
            ),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "integration-status",
            "Ошибка получения статуса Telegram интеграции",
            e,
        )


@router.get("/telegram/templates")
def get_telegram_templates(
    language: str = "ru",
    template_type: Optional[str] = None,
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
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

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
        raise_admin_telegram_error(
            "stats",
            "Ошибка получения статистики Telegram",
            e,
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
        raise_admin_telegram_error(
            "users",
            "Ошибка получения пользователей Telegram",
            e,
        )


# ===================== ШИРОКОВЕЩАТЕЛЬНЫЕ СООБЩЕНИЯ =====================


@router.post("/telegram/broadcast")
def send_broadcast_message(
    message: str,
    target_groups: List[str],  # ["patients", "doctors", "admins"]
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
