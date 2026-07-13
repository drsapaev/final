"""
Telegram webhook helper functions, constants, and utilities.

Split from telegram_webhook.py (5647 LOC → modular).
"""
"""
Webhook endpoint для обработки входящих сообщений от Telegram
"""

import hashlib  # noqa: F401
import hmac  # noqa: F401
import html  # noqa: F401
import ipaddress  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
import secrets  # noqa: F401
import socket  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from decimal import Decimal  # noqa: F401
from typing import Any, NoReturn  # noqa: F401
from urllib.parse import urlsplit, urlunsplit  # noqa: F401

from fastapi import (  # noqa: F401
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse  # noqa: F401
from pydantic import BaseModel, ConfigDict, Field  # noqa: F401
from sqlalchemy import func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import require_roles  # noqa: F401
from app.api.v1.endpoints.admin_telegram import (  # noqa: F401
    PATIENT_BOOKING_ENTRY_ROUTE,
    PATIENT_MINI_APP_ENTRY_ROUTE,
    PATIENT_PAYMENT_ENTRY_ROUTE,
    STAFF_BOT_COMMAND_REGISTRATION_CONTRACT,
    STAFF_BOT_CONFIRMATION_CONTRACT,
    STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS,
    STAFF_BOT_READ_ONLY_MENU_CONTRACT,
    STAFF_LINK_TOKEN_PREFIX,
    STAFF_LINK_TOKEN_SEPARATOR,
    _build_staff_bot_status,
    _get_configured_bot_token,
    _get_staff_bot_token_runtime_status,
    _normalize_staff_role,
    validate_staff_link_start_token,
)
from app.core.config import settings  # noqa: F401
from app.crud import audit as crud_audit  # noqa: F401
from app.crud import telegram_config as crud_telegram  # noqa: F401
from app.crud.appointment import appointment as appointment_crud  # noqa: F401
from app.db.session import get_db  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.lab import LabReportInstance  # noqa: F401
from app.models.notification import (  # noqa: F401
    NotificationDelivery,
    NotificationEvent,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: F401
from app.models.patient import Patient  # noqa: F401
from app.models.payment import Payment, PaymentVisit  # noqa: F401
from app.models.payment_invoice import PaymentInvoice  # noqa: F401
from app.models.payment_webhook import PaymentWebhook  # noqa: F401
from app.models.telegram_config import TelegramMessage, TelegramUser  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.visit import Visit  # noqa: F401
from app.models.webhook import (  # noqa: F401
    WebhookCall,
    WebhookCallStatus,
    WebhookEvent,
)
from app.schemas import appointment as appointment_schemas  # noqa: F401
from app.schemas.patient_onboarding import (  # noqa: F401
    OnboardingAnalyticsSummaryResponse,
    OnboardingPatientSearchRequest,
    OnboardingSearchResponse,
    PatientOnboardingAuthRequest,
    PatientOnboardingStatusResponse,
    PatientOnboardingSubmitRequest,
    PatientOnboardingSubmitResponse,
    RegistrarOnboardingActionResponse,
    RegistrarOnboardingListResponse,
    RegistrarOnboardingReviewDecisionRequest,
    RegistrarPatientCreateDecisionRequest,
    RegistrarPatientLinkDecisionRequest,
)
from app.services.lab_report_pdf_service import lab_report_pdf_service  # noqa: F401
from app.services.lab_reporting_service import LabReportingService  # noqa: F401
from app.services.patient_onboarding_service import (
    PatientOnboardingService,  # noqa: F401
)
from app.services.payment_reconciliation_api_service import (  # noqa: F401
    PaymentReconciliationApiService,
)
from app.services.telegram_bot import (  # noqa: F401
    get_telegram_bot_service,
    telegram_text_corruption_reason,
)
from app.services.telegram_mini_app_init_data import (  # noqa: F401
    TelegramMiniAppInitDataError,
    TelegramMiniAppSessionScope,
    TelegramMiniAppSessionScopeError,
    build_telegram_mini_app_appointment_booking_preview,
    build_telegram_mini_app_patient_forms_preview,
    resolve_telegram_mini_app_session_scope,
    save_telegram_mini_app_patient_form_submission,
    validate_telegram_mini_app_init_data,
)
from app.services.telegram_staff_confirmation_token_service import (  # noqa: F401
    TelegramStaffConfirmationTokenService,
)
from app.services.visit_confirmation_service import (  # noqa: F401
    TELEGRAM_TICKET_QR_PREFIX,
    consume_telegram_ticket_start_token,
)
from app.utils.validators import normalize_phone_uz  # noqa: F401

logger = logging.getLogger(__name__)
router = APIRouter()

# TG-AUDIT-28 P1-4: body size limit for webhook (was unbounded — DoS risk).
# Telegram webhook payloads are typically <10KB; 256KB is generous.
MAX_TELEGRAM_WEBHOOK_BODY_BYTES = 256 * 1024


async def _read_telegram_webhook_json(request: Request) -> dict[str, Any]:
    """Read webhook body with size limit. Raises HTTPException(413) if too large."""
    body = await request.body()
    if len(body) > MAX_TELEGRAM_WEBHOOK_BODY_BYTES:
        logger.warning(
            "Telegram webhook body too large: %d bytes (max %d)",
            len(body), MAX_TELEGRAM_WEBHOOK_BODY_BYTES,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook body too large",
        )
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Telegram webhook body parse error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from exc

# TG-AUDIT-28 P1-4: body size limit for webhook (was unbounded — DoS risk).
# Telegram webhook payloads are typically <10KB; 256KB is generous.
MAX_TELEGRAM_WEBHOOK_BODY_BYTES = 256 * 1024


async def _read_telegram_webhook_json(request: Request) -> dict[str, Any]:
    """Read webhook body with size limit. Raises HTTPException(413) if too large."""
    body = await request.body()
    if len(body) > MAX_TELEGRAM_WEBHOOK_BODY_BYTES:
        logger.warning(
            "Telegram webhook body too large: %d bytes (max %d)",
            len(body), MAX_TELEGRAM_WEBHOOK_BODY_BYTES,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook body too large",
        )
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Telegram webhook body parse error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from exc
WEBHOOK_SECRET_HEADER = "x-telegram-bot-api-secret-token"
TELEGRAM_TICKET_QR_LINKED_MESSAGE = (
    "Ваш Telegram привязан к чеку клиники. "
    "Когда результаты будут готовы, откройте меню бота."
)
TELEGRAM_TICKET_QR_EXPIRED_MESSAGE = (
    "Ссылка из чека истекла или уже использована. "
    "Обратитесь в регистратуру."
)
TELEGRAM_TICKET_QR_LINK_FAILED_MESSAGE = (
    "Не удалось привязать Telegram к чеку. "
    "Попробуйте открыть QR еще раз."
)
TELEGRAM_STAFF_LINKED_MESSAGE = (
    "Telegram привязан к учетной записи сотрудника. "
    "Staff-команды включены в режиме просмотра: действия выполняются только в приложении."
)
TELEGRAM_STAFF_LINK_REJECTED_MESSAGE = (
    "Ссылка привязки сотрудника недействительна или уже использована. "
    "Запросите новую ссылку у администратора."
)
TELEGRAM_STAFF_LINK_FAILED_MESSAGE = (
    "Не удалось привязать Telegram сотрудника. "
    "Попробуйте открыть ссылку еще раз или обратитесь к администратору."
)
TELEGRAM_STAFF_LINK_REPLY_MARKUP = {"remove_keyboard": True}
TELEGRAM_STAFF_MENU_UNLINKED_MESSAGE = (
    "Staff Telegram menu is available only after staff account linking."
)
TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE = (
    "Staff Telegram menu is not available for this account role."
)
TELEGRAM_STAFF_MENU_PLACEHOLDER_MESSAGE = (
    "Read-only staff data is not connected in Telegram yet. Use the clinic app for live data."
)
TELEGRAM_STAFF_ACTION_DENIED_MESSAGE = (
    "State-changing staff actions require confirmation in the clinic app. "
    "Telegram execution is disabled."
)
TELEGRAM_STAFF_ACTION_CONFIRMATION_REQUESTED_MESSAGE = (
    "Staff action confirmation requested. No data was changed in Telegram. "
    "Open the clinic app to review and confirm the action."
)
STAFF_COMMAND_DOMAIN_ITEM_KEYS = {
    "/queue": ("queue_overview",),
    "/payments": (
        "payment_status",
        "unpaid_invoices",
        "paid_invoices",
        "reconciliation_alerts",
        "revenue_summary",
    ),
    "/reports": ("ready_reports", "integration_errors"),
    "/schedule": ("today_schedule",),
    "/summary": ("daily_summary", "revenue_summary"),
}
TELEGRAM_SHARE_CONTACT_MESSAGE = (
    "Чтобы привязать Telegram к карте пациента, нажмите кнопку "
    "\"Поделиться номером\". Номер должен совпадать с номером в регистратуре."
)
TELEGRAM_CONTACT_REJECTED_MESSAGE = (
    "Можно отправить только свой номер Telegram. "
    "Нажмите кнопку \"Поделиться номером\" в меню бота."
)
TELEGRAM_PATIENT_NOT_FOUND_MESSAGE = (
    "Пациент с этим номером не найден. Проверьте номер в регистратуре "
    "или отсканируйте QR с чека."
)
TELEGRAM_CONTACT_LINKED_MESSAGE = (
    "Telegram привязан к карте пациента. "
    "Теперь бот сможет присылать уведомления клиники."
)
TELEGRAM_NEEDS_LINK_MESSAGE = (
    "Telegram пока не привязан к пациенту. "
    "Отсканируйте QR с чека или поделитесь номером телефона через кнопку меню."
)
TELEGRAM_MAIN_MENU = {
    "keyboard": [
        [{"text": "📱 Поделиться номером", "request_contact": True}],
        [{"text": "🏥 Записаться на приём"}],
        [{"text": "🎫 Моя очередь"}, {"text": "📅 Мои визиты"}],
        [{"text": "💳 Оплаты и долг"}, {"text": "📄 Результаты"}],
        [{"text": "📲 Онлайн-сервисы"}],
        [{"text": "📋 Анкеты пациента"}, {"text": "🧾 Документы и чеки"}],
        [{"text": "🧑‍⚕️ Врачи и расписание"}, {"text": "📲 Кабинет пациента"}],
        [{"text": "👥 Режим сотрудника"}],
        [{"text": "👤 Мой статус"}, {"text": "⚙️ Настройки"}],
        [{"text": "☎️ Связаться с клиникой"}, {"text": "❓ Помощь"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
}
TELEGRAM_LANGUAGE_RU = "ru"
TELEGRAM_LANGUAGE_UZ = "uz-Latn"
TELEGRAM_LANGUAGE_MENU = {
    "keyboard": [[{"text": "🇷🇺 Русский"}, {"text": "🇺🇿 O'zbekcha"}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}
TELEGRAM_NOTIFICATION_CONSENT_MENUS = {
    TELEGRAM_LANGUAGE_RU: {
        "keyboard": [[{"text": "🔔 Разрешить уведомления"}, {"text": "🔕 Без уведомлений"}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    },
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [[{"text": "🔔 Xabarnomalarga roziman"}, {"text": "🔕 Xabarnomasiz"}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    },
}
TELEGRAM_MAIN_MENUS = {
    TELEGRAM_LANGUAGE_RU: TELEGRAM_MAIN_MENU,
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [
            [{"text": "📱 Telefon raqamni ulashish", "request_contact": True}],
            [{"text": "🏥 Qabulga yozilish"}],
            [{"text": "🎫 Mening navbatim"}, {"text": "📅 Mening tashriflarim"}],
            [{"text": "💳 To'lovlar va qarz"}, {"text": "📄 Natijalar"}],
            [{"text": "📲 Onlayn xizmatlar"}],
            [{"text": "📋 Bemor anketalari"}, {"text": "🧾 Hujjatlar va cheklar"}],
            [{"text": "🧑‍⚕️ Shifokorlar jadvali"}, {"text": "📲 Bemor kabineti"}],
            [{"text": "👥 Xodim rejimi"}],
            [{"text": "👤 Mening holatim"}, {"text": "⚙️ Sozlamalar"}],
            [{"text": "☎️ Klinikaga bog'lanish"}, {"text": "❓ Yordam"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
}
TELEGRAM_PATIENT_SERVICES_MENUS = {
    TELEGRAM_LANGUAGE_RU: {
        "keyboard": [
            [{"text": "🏥 Записаться на приём"}],
            [{"text": "🎫 Моя очередь"}, {"text": "📅 Мои визиты"}],
            [{"text": "💳 Оплаты и долг"}, {"text": "📄 Результаты"}],
            [{"text": "📋 Анкеты пациента"}, {"text": "🧾 Документы и чеки"}],
            [{"text": "🧑‍⚕️ Врачи и расписание"}, {"text": "📲 Кабинет пациента"}],
            [{"text": "👥 Режим сотрудника"}],
            [{"text": "⬅️ Главное меню"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [
            [{"text": "🏥 Qabulga yozilish"}],
            [{"text": "🎫 Mening navbatim"}, {"text": "📅 Mening tashriflarim"}],
            [{"text": "💳 To'lovlar va qarz"}, {"text": "📄 Natijalar"}],
            [{"text": "📋 Bemor anketalari"}, {"text": "🧾 Hujjatlar va cheklar"}],
            [{"text": "🧑‍⚕️ Shifokorlar jadvali"}, {"text": "📲 Bemor kabineti"}],
            [{"text": "👥 Xodim rejimi"}],
            [{"text": "⬅️ Asosiy menyu"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
}
TELEGRAM_SETTINGS_MENUS = {
    TELEGRAM_LANGUAGE_RU: {
        "keyboard": [
            [{"text": "🇷🇺 Русский"}, {"text": "🇺🇿 O'zbekcha"}],
            [{"text": "🔔 Разрешить уведомления"}, {"text": "🔕 Без уведомлений"}],
            [{"text": "🏥 Записаться на приём"}],
            [{"text": "🎫 Моя очередь"}, {"text": "📅 Мои визиты"}],
            [{"text": "☎️ Связаться с клиникой"}, {"text": "❓ Помощь"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [
            [{"text": "🇷🇺 Русский"}, {"text": "🇺🇿 O'zbekcha"}],
            [{"text": "🔔 Xabarnomalarga roziman"}, {"text": "🔕 Xabarnomasiz"}],
            [{"text": "🏥 Qabulga yozilish"}],
            [{"text": "🎫 Mening navbatim"}, {"text": "📅 Mening tashriflarim"}],
            [{"text": "☎️ Klinikaga bog'lanish"}, {"text": "❓ Yordam"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
}
TELEGRAM_SETTINGS_STATUS_LABELS = {
    TELEGRAM_LANGUAGE_RU: {
        "language": {
            TELEGRAM_LANGUAGE_RU: "Русский",
            TELEGRAM_LANGUAGE_UZ: "O'zbekcha",
        },
        "notifications_on": "включены",
        "notifications_off": "отключены",
        "template": (
            "\n\nТекущий язык: {language_label}\n"
            "Уведомления: {notification_label}"
        ),
    },
    TELEGRAM_LANGUAGE_UZ: {
        "language": {
            TELEGRAM_LANGUAGE_RU: "Rus tili",
            TELEGRAM_LANGUAGE_UZ: "O'zbekcha",
        },
        "notifications_on": "yoqilgan",
        "notifications_off": "o'chirilgan",
        "template": (
            "\n\nJoriy til: {language_label}\n"
            "Xabarnomalar: {notification_label}"
        ),
    },
}
TELEGRAM_LOCALIZED_TEXTS = {
    "language_prompt": {
        TELEGRAM_LANGUAGE_RU: "Выберите язык обслуживания.\n\nTilni tanlang.",
        TELEGRAM_LANGUAGE_UZ: "Tilni tanlang.\n\nВыберите язык обслуживания.",
    },
    "ticket_qr_linked": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_TICKET_QR_LINKED_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram klinika cheki bilan bog'landi. "
            "Natijalar tayyor bo'lganda bot menyusini oching."
        ),
    },
    "ticket_qr_expired": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_TICKET_QR_EXPIRED_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Chekdagi havola muddati tugagan yoki ishlatilgan. "
            "Registraturaga murojaat qiling."
        ),
    },
    "ticket_qr_link_failed": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_TICKET_QR_LINK_FAILED_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Telegramni chek bilan bog'lab bo'lmadi. "
            "QR kodni yana ochib ko'ring."
        ),
    },
    "share_contact": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_SHARE_CONTACT_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Telegramni bemor kartasi bilan bog'lash uchun "
            "\"Telefon raqamni ulashish\" tugmasini bosing. Raqam registraturadagi raqam bilan mos bo'lishi kerak."
        ),
    },
    "contact_rejected": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_CONTACT_REJECTED_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Faqat o'zingizning Telegram raqamingizni yuborish mumkin. "
            "Bot menyusidagi \"Telefon raqamni ulashish\" tugmasini bosing."
        ),
    },
    "patient_not_found": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_PATIENT_NOT_FOUND_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Bu raqam bilan bemor topilmadi. Raqamni registraturada tekshiring "
            "yoki chekdagi QR kodni skaner qiling."
        ),
    },
    "contact_linked": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_CONTACT_LINKED_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram bemor kartasi bilan bog'landi. "
            "Endi bot klinika xabarnomalarini yubora oladi."
        ),
    },
    "needs_link": {
        TELEGRAM_LANGUAGE_RU: TELEGRAM_NEEDS_LINK_MESSAGE,
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram hali bemorga bog'lanmagan. "
            "Chekdagi QR kodni skaner qiling yoki menyudagi telefon tugmasi orqali raqamingizni ulashing."
        ),
    },
    "welcome": {
        TELEGRAM_LANGUAGE_RU: (
            "Добро пожаловать в Kosmed Clinic.\n\n"
            "Через бота можно привязать Telegram к карте пациента, получать "
            "уведомления клиники и открывать результаты, когда они готовы."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Kosmed Clinic botiga xush kelibsiz.\n\n"
            "Bot orqali Telegramni bemor kartasiga bog'lash, klinika xabarnomalarini olish "
            "va natijalar tayyor bo'lganda ularni ochish mumkin."
        ),
    },
    "language_selected": {
        TELEGRAM_LANGUAGE_RU: "Язык изменён на русский. Главное меню обновлено.",
        TELEGRAM_LANGUAGE_UZ: "Til O'zbekchaga o'zgartirildi. Asosiy menyu yangilandi.",
    },
    "main_menu_refreshed": {
        TELEGRAM_LANGUAGE_RU: (
            "Главное меню обновлено. Если кнопки Telegram ещё показывают старый язык, "
            "сверните и снова откройте панель кнопок."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Asosiy menyu yangilandi. Agar Telegram tugmalari eski tilda ko'rinsa, "
            "tugmalar panelini yopib qayta oching."
        ),
    },
    "notification_consent": {
        TELEGRAM_LANGUAGE_RU: (
            "Разрешить Telegram-уведомления от клиники: напоминания, очередь, оплаты и готовые результаты?"
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Klinikadan Telegram xabarnomalarini olishga rozimisiz: eslatmalar, navbat, to'lovlar va tayyor natijalar?"
        ),
    },
    "notifications_enabled": {
        TELEGRAM_LANGUAGE_RU: "Уведомления включены.",
        TELEGRAM_LANGUAGE_UZ: "Xabarnomalar yoqildi.",
    },
    "notifications_disabled": {
        TELEGRAM_LANGUAGE_RU: "Уведомления отключены. Их можно включить позже через клинику.",
        TELEGRAM_LANGUAGE_UZ: "Xabarnomalar o'chirildi. Ularni keyin klinika orqali yoqish mumkin.",
    },
    "help": {
        TELEGRAM_LANGUAGE_RU: (
            "Kosmed Clinic bot\n\n"
            "Для пациента:\n"
            "🏥 Записаться на приём - отправить заявку через защищенный Mini App.\n"
            "🎫 Моя очередь - номер, кабинет, статус и позиция ожидания.\n"
            "📅 Мои визиты - последние и сегодняшние визиты без медицинских деталей.\n"
            "💳 Оплаты и долг - начислено, оплачено, долг и незавершенные платежи.\n"
            "📄 Результаты - до 3 готовых PDF-отчетов, только после привязки.\n"
            "📲 Онлайн-сервисы - карта подключенных и будущих защищенных функций.\n"
            "📋 Анкеты пациента - защищенное заполнение через Mini App.\n"
            "🧾 Документы и чеки - безопасный вход к будущему кабинету документов.\n"
            "🧑‍⚕️ Врачи и расписание - защищенный просмотр расписания.\n"
            "📲 Кабинет пациента - защищенный вход без медданных в чате.\n"
            "👤 Мой статус - привязка Telegram к карте пациента.\n"
            "⚙️ Настройки - язык и уведомления.\n"
            "👥 Режим сотрудника - вход только по персональной ссылке администратора или /staff.\n\n"
            "☎️ Связаться с клиникой - безопасная подсказка, куда обращаться по записи, кассе и срочным вопросам.\n\n"
            "Команды: /start, /menu, /services, /book, /queue, /visits, /payments, /results, "
            "/forms, /documents, /doctors, /cabinet, /profile, /settings, /support, /staff, /help.\n\n"
            "Для записи откройте Mini App из кнопки под сообщением \"Записаться на приём\". "
            "Для привязки отсканируйте QR с чека или нажмите "
            "\"Поделиться номером\".\n\n"
            "Для сотрудников: доступ отдельно через персональную ссылку администратора "
            "или /staff после привязки. В Telegram режим сотрудника только для просмотра; "
            "действия выполняются в приложении клиники."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Kosmed Clinic bot\n\n"
            "Bemor uchun:\n"
            "🏥 Qabulga yozilish - himoyalangan Mini App orqali so'rov yuborish.\n"
            "🎫 Mening navbatim - raqam, kabinet, holat va kutishdagi o'rin.\n"
            "📅 Mening tashriflarim - so'nggi va bugungi tashriflar, tibbiy tafsilotlarsiz.\n"
            "💳 To'lovlar va qarz - hisoblangan, to'langan, qarz va yakunlanmagan to'lovlar.\n"
            "📄 Natijalar - faqat bog'langan bemor uchun 3 tagacha tayyor PDF hisobot.\n"
            "📲 Onlayn xizmatlar - ulangan va kelajakdagi himoyalangan funksiyalar xaritasi.\n"
            "📋 Bemor anketalari - Mini App orqali himoyalangan to'ldirish.\n"
            "🧾 Hujjatlar va cheklar - kelajakdagi himoyalangan hujjatlar kabineti kirishi.\n"
            "🧑‍⚕️ Shifokorlar jadvali - himoyalangan jadval ko'rish.\n"
            "📲 Bemor kabineti - chatda tibbiy ma'lumotsiz himoyalangan kirish.\n"
            "👤 Mening holatim - Telegram bemor kartasiga bog'langanini ko'rish.\n"
            "⚙️ Sozlamalar - til va xabarnomalar.\n"
            "👥 Xodim rejimi - faqat administrator bergan shaxsiy havola yoki /staff orqali.\n\n"
            "☎️ Klinikaga bog'lanish - yozilish, kassa va shoshilinch savollar bo'yicha xavfsiz yo'l-yo'riq.\n\n"
            "Buyruqlar: /start, /menu, /services, /book, /queue, /visits, /payments, /results, "
            "/forms, /documents, /doctors, /cabinet, /profile, /settings, /support, /staff, /help.\n\n"
            "Yozilish uchun \"Qabulga yozilish\" xabari ostidagi Mini App tugmasini oching. "
            "Bog'lash uchun chekdagi QR kodni skaner qiling yoki "
            "\"Telefon raqamni ulashish\" tugmasini bosing.\n\n"
            "Xodimlar uchun: kirish administrator bergan shaxsiy havola orqali "
            "yoki bog'langandan keyin /staff orqali. Telegramdagi xodim rejimi faqat "
            "ko'rish uchun; amallar klinika ilovasida bajariladi."
        ),
    },
    "settings": {
        TELEGRAM_LANGUAGE_RU: (
            "Настройки Telegram\n\n"
            "Выберите язык обслуживания или режим уведомлений. После смены языка "
            "главное меню сразу обновится."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram sozlamalari\n\n"
            "Xizmat tilini yoki xabarnoma rejimini tanlang. Til o'zgarganda "
            "asosiy menyu darhol yangilanadi."
        ),
    },
    "book": {
        TELEGRAM_LANGUAGE_RU: (
            "Записаться на приём\n\n"
            "Онлайн-заявка на запись уже доступна через защищенный Mini App. "
            "Нажмите кнопку ниже, выберите дату и время, затем отправьте заявку: "
            "регистратура подтвердит детали.\n\n"
            "Бот не создаёт визит, очередь или оплату из свободного сообщения в чате "
            "и не принимает медицинские данные в тексте. После подтверждения записи "
            "вы сможете смотреть очередь, визиты, оплаты и готовые результаты в этом меню."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Qabulga yozilish\n\n"
            "Himoyalangan Mini App orqali yozilish so'rovi allaqachon ishlaydi. "
            "Quyidagi tugmani bosing, sana va vaqtni tanlang, keyin so'rovni yuboring: "
            "registratura ma'lumotlarni tasdiqlaydi.\n\n"
            "Bot chatdagi erkin matndan tashrif, navbat yoki to'lov yaratmaydi "
            "va tibbiy ma'lumotlarni matn orqali qabul qilmaydi. Yozilish tasdiqlangach, "
            "bu menyuda navbat, tashriflar, to'lovlar va tayyor natijalarni ko'rishingiz mumkin."
        ),
    },
    "service_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть защищенный раздел",
        TELEGRAM_LANGUAGE_UZ: "Havfsiz bo'limni ochish",
    },
    "patient_forms_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть анкету",
        TELEGRAM_LANGUAGE_UZ: "Anketani ochish",
    },
    "patient_documents_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть документы",
        TELEGRAM_LANGUAGE_UZ: "Hujjatlarni ochish",
    },
    "patient_doctors_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть расписание врачей",
        TELEGRAM_LANGUAGE_UZ: "Shifokorlar jadvalini ochish",
    },
    "patient_cabinet_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть мой кабинет",
        TELEGRAM_LANGUAGE_UZ: "Kabinetimni ochish",
    },
    "services_menu": {
        TELEGRAM_LANGUAGE_RU: (
            "Онлайн-сервисы\n\n"
            "Здесь собраны видимые кнопки для функций бота. Уже подключённые разделы "
            "откроют данные из системы, а неподключённые разделы покажут безопасную "
            "заглушку без создания записи, оплаты или медицинского документа в Telegram."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Onlayn xizmatlar\n\n"
            "Bu yerda bot funksiyalari uchun ko'rinadigan tugmalar jamlangan. Ulangan "
            "bo'limlar tizimdagi ma'lumotlarni ko'rsatadi, ulanmagan bo'limlar esa "
            "Telegramda yozuv, to'lov yoki tibbiy hujjat yaratmasdan xavfsiz izoh beradi."
        ),
    },
    "patient_forms": {
        TELEGRAM_LANGUAGE_RU: (
            "Анкеты пациента\n\n"
            "Анкеты пока не заполняются в Telegram. Этот раздел будет подключён через "
            "защищённый кабинет или Mini App, чтобы не принимать паспортные, медицинские "
            "и согласительные данные в обычном чате."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Bemor anketalari\n\n"
            "Anketalar hozircha Telegramda to'ldirilmaydi. Bu bo'lim keyin himoyalangan "
            "kabinet yoki Mini App orqali ulanadi, shunda pasport, tibbiy va rozilik "
            "ma'lumotlari oddiy chatda qabul qilinmaydi."
        ),
    },
    "patient_documents": {
        TELEGRAM_LANGUAGE_RU: (
            "Документы и чеки\n\n"
            "Чеки, направления и медицинские документы будут открываться только через "
            "защищённый кабинет. В Telegram остаются короткие уведомления и безопасные "
            "сводки без внутренних номеров."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Hujjatlar va cheklar\n\n"
            "Cheklar, yo'llanmalar va tibbiy hujjatlar faqat himoyalangan kabinet orqali "
            "ochiladi. Telegramda ichki raqamlarsiz qisqa xabarnomalar va xavfsiz "
            "xulosalar qoladi."
        ),
    },
    "doctor_schedule": {
        TELEGRAM_LANGUAGE_RU: (
            "Врачи и расписание\n\n"
            "Просмотр врачей и свободного времени пока не подключён к Telegram. "
            "Запись и изменение расписания выполняются через регистратуру или защищённое "
            "приложение клиники."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Shifokorlar jadvali\n\n"
            "Shifokorlar va bo'sh vaqtlarni ko'rish hozircha Telegramga ulanmagan. "
            "Yozilish va jadvalni o'zgartirish registratura yoki klinikaning himoyalangan "
            "ilovasi orqali bajariladi."
        ),
    },
    "patient_cabinet": {
        TELEGRAM_LANGUAGE_RU: (
            "Кабинет пациента\n\n"
            "Общий вход в кабинет пациента для Telegram ещё не включён. Сейчас безопасно "
            "доступны отдельные разделы меню: очередь, визиты, оплаты и готовые результаты. "
            "Кнопка оплаты откроет защищённый путь, когда он настроен для клиники."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Bemor kabineti\n\n"
            "Telegram uchun umumiy bemor kabineti kirishi hali yoqilmagan. Hozir menyuda "
            "navbat, tashriflar, to'lovlar va tayyor natijalar xavfsiz ko'rsatiladi. "
            "To'lov tugmasi klinikada sozlanganda himoyalangan yo'lni ochadi."
        ),
    },
    "staff_entry": {
        TELEGRAM_LANGUAGE_RU: (
            "Режим сотрудника\n\n"
            "Доступ для регистратора, врача, кассира, лаборатории и администратора "
            "включается только через персональную ссылку администратора или команду /staff "
            "после привязки сотрудника.\n\n"
            "В пациентском чате бот не выполняет внутренние действия клиники. Доступные "
            "staff-разделы остаются read-only, а вызов пациента, пропуск, перенос визита, "
            "возвраты и публикация документов требуют отдельного подтверждения в системе."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Xodim rejimi\n\n"
            "Registrator, shifokor, kassir, laboratoriya va administrator kirishi faqat "
            "administrator bergan shaxsiy havola yoki xodim bog'langandan keyin /staff "
            "buyrug'i orqali yoqiladi.\n\n"
            "Bemor chatida bot klinikaning ichki amallarini bajarmaydi. Mavjud staff "
            "bo'limlari read-only, bemorni chaqirish, o'tkazib yuborish, tashrifni ko'chirish, "
            "qaytarim va hujjat chiqarish esa tizimda alohida tasdiq talab qiladi."
        ),
    },
    "support": {
        TELEGRAM_LANGUAGE_RU: (
            "Связаться с клиникой\n\n"
            "Для записи, кассы и срочных вопросов обратитесь в регистратуру "
            "или позвоните по номеру, указанному на чеке и в клинике.\n\n"
            "Не отправляйте в Telegram диагнозы, результаты анализов, паспортные "
            "данные или фото документов. Медицинские детали смотрите только в "
            "защищенном кабинете или у сотрудника клиники."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Klinikaga bog'lanish\n\n"
            "Yozilish, kassa va shoshilinch savollar uchun registraturaga murojaat "
            "qiling yoki chekda va klinikada ko'rsatilgan raqamga qo'ng'iroq qiling.\n\n"
            "Telegram chatiga diagnoz, tahlil natijalari, pasport ma'lumotlari yoki "
            "hujjat rasmlarini yubormang. Tibbiy tafsilotlarni faqat himoyalangan "
            "kabinetda yoki klinika xodimi orqali ko'ring."
        ),
    },
    "lab_results_empty": {
        TELEGRAM_LANGUAGE_RU: (
            "Готовых PDF-результатов пока нет. "
            "Когда лаборатория финализирует отчет, он появится здесь."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Tayyor PDF natijalar hozircha yo'q. "
            "Laboratoriya hisobotni yakunlaganda u shu yerda paydo bo'ladi."
        ),
    },
    "lab_results_found": {
        TELEGRAM_LANGUAGE_RU: "Нашел готовые результаты: {count}. Отправляю PDF-файлы.",
        TELEGRAM_LANGUAGE_UZ: "Tayyor natijalar topildi: {count}. PDF fayllarni yuboryapman.",
    },
    "lab_results_send_failed": {
        TELEGRAM_LANGUAGE_RU: (
            "Не удалось отправить PDF-результаты. Обратитесь в регистратуру."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "PDF natijalarni yuborib bo'lmadi. Registraturaga murojaat qiling."
        ),
    },
    "lab_result_document_caption": {
        TELEGRAM_LANGUAGE_RU: (
            "Результат анализа: {template_name}\n"
            "Отчет #{report_id} от {report_date}"
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Tahlil natijasi: {template_name}\n"
            "Hisobot #{report_id}, sana: {report_date}"
        ),
    },
    "lab_result_document_failed_caption": {
        TELEGRAM_LANGUAGE_RU: "Отчет #{report_id}",
        TELEGRAM_LANGUAGE_UZ: "Hisobot #{report_id}",
    },
    "results_hint": {
        TELEGRAM_LANGUAGE_RU: (
            "Результаты будут приходить сюда, когда лаборатория или врач отметит их "
            "готовыми к выдаче. Если результат нужен срочно, обратитесь в регистратуру."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Natijalar laboratoriya yoki shifokor ularni berishga tayyor deb belgilaganda "
            "shu yerga keladi. Natija shoshilinch kerak bo'lsa, registraturaga murojaat qiling."
        ),
    },
    "profile_linked": {
        TELEGRAM_LANGUAGE_RU: (
            "Telegram привязан к пациенту: {patient}.\n{visit_summary}"
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram bemorga bog'langan: {patient}.\n{visit_summary}"
        ),
    },
    "recent_visit_none": {
        TELEGRAM_LANGUAGE_RU: "Последних визитов пока нет.",
        TELEGRAM_LANGUAGE_UZ: "Hozircha oxirgi tashriflar yo'q.",
    },
    "recent_visit_unknown_date": {
        TELEGRAM_LANGUAGE_RU: "дата не указана",
        TELEGRAM_LANGUAGE_UZ: "sana ko'rsatilmagan",
    },
    "recent_visit_summary": {
        TELEGRAM_LANGUAGE_RU: "Последний визит: #{visit_id}, {visit_date}, статус: {status}.",
        TELEGRAM_LANGUAGE_UZ: "Oxirgi tashrif: #{visit_id}, {visit_date}, holat: {status}.",
    },
    "visits_empty": {
        TELEGRAM_LANGUAGE_RU: "У пациента {patient} пока нет активных или недавних визитов.",
        TELEGRAM_LANGUAGE_UZ: "Bemor {patient} uchun faol yoki oxirgi tashriflar yo'q.",
    },
    "visits_patient": {
        TELEGRAM_LANGUAGE_RU: "Пациент: {patient}",
        TELEGRAM_LANGUAGE_UZ: "Bemor: {patient}",
    },
    "visits_title": {
        TELEGRAM_LANGUAGE_RU: "Мои визиты:",
        TELEGRAM_LANGUAGE_UZ: "Mening tashriflarim:",
    },
    "visits_line": {
        TELEGRAM_LANGUAGE_RU: "{index}. Визит #{visit_id} - {visit_date}, статус: {status}",
        TELEGRAM_LANGUAGE_UZ: "{index}. Tashrif #{visit_id} - {visit_date}, holat: {status}",
    },
    "visits_privacy_note": {
        TELEGRAM_LANGUAGE_RU: "В Telegram показываются только номер, дата и статус визита.",
        TELEGRAM_LANGUAGE_UZ: "Telegramda faqat tashrif raqami, sanasi va holati ko'rsatiladi.",
    },
    "payments_empty": {
        TELEGRAM_LANGUAGE_RU: (
            "Пациент: {patient}\n"
            "Активных начислений и оплат пока нет."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Bemor: {patient}\n"
            "Hozircha faol hisob-kitoblar va to'lovlar yo'q."
        ),
    },
    "payments_patient": {
        TELEGRAM_LANGUAGE_RU: "Пациент: {patient}",
        TELEGRAM_LANGUAGE_UZ: "Bemor: {patient}",
    },
    "payments_title": {
        TELEGRAM_LANGUAGE_RU: "Оплаты и долг:",
        TELEGRAM_LANGUAGE_UZ: "To'lovlar va qarz:",
    },
    "payments_billed": {
        TELEGRAM_LANGUAGE_RU: "Начислено: {amount} сум",
        TELEGRAM_LANGUAGE_UZ: "Hisoblangan: {amount} so'm",
    },
    "payments_paid": {
        TELEGRAM_LANGUAGE_RU: "Оплачено: {amount} сум",
        TELEGRAM_LANGUAGE_UZ: "To'langan: {amount} so'm",
    },
    "payments_debt": {
        TELEGRAM_LANGUAGE_RU: "Долг: {amount} сум",
        TELEGRAM_LANGUAGE_UZ: "Qarz: {amount} so'm",
    },
    "payments_pending": {
        TELEGRAM_LANGUAGE_RU: "Ожидает подтверждения: {amount} сум",
        TELEGRAM_LANGUAGE_UZ: "Tasdiqlanishi kutilmoqda: {amount} so'm",
    },
    "payments_visits": {
        TELEGRAM_LANGUAGE_RU: "Связанные визиты: {count}",
        TELEGRAM_LANGUAGE_UZ: "Bog'langan tashriflar: {count}",
    },
    "payments_online_unavailable": {
        TELEGRAM_LANGUAGE_RU: (
            "Онлайн-оплата пока не подключена. Для оплаты обратитесь в кассу."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Onlayn to'lov hozircha ulanmagan. To'lov uchun kassaga murojaat qiling."
        ),
    },
    "payments_protected_entry": {
        TELEGRAM_LANGUAGE_RU: (
            "Для оплаты откройте защищенный кабинет. В Telegram не отправляются номера счетов или платежей."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "To'lov uchun himoyalangan kabinetni oching. Telegramda hisob yoki to'lov raqamlari yuborilmaydi."
        ),
    },
    "payments_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть оплату в кабинете",
        TELEGRAM_LANGUAGE_UZ: "Kabinetda to'lovni ochish",
    },
    "booking_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Открыть запись в кабинете",
        TELEGRAM_LANGUAGE_UZ: "Kabinetda yozilish uchun ochish",
    },
    "onboarding_entry_button": {
        TELEGRAM_LANGUAGE_RU: "Оставить заявку на запись",
        TELEGRAM_LANGUAGE_UZ: "Qabul uchun so'rov qoldirish",
    },
    "unlinked_protected_action": {
        TELEGRAM_LANGUAGE_RU: (
            "Пока Telegram не привязан к карте пациента.\n\n"
            "Очередь, оплаты, документы и результаты доступны только после проверки "
            "регистратурой. Вы можете оставить безопасную заявку на запись: сотрудники "
            "свяжут её с существующей картой или создадут новую карту вручную."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram hozircha bemor kartasiga bog'lanmagan.\n\n"
            "Navbat, to'lovlar, hujjatlar va natijalar faqat registratura tekshiruvidan "
            "keyin ochiladi. Siz qabul uchun xavfsiz so'rov qoldirishingiz mumkin: "
            "xodimlar uni mavjud karta bilan bog'laydi yoki yangi kartani qo'lda yaratadi."
        ),
    },
    "queue_entry_button": {
        TELEGRAM_LANGUAGE_RU: "🎫 Открыть мою очередь",
        TELEGRAM_LANGUAGE_UZ: "🎫 Mening navbatimni ochish",
    },
    "queue_open_hint": {
        TELEGRAM_LANGUAGE_RU: "Нажмите кнопку ниже, чтобы открыть очередь в Mini App.",
        TELEGRAM_LANGUAGE_UZ: "Mini Appda navbatni ochish uchun quyidagi tugmani bosing.",
    },
    "visits_entry_button": {
        TELEGRAM_LANGUAGE_RU: "📅 Открыть мои визиты",
        TELEGRAM_LANGUAGE_UZ: "📅 Mening tashriflarimni ochish",
    },
    "visits_open_hint": {
        TELEGRAM_LANGUAGE_RU: "Нажмите кнопку ниже, чтобы открыть визиты в Mini App.",
        TELEGRAM_LANGUAGE_UZ: "Mini Appda tashriflarni ochish uchun quyidagi tugmani bosing.",
    },
    "queue_empty": {
        TELEGRAM_LANGUAGE_RU: (
            "Telegram привязан к пациенту: {patient}.\n"
            "{visit_summary}\n\n"
            "На сегодня активной очереди нет."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram bemorga bog'langan: {patient}.\n"
            "{visit_summary}\n\n"
            "Bugun faol navbat yo'q."
        ),
    },
    "queue_patient": {
        TELEGRAM_LANGUAGE_RU: "Пациент: {patient}",
        TELEGRAM_LANGUAGE_UZ: "Bemor: {patient}",
    },
    "queue_title": {
        TELEGRAM_LANGUAGE_RU: "Ваша очередь на сегодня:",
        TELEGRAM_LANGUAGE_UZ: "Bugungi navbatingiz:",
    },
    "queue_status": {
        TELEGRAM_LANGUAGE_RU: "статус: {status}",
        TELEGRAM_LANGUAGE_UZ: "holat: {status}",
    },
    "queue_position": {
        TELEGRAM_LANGUAGE_RU: "позиция: {position}",
        TELEGRAM_LANGUAGE_UZ: "navbatdagi o'rin: {position}",
    },
    "queue_cabinet": {
        TELEGRAM_LANGUAGE_RU: "Кабинет {cabinet}",
        TELEGRAM_LANGUAGE_UZ: "{cabinet}-xona",
    },
    "queue_more": {
        TELEGRAM_LANGUAGE_RU: "Еще записей: {count}",
        TELEGRAM_LANGUAGE_UZ: "Yana yozuvlar: {count}",
    },
    "queue_default_name": {
        TELEGRAM_LANGUAGE_RU: "Очередь",
        TELEGRAM_LANGUAGE_UZ: "Navbat",
    },
}
TELEGRAM_WEBHOOK_PUBLIC_ERROR = "Ошибка обработки webhook"
TELEGRAM_SEND_PUBLIC_ERROR = "Ошибка отправки сообщения"
TELEGRAM_BOT_INFO_PUBLIC_MESSAGE = "Ошибка получения информации о боте"
MINI_APP_BOOKING_REQUEST_ERROR_REASONS = frozenset(
    {
        "appointment_date_invalid",
        "appointment_date_in_past",
        "appointment_time_invalid",
        "appointment_service_invalid",
        "appointment_service_too_long",
        "doctor_id_invalid",
        "department_too_long",
        "notes_too_long",
    }
)
MINI_APP_FORMS_REQUEST_ERROR_REASONS = frozenset(
    {
        "patient_form_id_required",
        "patient_form_unknown",
        "patient_form_status_invalid",
        "patient_form_answers_invalid",
        "patient_form_answer_unknown_field",
        "patient_form_answer_type_invalid",
        "patient_form_answer_too_long",
        "patient_form_answer_required",
    }
)
QUEUE_TERMINAL_STATUSES = {"served", "incomplete", "no_show", "cancelled"}
QUEUE_WAITING_STATUSES = {"waiting"}
EMR_CLOSED_VISIT_STATUSES = {
    "closed",
    "completed",
    "served",
    "done",
    "cancelled",
    "canceled",
    "no_show",
}
QUEUE_TAG_LABELS = {
    "ecg": "ЭКГ",
    "cardiology_common": "Кардиология",
    "dermatology": "Дерматология",
    "stomatology": "Стоматология",
    "cosmetology": "Косметология",
    "lab": "Лаборатория",
    "general": "Общая очередь",
}
QUEUE_STATUS_LABELS = {
    "waiting": "ожидает",
    "called": "вызван",
    "in_service": "на приеме",
    "diagnostics": "на диагностике",
    "served": "завершен",
    "incomplete": "не завершен",
    "no_show": "не явился",
    "cancelled": "отменен",
}
QUEUE_TAG_LABELS_BY_LANGUAGE = {
    TELEGRAM_LANGUAGE_RU: QUEUE_TAG_LABELS,
    TELEGRAM_LANGUAGE_UZ: {
        "ecg": "EKG",
        "cardiology_common": "Kardiologiya",
        "dermatology": "Dermatologiya",
        "stomatology": "Stomatologiya",
        "cosmetology": "Kosmetologiya",
        "lab": "Laboratoriya",
        "general": "Umumiy navbat",
    },
}
QUEUE_STATUS_LABELS_BY_LANGUAGE = {
    TELEGRAM_LANGUAGE_RU: QUEUE_STATUS_LABELS,
    TELEGRAM_LANGUAGE_UZ: {
        "waiting": "kutmoqda",
        "called": "chaqirilgan",
        "in_service": "qabulda",
        "diagnostics": "diagnostikada",
        "served": "yakunlangan",
        "incomplete": "yakunlanmagan",
        "no_show": "kelmagan",
        "cancelled": "bekor qilingan",
    },
}
PAYMENT_PAID_STATUSES = {"paid", "completed"}
PAYMENT_PENDING_STATUSES = {"pending", "processing"}
UNPAID_INVOICE_STATUSES = {"pending", "processing"}
PAID_INVOICE_STATUSES = {"paid"}
RECONCILIATION_ALERT_THRESHOLD = Decimal("1000")
LAB_REPORT_READY_STATUSES = {"FINALIZED", "PRINTED"}
LAB_REPORT_PENDING_STATUSES = {"DRAFT", "IN_PROGRESS"}
LAB_RESULT_DELIVERY_EVENT_TYPES = {
    "lab_results",
    "lab_result_sent_confirmation",
    "lab_critical_result",
}
SUCCESSFUL_DELIVERY_STATUSES = {"delivered", "seen", "read", "archived"}
PENDING_DELIVERY_STATUSES = {"pending", "dispatched"}
MAX_TELEGRAM_LAB_REPORTS = 3
PATIENT_MINI_APP_ENTRY_TOKEN_PREFIX = "pma"
PATIENT_ONBOARDING_ENTRY_TOKEN_PREFIX = "pmo"
PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR = "_"
PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS = 10 * 60
PATIENT_MINI_APP_ENTRY_TOKEN_SECTIONS = {
    "appointments",
    "forms",
    "cabinet",
    "visits",
    "queue",
    "payments",
    "results",
    "documents",
    "doctors",
}


def _telegram_update_summary(update: dict[str, Any]) -> dict[str, Any]:
    message = update.get("message") or update.get("edited_message") or {}
    callback_query = update.get("callback_query") or {}
    return {
        "update_id": update.get("update_id"),
        "message_id": message.get("message_id"),
        "callback_query_id": callback_query.get("id"),
        "has_message": bool(message),
        "has_callback_query": bool(callback_query),
    }


def _extract_ticket_qr_start_payload(
    update: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    message = update.get("message") or {}
    text = str(message.get("text") or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None

    command = parts[0].split("@", 1)[0]
    payload = parts[1].strip()
    if command != "/start" or not payload.startswith(f"{TELEGRAM_TICKET_QR_PREFIX}_"):
        return None

    return payload, message


def _extract_staff_link_start_payload(
    update: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    message = update.get("message") or {}
    text = str(message.get("text") or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None

    command = parts[0].split("@", 1)[0].lower()
    payload = parts[1].strip()
    if command != "/start":
        return None

    staff_prefix = f"{STAFF_LINK_TOKEN_PREFIX}{STAFF_LINK_TOKEN_SEPARATOR}"
    if not payload.startswith(staff_prefix):
        return None

    return payload, message


def _normalize_patient_language(language_code: Any) -> str:
    value = str(language_code or "").strip().lower().replace("_", "-")
    if value in {"uz", "uz-latn", "uzbek", "o'zbekcha", "ozbekcha"} or value.startswith("uz-"):
        return TELEGRAM_LANGUAGE_UZ
    return TELEGRAM_LANGUAGE_RU


def _localized_text(key: str, language_code: Any) -> str:
    language = _normalize_patient_language(language_code)
    values = TELEGRAM_LOCALIZED_TEXTS.get(key) or {}
    return values.get(language) or values.get(TELEGRAM_LANGUAGE_RU) or ""


def _base36_encode(value: int) -> str:
    if value < 0:
        raise ValueError("base36 value must be non-negative")
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def _base36_decode(value: str) -> int:
    return int(value, 36)


def _patient_mini_app_token_section(section: str | None) -> str:
    normalized = str(section or "cabinet").strip().lower()
    if normalized in {"booking", "doctors"}:
        return "appointments"
    if normalized == "payment":
        return "payments"
    if normalized == "documents":
        return "results"
    if normalized in PATIENT_MINI_APP_ENTRY_TOKEN_SECTIONS:
        return normalized
    return "cabinet"


def _patient_mini_app_entry_token_signature(body: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base36_encode(int.from_bytes(digest[:12], "big"))


def _patient_mini_app_entry_token_ttl_seconds() -> int:
    """Return the configured entry-token TTL, honoring test monkeypatches.

    Tests freeze the TTL by patching
    ``telegram_webhook.PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS``. The split
    ``_helpers`` module imports the constant directly, so a plain module-level
    lookup would bypass the patch. Resolve via the public package namespace at
    call time so the patched value (if any) is used.
    """
    from app.api.v1.endpoints import telegram_webhook as _tw

    return int(
        getattr(
            _tw,
            "PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS",
            PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS,
        )
    )


def _build_patient_mini_app_entry_token(chat_id: int, section: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(
        seconds=_patient_mini_app_entry_token_ttl_seconds()
    )
    body = PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR.join(
        [
            PATIENT_MINI_APP_ENTRY_TOKEN_PREFIX,
            _patient_mini_app_token_section(section),
            _base36_encode(int(chat_id)),
            _base36_encode(
                int(expires_at.replace(tzinfo=UTC).timestamp())
            ),
            _base36_encode(secrets.randbits(48)),
        ]
    )
    signature = _patient_mini_app_entry_token_signature(body)
    return f"{body}{PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR}{signature}"


def _build_patient_onboarding_entry_token(chat_id: int, section: str = "appointments") -> str:
    expires_at = datetime.now(UTC) + timedelta(
        seconds=_patient_mini_app_entry_token_ttl_seconds()
    )
    body = PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR.join(
        [
            PATIENT_ONBOARDING_ENTRY_TOKEN_PREFIX,
            _patient_mini_app_token_section(section),
            _base36_encode(int(chat_id)),
            _base36_encode(
                int(expires_at.replace(tzinfo=UTC).timestamp())
            ),
            _base36_encode(secrets.randbits(48)),
        ]
    )
    signature = _patient_mini_app_entry_token_signature(body)
    return f"{body}{PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR}{signature}"


def _parse_patient_mini_app_entry_token(
    token: str,
    *,
    expected_section: str | None = None,
) -> dict[str, Any] | None:
    parts = str(token or "").split(PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR)
    if len(parts) != 6 or parts[0] != PATIENT_MINI_APP_ENTRY_TOKEN_PREFIX:
        return None

    section = _patient_mini_app_token_section(parts[1])
    if expected_section and section != _patient_mini_app_token_section(expected_section):
        return None

    body = PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR.join(parts[:5])
    if not hmac.compare_digest(
        parts[5],
        _patient_mini_app_entry_token_signature(body),
    ):
        return None

    try:
        chat_id = _base36_decode(parts[2])
        expires_at = datetime.fromtimestamp(_base36_decode(parts[3]), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None

    if expires_at < datetime.now(UTC):
        return None

    return {
        "chat_id": chat_id,
        "section": section,
        "expires_at": expires_at,
    }


def _parse_patient_onboarding_entry_token(
    token: str,
    *,
    expected_section: str | None = None,
) -> dict[str, Any] | None:
    parts = str(token or "").split(PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR)
    if len(parts) != 6 or parts[0] != PATIENT_ONBOARDING_ENTRY_TOKEN_PREFIX:
        return None

    section = _patient_mini_app_token_section(parts[1])
    if expected_section and section != _patient_mini_app_token_section(expected_section):
        return None

    body = PATIENT_MINI_APP_ENTRY_TOKEN_SEPARATOR.join(parts[:5])
    if not hmac.compare_digest(
        parts[5],
        _patient_mini_app_entry_token_signature(body),
    ):
        return None

    try:
        chat_id = _base36_decode(parts[2])
        expires_at = datetime.fromtimestamp(_base36_decode(parts[3]), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None

    if expires_at < datetime.now(UTC):
        return None

    return {
        "chat_id": chat_id,
        "section": section,
        "expires_at": expires_at,
    }


def _append_patient_mini_app_entry_token(entry_url: str, token: str) -> str:
    separator = "&" if "?" in entry_url else "?"
    return f"{entry_url}{separator}entryToken={token}"


def _detect_local_lan_ip() -> str | None:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0)
        try:
            probe.connect(("8.8.8.8", 80))
            local_ip = probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            return None

    try:
        parsed_ip = ipaddress.ip_address(local_ip)
    except ValueError:
        return None
    if parsed_ip.is_loopback or parsed_ip.is_unspecified:
        return None
    return local_ip


def _is_local_frontend_host(hostname: str | None) -> bool:
    host = str(hostname or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _telegram_patient_frontend_url() -> str | None:
    configured_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip()
    if not configured_url:
        return None

    parsed = urlsplit(configured_url)
    if parsed.scheme != "http" or not _is_local_frontend_host(parsed.hostname):
        return configured_url

    local_ip = _detect_local_lan_ip()
    if not local_ip:
        return configured_url

    port = parsed.port or 5173
    netloc = f"{local_ip}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _patient_entry_url(section: str | None = None) -> str | None:
    frontend_url = _telegram_patient_frontend_url()
    if not frontend_url:
        return None

    if section == "booking":
        route = PATIENT_BOOKING_ENTRY_ROUTE
    elif section == "payment":
        route = PATIENT_PAYMENT_ENTRY_ROUTE
    elif section:
        route = f"{PATIENT_MINI_APP_ENTRY_ROUTE}?section={section}"
    else:
        route = PATIENT_MINI_APP_ENTRY_ROUTE

    if not route.startswith("/"):
        route = f"/{route}"
    return f"{frontend_url.rstrip('/')}{route}"


def _telegram_entry_button(text: str, entry_url: str) -> dict[str, Any]:
    button: dict[str, Any] = {"text": text}
    if entry_url.lower().startswith("https://"):
        button["web_app"] = {"url": entry_url}
    else:
        button["url"] = entry_url
    return button


def _patient_payment_entry_url() -> str | None:
    return _patient_entry_url("payment")


def _patient_booking_entry_url() -> str | None:
    return _patient_entry_url("booking")


def _telegram_service_entry_markup(
    db: Session,
    chat_id: int,
    section: str,
    button_text_key: str,
) -> dict[str, Any] | None:
    from app.api.v1.endpoints.telegram_webhook._staff_commands import (
        _patient_for_telegram_chat,
    )

    telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return None

    entry_url = _patient_entry_url(section)
    if not entry_url:
        return None

    if not entry_url.lower().startswith("https://"):
        entry_token = _build_patient_mini_app_entry_token(
            chat_id,
            _patient_mini_app_token_section(section),
        )
        entry_url = _append_patient_mini_app_entry_token(entry_url, entry_token)

    language = _telegram_chat_language(db, chat_id)
    return {
        "inline_keyboard": [
            [
                _telegram_entry_button(
                    _localized_text(button_text_key, language),
                    entry_url,
                )
            ]
        ]
    }


def _telegram_onboarding_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    entry_url = _patient_entry_url("booking")
    if not entry_url:
        return None

    if not entry_url.lower().startswith("https://"):
        entry_token = _build_patient_onboarding_entry_token(
            chat_id,
            "appointments",
        )
        entry_url = _append_patient_mini_app_entry_token(entry_url, entry_token)

    language = _telegram_chat_language(db, chat_id)
    return {
        "inline_keyboard": [
            [
                _telegram_entry_button(
                    _localized_text("onboarding_entry_button", language),
                    entry_url,
                )
            ]
        ]
    }


def _telegram_protected_or_onboarding_markup(
    db: Session,
    chat_id: int,
    section: str,
    button_text_key: str,
) -> dict[str, Any] | None:
    protected_markup = _telegram_service_entry_markup(
        db,
        chat_id,
        section,
        button_text_key,
    )
    if protected_markup:
        return protected_markup
    return _telegram_onboarding_entry_markup(db, chat_id)


def _telegram_payment_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "payment",
        "payments_entry_button",
    )


def _telegram_booking_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "booking",
        "booking_entry_button",
    )


def _telegram_queue_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "queue",
        "queue_entry_button",
    )


def _telegram_visits_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "visits",
        "visits_entry_button",
    )


def _telegram_patient_forms_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "forms",
        "patient_forms_entry_button",
    )


def _telegram_patient_documents_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "documents",
        "patient_documents_entry_button",
    )


def _telegram_patient_doctors_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "doctors",
        "patient_doctors_entry_button",
    )


def _telegram_patient_cabinet_entry_markup(db: Session, chat_id: int) -> dict[str, Any] | None:
    return _telegram_protected_or_onboarding_markup(
        db,
        chat_id,
        "cabinet",
        "patient_cabinet_entry_button",
    )


def _localized_main_menu(language_code: Any) -> dict[str, Any]:
    return TELEGRAM_MAIN_MENUS.get(
        _normalize_patient_language(language_code), TELEGRAM_MAIN_MENU
    )


def _localized_services_menu(language_code: Any) -> dict[str, Any]:
    return TELEGRAM_PATIENT_SERVICES_MENUS.get(
        _normalize_patient_language(language_code),
        TELEGRAM_PATIENT_SERVICES_MENUS[TELEGRAM_LANGUAGE_RU],
    )


def _localized_notification_consent_menu(language_code: Any) -> dict[str, Any]:
    return TELEGRAM_NOTIFICATION_CONSENT_MENUS.get(
        _normalize_patient_language(language_code),
        TELEGRAM_NOTIFICATION_CONSENT_MENUS[TELEGRAM_LANGUAGE_RU],
    )


def _localized_settings_menu(language_code: Any) -> dict[str, Any]:
    language = _normalize_patient_language(language_code)
    settings_menu = TELEGRAM_SETTINGS_MENUS.get(
        language,
        TELEGRAM_SETTINGS_MENUS[TELEGRAM_LANGUAGE_RU],
    )
    main_keyboard = _localized_main_menu(language).get("keyboard", [])
    settings_keyboard = settings_menu.get("keyboard", [])
    return {
        **settings_menu,
        "keyboard": settings_keyboard[:2] + main_keyboard,
    }


def _telegram_chat_language(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    return _normalize_patient_language(getattr(telegram_user, "language_code", None))


def _telegram_chat_text(db: Session, chat_id: int, key: str) -> str:
    return _localized_text(key, _telegram_chat_language(db, chat_id))


def _telegram_chat_menu(db: Session, chat_id: int) -> dict[str, Any]:
    return _localized_main_menu(_telegram_chat_language(db, chat_id))


def _telegram_settings_message(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    language = _normalize_patient_language(getattr(telegram_user, "language_code", None))
    labels = TELEGRAM_SETTINGS_STATUS_LABELS.get(
        language, TELEGRAM_SETTINGS_STATUS_LABELS[TELEGRAM_LANGUAGE_RU]
    )
    language_label = labels["language"].get(language, labels["language"][TELEGRAM_LANGUAGE_RU])
    notifications_enabled = bool(getattr(telegram_user, "notifications_enabled", False))
    notification_label = (
        labels["notifications_on"] if notifications_enabled else labels["notifications_off"]
    )
    return _localized_text("settings", language) + labels["template"].format(
        language_label=language_label,
        notification_label=notification_label,
    )


TELEGRAM_PATIENT_BUTTON_ICON_PREFIXES = (
    "📱",
    "📲",
    "🏥",
    "🎫",
    "📅",
    "💳",
    "👤",
    "📄",
    "📋",
    "🧾",
    "🧑‍⚕",
    "👥",
    "⚙",
    "❓",
    "☎",
    "🔔",
    "🔕",
    "⬅",
    "🇷🇺",
    "🇺🇿",
)


def _normalize_patient_button_text(text: Any) -> str:
    value = " ".join(str(text or "").strip().lower().split())
    value = value.replace("\ufe0f", "").strip()
    for prefix in TELEGRAM_PATIENT_BUTTON_ICON_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    return value


def _patient_text_handler_aliases(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    aliases: dict[str, Any] = {}
    for label, handler in pairs:
        raw_original = " ".join(str(label or "").strip().lower().split())
        if raw_original:
            aliases[raw_original] = handler
        raw = raw_original.replace("\ufe0f", "").strip()
        if raw:
            aliases[raw] = handler
        normalized = _normalize_patient_button_text(label)
        if normalized:
            aliases[normalized] = handler
    return aliases

