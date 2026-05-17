"""
Webhook endpoint для обработки входящих сообщений от Telegram
"""

import hashlib
import html
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.v1.endpoints.admin_telegram import (
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
from app.crud import audit as crud_audit
from app.crud import telegram_config as crud_telegram
from app.db.session import get_db
from app.models.clinic import Doctor
from app.models.lab import LabReportInstance
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice
from app.models.payment_webhook import PaymentWebhook
from app.models.telegram_config import TelegramMessage, TelegramUser
from app.models.user import User
from app.models.visit import Visit
from app.models.webhook import WebhookCall, WebhookCallStatus, WebhookEvent
from app.services.lab_report_pdf_service import lab_report_pdf_service
from app.services.lab_reporting_service import LabReportingService
from app.services.payment_reconciliation_api_service import (
    PaymentReconciliationApiService,
)
from app.services.telegram_bot import get_telegram_bot_service
from app.services.visit_confirmation_service import (
    TELEGRAM_TICKET_QR_PREFIX,
    consume_telegram_ticket_start_token,
)
from app.utils.validators import normalize_phone_uz

logger = logging.getLogger(__name__)
router = APIRouter()
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
        [{"text": "Поделиться номером", "request_contact": True}],
        [{"text": "Моя очередь"}, {"text": "Оплаты и долг"}],
        [{"text": "Мой статус"}, {"text": "Результаты"}],
        [{"text": "Настройки"}, {"text": "Помощь"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
}
TELEGRAM_LANGUAGE_RU = "ru"
TELEGRAM_LANGUAGE_UZ = "uz-Latn"
TELEGRAM_LANGUAGE_MENU = {
    "keyboard": [[{"text": "Русский"}, {"text": "O'zbekcha"}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}
TELEGRAM_NOTIFICATION_CONSENT_MENUS = {
    TELEGRAM_LANGUAGE_RU: {
        "keyboard": [[{"text": "Разрешить уведомления"}, {"text": "Без уведомлений"}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    },
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [[{"text": "Xabarnomalarga roziman"}, {"text": "Xabarnomasiz"}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    },
}
TELEGRAM_MAIN_MENUS = {
    TELEGRAM_LANGUAGE_RU: TELEGRAM_MAIN_MENU,
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [
            [{"text": "Telefon raqamni ulashish", "request_contact": True}],
            [{"text": "Mening navbatim"}, {"text": "To'lovlar va qarz"}],
            [{"text": "Mening holatim"}, {"text": "Natijalar"}],
            [{"text": "Sozlamalar"}, {"text": "Yordam"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
}
TELEGRAM_SETTINGS_MENUS = {
    TELEGRAM_LANGUAGE_RU: {
        "keyboard": [
            [{"text": "Русский"}, {"text": "O'zbekcha"}],
            [{"text": "Разрешить уведомления"}, {"text": "Без уведомлений"}],
            [{"text": "Моя очередь"}, {"text": "Помощь"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    },
    TELEGRAM_LANGUAGE_UZ: {
        "keyboard": [
            [{"text": "Русский"}, {"text": "O'zbekcha"}],
            [{"text": "Xabarnomalarga roziman"}, {"text": "Xabarnomasiz"}],
            [{"text": "Mening navbatim"}, {"text": "Yordam"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
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
            "Команды бота:\n"
            "/start - главное меню\n"
            "/queue - моя очередь\n"
            "/payments - оплаты и долг\n"
            "/profile - статус привязки\n"
            "/settings - язык и уведомления\n"
            "/results - получить готовые PDF-результаты\n\n"
            "Для привязки можно отсканировать QR с чека или нажать "
            "\"Поделиться номером\"."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Bot buyruqlari:\n"
            "/start - asosiy menyu\n"
            "/queue - mening navbatim\n"
            "/payments - to'lovlar va qarz\n"
            "/profile - bog'lanish holati\n"
            "/settings - til va xabarnomalar\n"
            "/results - tayyor PDF natijalarni olish\n\n"
            "Bog'lash uchun chekdagi QR kodni skaner qiling yoki "
            "\"Telefon raqamni ulashish\" tugmasini bosing."
        ),
    },
    "settings": {
        TELEGRAM_LANGUAGE_RU: (
            "Настройки Telegram: выберите язык обслуживания или режим уведомлений."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Telegram sozlamalari: xizmat tilini yoki xabarnoma rejimini tanlang."
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
        TELEGRAM_LANGUAGE_RU: "Визит: {visits}",
        TELEGRAM_LANGUAGE_UZ: "Tashrif: {visits}",
    },
    "payments_online_unavailable": {
        TELEGRAM_LANGUAGE_RU: (
            "Онлайн-оплата пока не подключена. Для оплаты обратитесь в кассу."
        ),
        TELEGRAM_LANGUAGE_UZ: (
            "Onlayn to'lov hozircha ulanmagan. To'lov uchun kassaga murojaat qiling."
        ),
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


def _telegram_update_summary(update: Dict[str, Any]) -> Dict[str, Any]:
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
    update: Dict[str, Any],
) -> tuple[str, Dict[str, Any]] | None:
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
    update: Dict[str, Any],
) -> tuple[str, Dict[str, Any]] | None:
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


def _localized_main_menu(language_code: Any) -> Dict[str, Any]:
    return TELEGRAM_MAIN_MENUS.get(
        _normalize_patient_language(language_code), TELEGRAM_MAIN_MENU
    )


def _localized_notification_consent_menu(language_code: Any) -> Dict[str, Any]:
    return TELEGRAM_NOTIFICATION_CONSENT_MENUS.get(
        _normalize_patient_language(language_code),
        TELEGRAM_NOTIFICATION_CONSENT_MENUS[TELEGRAM_LANGUAGE_RU],
    )


def _localized_settings_menu(language_code: Any) -> Dict[str, Any]:
    return TELEGRAM_SETTINGS_MENUS.get(
        _normalize_patient_language(language_code),
        TELEGRAM_SETTINGS_MENUS[TELEGRAM_LANGUAGE_RU],
    )


def _telegram_chat_language(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    return _normalize_patient_language(getattr(telegram_user, "language_code", None))


def _telegram_chat_text(db: Session, chat_id: int, key: str) -> str:
    return _localized_text(key, _telegram_chat_language(db, chat_id))


def _telegram_chat_menu(db: Session, chat_id: int) -> Dict[str, Any]:
    return _localized_main_menu(_telegram_chat_language(db, chat_id))


def _upsert_ticket_qr_telegram_user(
    db: Session,
    message: Dict[str, Any],
    patient_id: int | None = None,
    language_code: str | None = None,
    notifications_enabled: bool | None = None,
) -> None:
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, int(chat_id))
    payload = {
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "active": True,
        "blocked": False,
        "last_activity": datetime.utcnow(),
    }
    if language_code is not None:
        payload["language_code"] = _normalize_patient_language(language_code)
    elif not telegram_user:
        payload["language_code"] = _normalize_patient_language(
            from_user.get("language_code") or TELEGRAM_LANGUAGE_RU
        )
    if patient_id is not None:
        payload["patient_id"] = patient_id
    if notifications_enabled is not None:
        payload["notifications_enabled"] = notifications_enabled
        payload["appointment_reminders"] = notifications_enabled
        payload["lab_notifications"] = notifications_enabled

    if telegram_user:
        for field, value in payload.items():
            if hasattr(telegram_user, field):
                setattr(telegram_user, field, value)
        db.flush()
        return

    create_notifications_enabled = payload.pop("notifications_enabled", True)
    create_appointment_reminders = payload.pop("appointment_reminders", True)
    create_lab_notifications = payload.pop("lab_notifications", True)
    db.add(
        TelegramUser(
            **payload,
            chat_id=int(chat_id),
            notifications_enabled=create_notifications_enabled,
            appointment_reminders=create_appointment_reminders,
            lab_notifications=create_lab_notifications,
        )
    )
    db.flush()


def _staff_telegram_reference_hash(chat_id: int) -> str:
    digest = hashlib.sha256(f"staff-telegram-chat:{chat_id}".encode("utf-8")).hexdigest()
    return f"telegram_chat:{digest[:24]}"


def _upsert_staff_link_telegram_user(
    db: Session,
    message: Dict[str, Any],
    *,
    linked_user_id: int,
) -> TelegramUser | None:
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, int(chat_id))
    payload = {
        "user_id": linked_user_id,
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "active": True,
        "blocked": False,
        "last_activity": datetime.utcnow(),
    }

    if telegram_user:
        for field, value in payload.items():
            if hasattr(telegram_user, field):
                setattr(telegram_user, field, value)
        db.flush()
        return telegram_user

    telegram_user = TelegramUser(
        **payload,
        chat_id=int(chat_id),
        language_code=_normalize_patient_language(
            from_user.get("language_code") or TELEGRAM_LANGUAGE_RU
        ),
        notifications_enabled=False,
        appointment_reminders=False,
        lab_notifications=False,
    )
    db.add(telegram_user)
    db.flush()
    return telegram_user


def _record_staff_link_audit(
    db: Session,
    *,
    action: str,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int | None = None,
    telegram_user_id: int | None = None,
    role: str | None = None,
    reason: str | None = None,
) -> None:
    result = "success" if action == "staff_link_created" else "rejected"
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": action,
        "target_type": "telegram_user",
        "target_reference_hash": _staff_telegram_reference_hash(chat_id),
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
    }
    if reason:
        payload["reason"] = reason

    crud_audit.log(
        db,
        action=action,
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _record_staff_command_audit(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int | None,
    telegram_user_id: int | None,
    role: str,
    command_key: str,
    menu_item_key: str | None = None,
    result: str = "handled",
    reason: str | None = None,
) -> None:
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": "staff_command_received",
        "target_type": "telegram_user",
        "target_reference_hash": _staff_telegram_reference_hash(chat_id),
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "command_key": command_key,
        "read_only": True,
        "state_changing_action": False,
        "redacted": True,
    }
    if menu_item_key:
        payload["menu_item_key"] = menu_item_key
    if reason:
        payload["reason"] = reason

    crud_audit.log(
        db,
        action="staff_command_received",
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _staff_action_reference_hash(operation_key: str) -> str:
    digest = hashlib.sha256(f"staff_action:{operation_key}".encode()).hexdigest()
    return f"staff_action:{digest[:24]}"


def _record_staff_action_denied_audit(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int,
    telegram_user_id: int | None,
    role: str,
    operation_key: str,
    command_key: str,
    reason: str,
) -> None:
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": "staff_action_denied",
        "target_type": "telegram_staff_action",
        "target_reference_hash": _staff_action_reference_hash(operation_key),
        "result": "denied",
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "operation_key": operation_key,
        "command_key": command_key,
        "confirmation_required": True,
        "telegram_execution_enabled": False,
        "domain_mutation": False,
        "state_changing_action": True,
        "redacted": True,
        "reason": reason,
    }
    crud_audit.log(
        db,
        action="staff_action_denied",
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _staff_read_only_commands() -> set[str]:
    return {
        str(item.get("command") or "").lower()
        for item in STAFF_BOT_COMMAND_REGISTRATION_CONTRACT.get("commands", [])
        if item.get("intent") == "read_only" and item.get("command")
    }


def _staff_menu_for_role(role: Any) -> Dict[str, Any] | None:
    role_key = _normalize_staff_role(role)
    for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT:
        if role_menu.get("role") == role_key:
            return role_menu
    return None


def _staff_menu_keyboard(role_menu: Dict[str, Any]) -> Dict[str, Any]:
    rows = [
        [{"text": str(item.get("label") or item.get("key"))}]
        for item in role_menu.get("items", [])
        if item.get("intent") == "read_only"
    ]
    rows.append([{"text": "/staff"}, {"text": "/help"}])
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def _staff_menu_message(user: User, role_menu: Dict[str, Any]) -> str:
    items = [
        str(item.get("label") or item.get("key"))
        for item in role_menu.get("items", [])
        if item.get("intent") == "read_only"
    ]
    lines = [
        "Staff read-only menu",
        f"Role: {_normalize_staff_role(getattr(user, 'role', None))}",
        "",
        "Available:",
    ]
    lines.extend(f"- {item}" for item in items)
    lines.extend(
        [
            "",
            "State-changing actions are disabled in Telegram.",
        ]
    )
    return "\n".join(lines)


def _staff_read_only_item_labels() -> set[str]:
    labels: set[str] = set()
    for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT:
        for item in role_menu.get("items", []):
            label = str(item.get("label") or "").strip().lower()
            if label:
                labels.add(label)
            key = str(item.get("key") or "").strip().lower()
            if key:
                labels.add(key)
    return labels


def _staff_menu_item_for_text(
    role_menu: Dict[str, Any], text: str
) -> Dict[str, Any] | None:
    normalized_text = text.strip().lower()
    for item in role_menu.get("items", []):
        label = str(item.get("label") or "").strip().lower()
        key = str(item.get("key") or "").strip().lower()
        if normalized_text in {label, key}:
            return item
    return None


def _staff_menu_item_for_command(
    role_menu: Dict[str, Any], command: str
) -> Dict[str, Any] | None:
    allowed_keys = set(STAFF_COMMAND_DOMAIN_ITEM_KEYS.get(command, ()))
    if not allowed_keys:
        return None
    for item in role_menu.get("items", []):
        if str(item.get("key") or "").strip().lower() in allowed_keys:
            return item
    return None


def _today_start() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


def _status_counts(rows: list[tuple[Any, Any]]) -> Dict[str, int]:
    return {str(status or "unknown"): int(count or 0) for status, count in rows}


def _format_money(amount: Any) -> str:
    value = amount if isinstance(amount, Decimal) else Decimal(str(amount or 0))
    return f"{value.quantize(Decimal('0.01'))} UZS"


def _queue_status_counts(db: Session) -> Dict[str, int]:
    rows = (
        db.query(OnlineQueueEntry.status, func.count(OnlineQueueEntry.id))
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(DailyQueue.day == date.today())
        .group_by(OnlineQueueEntry.status)
        .all()
    )
    return _status_counts(rows)


def _payment_status_rows(db: Session) -> list[tuple[str, int, Decimal]]:
    return [
        (str(status or "unknown"), int(count or 0), amount or Decimal("0"))
        for status, count, amount in (
            db.query(
                Payment.status,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .filter(Payment.created_at >= _today_start())
            .group_by(Payment.status)
            .all()
        )
    ]


def _payment_invoice_status_rows(db: Session) -> list[tuple[str, int, Decimal]]:
    return [
        (str(status or "unknown"), int(count or 0), amount or Decimal("0"))
        for status, count, amount in (
            db.query(
                PaymentInvoice.status,
                func.count(PaymentInvoice.id),
                func.coalesce(func.sum(PaymentInvoice.total_amount), 0),
            )
            .filter(PaymentInvoice.created_at >= _today_start())
            .group_by(PaymentInvoice.status)
            .all()
        )
    ]


def _lab_status_counts(db: Session) -> Dict[str, int]:
    rows = (
        db.query(LabReportInstance.status, func.count(LabReportInstance.id))
        .filter(LabReportInstance.created_at >= _today_start())
        .group_by(LabReportInstance.status)
        .all()
    )
    return _status_counts(rows)


def _lab_delivery_status_counts(db: Session) -> Dict[str, int]:
    rows = (
        db.query(
            NotificationDelivery.delivery_status,
            func.count(NotificationDelivery.id),
        )
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationDelivery.created_at >= _today_start(),
            NotificationDelivery.channel == "telegram",
            NotificationEvent.event_type.in_(LAB_RESULT_DELIVERY_EVENT_TYPES),
        )
        .group_by(NotificationDelivery.delivery_status)
        .all()
    )
    return _status_counts(rows)


def _integration_error_counts(db: Session) -> Dict[str, int]:
    failed_webhook_calls_today = (
        db.query(func.count(WebhookCall.id))
        .filter(
            WebhookCall.created_at >= _today_start(),
            WebhookCall.status == WebhookCallStatus.FAILED,
        )
        .scalar()
        or 0
    )
    retrying_webhook_calls = (
        db.query(func.count(WebhookCall.id))
        .filter(WebhookCall.status == WebhookCallStatus.RETRYING)
        .scalar()
        or 0
    )
    unprocessed_webhook_events = (
        db.query(func.count(WebhookEvent.id))
        .filter(WebhookEvent.processed.is_(False))
        .scalar()
        or 0
    )
    failed_payment_webhooks_today = (
        db.query(func.count(PaymentWebhook.id))
        .filter(
            PaymentWebhook.created_at >= _today_start(),
            PaymentWebhook.status == "failed",
        )
        .scalar()
        or 0
    )
    return {
        "failed_webhook_calls_today": int(failed_webhook_calls_today),
        "retrying_webhook_calls": int(retrying_webhook_calls),
        "unprocessed_webhook_events": int(unprocessed_webhook_events),
        "failed_payment_webhooks_today": int(failed_payment_webhooks_today),
    }


def _visit_status_counts(db: Session, user: User | None = None) -> Dict[str, int]:
    query = db.query(Visit.status, func.count(Visit.id)).filter(
        Visit.visit_date == date.today()
    )
    if _normalize_staff_role(getattr(user, "role", None)) == "doctor":
        doctor = (
            db.query(Doctor)
            .filter(
                Doctor.user_id == getattr(user, "id", None),
                Doctor.active.is_(True),
            )
            .first()
        )
        if not doctor:
            return {}
        query = query.filter(Visit.doctor_id == doctor.id)
    rows = query.group_by(Visit.status).all()
    return _status_counts(rows)


def _staff_queue_overview_message(db: Session) -> str:
    counts = _queue_status_counts(db)
    total = sum(counts.values())
    active = sum(
        count for status, count in counts.items() if status not in QUEUE_TERMINAL_STATUSES
    )
    in_progress = sum(
        counts.get(status, 0) for status in ("called", "in_service", "diagnostics")
    )
    return "\n".join(
        [
            "Queue overview",
            f"Date: {date.today().isoformat()}",
            f"Total entries: {total}",
            f"Active entries: {active}",
            f"Waiting: {counts.get('waiting', 0)}",
            f"Called/in service: {in_progress}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_next_patient_entry(db: Session) -> OnlineQueueEntry | None:
    return (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.active.is_(True),
            OnlineQueueEntry.status.in_(QUEUE_WAITING_STATUSES),
        )
        .order_by(
            OnlineQueueEntry.priority.desc(),
            func.coalesce(
                OnlineQueueEntry.queue_time, OnlineQueueEntry.created_at
            ).asc(),
            OnlineQueueEntry.id.asc(),
        )
        .first()
    )


def _staff_next_patient_message(db: Session) -> str:
    entry = _staff_next_patient_entry(db)
    if not entry:
        return "\n".join(
            [
                "Next patient",
                f"Date: {date.today().isoformat()}",
                "Waiting patients: 0",
                "Mode: read-only queue snapshot",
            ]
        )

    queue_name = _queue_entry_name(entry)
    position = _queue_entry_position(db, entry)
    details = [
        "Next patient",
        f"Date: {date.today().isoformat()}",
        f"Queue: {queue_name}",
        f"Queue number: {entry.number}",
        f"Status: {entry.status}",
    ]
    if position:
        details.append(f"Position: {position}")
    details.append("Mode: read-only queue snapshot")
    return "\n".join(details)


def _staff_today_schedule_message(db: Session, user: User | None = None) -> str:
    counts = _visit_status_counts(db, user)
    normalized_counts = {
        str(status or "unknown").lower(): count for status, count in counts.items()
    }
    total = sum(counts.values())
    in_progress = sum(
        normalized_counts.get(status, 0)
        for status in ("in_progress", "in_visit", "called")
    )
    completed = sum(
        normalized_counts.get(status, 0)
        for status in ("completed", "served", "done")
    )
    cancelled = sum(
        normalized_counts.get(status, 0)
        for status in ("cancelled", "canceled", "no_show")
    )
    open_visits = max(total - in_progress - completed - cancelled, 0)
    return "\n".join(
        [
            "Today's schedule",
            f"Date: {date.today().isoformat()}",
            f"Visits today: {total}",
            f"Open visits: {open_visits}",
            f"In progress: {in_progress}",
            f"Completed/cancelled: {completed + cancelled}",
            "Mode: read-only schedule snapshot",
        ]
    )


def _staff_emr_reminders_message(db: Session, user: User | None = None) -> str:
    counts = _visit_status_counts(db, user)
    normalized_counts = {
        str(status or "unknown").lower(): count for status, count in counts.items()
    }
    total = sum(counts.values())
    closed = sum(
        normalized_counts.get(status, 0) for status in EMR_CLOSED_VISIT_STATUSES
    )
    needs_closure = max(total - closed, 0)
    in_progress = sum(
        normalized_counts.get(status, 0)
        for status in ("in_progress", "in_visit", "called")
    )
    open_visits = max(needs_closure - in_progress, 0)
    return "\n".join(
        [
            "EMR reminders",
            f"Date: {date.today().isoformat()}",
            f"Visits needing EMR closure: {needs_closure}",
            f"Open visits: {open_visits}",
            f"In progress: {in_progress}",
            f"Closed/cancelled: {closed}",
            "Mode: read-only EMR reminder snapshot",
        ]
    )


def _staff_unpaid_invoices_message(db: Session) -> str:
    rows = _payment_invoice_status_rows(db)
    total_count = sum(count for _status, count, _amount in rows)
    unpaid_count = sum(
        count for status, count, _amount in rows if status in UNPAID_INVOICE_STATUSES
    )
    unpaid_total = sum(
        (amount for status, _count, amount in rows if status in UNPAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    return "\n".join(
        [
            "Unpaid invoices",
            f"Date: {date.today().isoformat()}",
            f"Invoices today: {total_count}",
            f"Unpaid invoices: {unpaid_count}",
            f"Unpaid total: {_format_money(unpaid_total)}",
            "Mode: read-only invoice aggregate snapshot",
        ]
    )


def _staff_paid_invoices_message(db: Session) -> str:
    rows = _payment_invoice_status_rows(db)
    total_count = sum(count for _status, count, _amount in rows)
    paid_count = sum(
        count for status, count, _amount in rows if status in PAID_INVOICE_STATUSES
    )
    paid_total = sum(
        (amount for status, _count, amount in rows if status in PAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    return "\n".join(
        [
            "Paid invoices",
            f"Date: {date.today().isoformat()}",
            f"Invoices today: {total_count}",
            f"Paid invoices: {paid_count}",
            f"Paid total: {_format_money(paid_total)}",
            "Mode: read-only invoice aggregate snapshot",
        ]
    )


def _staff_reconciliation_alerts_message(db: Session) -> str:
    result = PaymentReconciliationApiService(db).get_reconciliation_alerts(
        threshold=float(RECONCILIATION_ALERT_THRESHOLD)
    )
    alerts = result.get("alerts") or []
    severity_counts = {
        "error": sum(1 for alert in alerts if alert.get("severity") == "error"),
        "high": int(
            result.get("high_severity_count")
            or sum(1 for alert in alerts if alert.get("severity") == "high")
        ),
        "medium": sum(1 for alert in alerts if alert.get("severity") == "medium"),
    }
    providers = sorted(
        {
            str(alert.get("provider") or "unknown")
            for alert in alerts
            if alert.get("provider")
        }
    )
    provider_summary = ", ".join(providers[:3]) if providers else "none"
    if len(providers) > 3:
        provider_summary = f"{provider_summary} +{len(providers) - 3}"
    return "\n".join(
        [
            "Reconciliation alerts",
            f"Date: {date.today().isoformat()}",
            f"Alerts: {int(result.get('alert_count') or len(alerts))}",
            f"High severity: {severity_counts['high']}",
            f"Medium severity: {severity_counts['medium']}",
            f"Error severity: {severity_counts['error']}",
            f"Providers: {provider_summary}",
            "Mode: read-only reconciliation aggregate snapshot",
        ]
    )


def _staff_payment_status_message(db: Session) -> str:
    rows = _payment_status_rows(db)
    total_count = sum(count for _status, count, _amount in rows)
    paid_total = sum(
        (amount for status, _count, amount in rows if status in PAYMENT_PAID_STATUSES),
        Decimal("0"),
    )
    pending_total = sum(
        (amount for status, _count, amount in rows if status in PAYMENT_PENDING_STATUSES),
        Decimal("0"),
    )
    pending_count = sum(
        count for status, count, _amount in rows if status in PAYMENT_PENDING_STATUSES
    )
    return "\n".join(
        [
            "Payment status",
            f"Date: {date.today().isoformat()}",
            f"Payments today: {total_count}",
            f"Pending payments: {pending_count}",
            f"Paid total: {_format_money(paid_total)}",
            f"Pending total: {_format_money(pending_total)}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_lab_reports_message(db: Session) -> str:
    counts = _lab_status_counts(db)
    ready = sum(
        counts.get(status, 0)
        for status in {"READY", "FINALIZED", "PRINTED"} | LAB_REPORT_READY_STATUSES
    )
    total = sum(counts.values())
    return "\n".join(
        [
            "Lab report status",
            f"Date: {date.today().isoformat()}",
            f"Reports today: {total}",
            f"Ready reports: {ready}",
            f"Pending reports: {max(total - ready, 0)}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_pending_lab_reports_message(db: Session) -> str:
    counts = _lab_status_counts(db)
    pending = sum(
        counts.get(status, 0) for status in LAB_REPORT_PENDING_STATUSES
    )
    draft = counts.get("DRAFT", 0)
    in_progress = counts.get("IN_PROGRESS", 0)
    ready_or_done = sum(
        counts.get(status, 0)
        for status in {"READY", "FINALIZED", "PRINTED"} | LAB_REPORT_READY_STATUSES
    )
    total = sum(counts.values())
    return "\n".join(
        [
            "Pending lab reports",
            f"Date: {date.today().isoformat()}",
            f"Reports today: {total}",
            f"Pending reports: {pending}",
            f"Draft reports: {draft}",
            f"In progress: {in_progress}",
            f"Ready/final: {ready_or_done}",
            "Mode: read-only lab aggregate snapshot",
        ]
    )


def _staff_lab_delivery_status_message(db: Session) -> str:
    counts = _lab_delivery_status_counts(db)
    total = sum(counts.values())
    successful = sum(
        counts.get(status, 0) for status in SUCCESSFUL_DELIVERY_STATUSES
    )
    pending = sum(counts.get(status, 0) for status in PENDING_DELIVERY_STATUSES)
    failed = counts.get("failed", 0)
    other = max(total - successful - pending - failed, 0)
    return "\n".join(
        [
            "Lab result delivery status",
            f"Date: {date.today().isoformat()}",
            f"Telegram deliveries today: {total}",
            f"Delivered/seen/read: {successful}",
            f"Pending/dispatched: {pending}",
            f"Failed: {failed}",
            f"Other: {other}",
            "Mode: read-only delivery aggregate snapshot",
        ]
    )


def _staff_integration_errors_message(db: Session) -> str:
    counts = _integration_error_counts(db)
    total = sum(counts.values())
    return "\n".join(
        [
            "Integration errors",
            f"Date: {date.today().isoformat()}",
            f"Total attention items: {total}",
            f"Failed webhook calls today: {counts['failed_webhook_calls_today']}",
            f"Retrying webhook calls: {counts['retrying_webhook_calls']}",
            f"Unprocessed webhook events: {counts['unprocessed_webhook_events']}",
            f"Failed payment webhooks today: {counts['failed_payment_webhooks_today']}",
            "Mode: read-only integration aggregate snapshot",
        ]
    )


def _staff_daily_summary_message(db: Session) -> str:
    queue_counts = _queue_status_counts(db)
    payment_rows = _payment_status_rows(db)
    lab_counts = _lab_status_counts(db)
    visits_today = (
        db.query(func.count(Visit.id))
        .filter(Visit.visit_date == date.today())
        .scalar()
        or 0
    )
    paid_total = sum(
        (
            amount
            for status, _count, amount in payment_rows
            if status in PAYMENT_PAID_STATUSES
        ),
        Decimal("0"),
    )
    ready_reports = sum(
        lab_counts.get(status, 0)
        for status in {"READY", "FINALIZED", "PRINTED"} | LAB_REPORT_READY_STATUSES
    )
    return "\n".join(
        [
            "Daily clinic summary",
            f"Date: {date.today().isoformat()}",
            f"Visits scheduled: {int(visits_today)}",
            f"Queue entries: {sum(queue_counts.values())}",
            f"Paid today: {_format_money(paid_total)}",
            f"Ready lab reports: {ready_reports}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_readiness_message(db: Session) -> str:
    patient_bot_token = _get_configured_bot_token(db)
    token_status = _get_staff_bot_token_runtime_status(
        db, patient_bot_token=patient_bot_token
    )
    staff_status = _build_staff_bot_status(
        webhook_set=False,
        staff_bot_token_status=token_status,
    )
    readiness = staff_status.get("readiness", [])
    ready_count = sum(1 for item in readiness if item.get("ready"))
    command_contract = staff_status.get("command_registration_contract", {})
    token_contract = staff_status.get("token_contract", {})
    return "\n".join(
        [
            "Staff bot readiness",
            f"Ready gates: {ready_count}/{len(readiness)}",
            f"Dedicated token: {'ready' if token_contract.get('ready') else 'required'}",
            "Read-only menu: enabled",
            (
                "Read-only commands: ready"
                if command_contract.get("registration_enabled")
                else "Read-only commands: blocked"
            ),
            "Live data: limited read-only aggregates",
            "State-changing actions: disabled",
        ]
    )


def _staff_read_only_domain_data_message(
    db: Session, menu_item: Dict[str, Any] | None, user: User | None = None
) -> str | None:
    item_key = str((menu_item or {}).get("key") or "").strip()
    if item_key not in STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS:
        return None
    if item_key == "staff_readiness":
        return _staff_readiness_message(db)
    if item_key == "queue_overview":
        return _staff_queue_overview_message(db)
    if item_key == "next_patient":
        return _staff_next_patient_message(db)
    if item_key == "today_schedule":
        return _staff_today_schedule_message(db, user)
    if item_key == "emr_reminders":
        return _staff_emr_reminders_message(db, user)
    if item_key == "unpaid_invoices":
        return _staff_unpaid_invoices_message(db)
    if item_key == "paid_invoices":
        return _staff_paid_invoices_message(db)
    if item_key == "reconciliation_alerts":
        return _staff_reconciliation_alerts_message(db)
    if item_key == "payment_status":
        return _staff_payment_status_message(db)
    if item_key == "ready_reports":
        return _staff_lab_reports_message(db)
    if item_key == "pending_reports":
        return _staff_pending_lab_reports_message(db)
    if item_key == "delivery_status":
        return _staff_lab_delivery_status_message(db)
    if item_key == "integration_errors":
        return _staff_integration_errors_message(db)
    if item_key == "daily_summary":
        return _staff_daily_summary_message(db)
    return None


def _staff_state_change_operations_by_command() -> Dict[str, Dict[str, Any]]:
    operations: Dict[str, Dict[str, Any]] = {}
    for operation in STAFF_BOT_CONFIRMATION_CONTRACT.get("operations", []):
        for command in operation.get("telegram_commands", []):
            command_key = str(command or "").strip().lower()
            if command_key:
                operations[command_key] = operation
    return operations


def _staff_state_change_operation_for_command(
    command: str,
) -> Dict[str, Any] | None:
    return _staff_state_change_operations_by_command().get(command)


def _linked_staff_for_chat(
    db: Session, chat_id: int
) -> tuple[TelegramUser | None, User | None, Dict[str, Any] | None]:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.user_id:
        return telegram_user, None, None

    user = db.query(User).filter(User.id == telegram_user.user_id).first()
    if not user or not getattr(user, "is_active", True):
        return telegram_user, user, None

    return telegram_user, user, _staff_menu_for_role(getattr(user, "role", None))


async def _handle_staff_read_only_menu(
    update: Dict[str, Any], db: Session, bot_service
) -> bool:
    message = _message_from_update(update)
    if not message:
        return False

    chat_id = _message_chat_id(message)
    if chat_id is None:
        return False

    update_id = update.get("update_id")
    request_id = f"telegram-update:{update_id}" if update_id is not None else None
    text = _message_text(message)
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    normalized_text = text.lower()
    read_only_commands = _staff_read_only_commands()
    state_change_operation = _staff_state_change_operation_for_command(command)
    staff_menu_requested = (
        command in read_only_commands
        or command == "/start"
        or command == "/menu"
        or state_change_operation is not None
        or normalized_text in _staff_read_only_item_labels()
    )
    if not staff_menu_requested:
        return False

    _telegram_user, user, role_menu = _linked_staff_for_chat(db, chat_id)
    if not user:
        if command in {"/staff", "/menu"}:
            _record_staff_command_audit(
                db,
                chat_id=chat_id,
                request_id=request_id,
                actor_user_id=None,
                telegram_user_id=getattr(_telegram_user, "id", None),
                role="unlinked",
                command_key=command,
                result="denied",
                reason="staff_not_linked",
            )
            db.commit()
            await bot_service._send_message(
                chat_id,
                TELEGRAM_STAFF_MENU_UNLINKED_MESSAGE,
                TELEGRAM_STAFF_LINK_REPLY_MARKUP,
            )
            return True
        return False

    if not role_menu:
        if user:
            _record_staff_command_audit(
                db,
                chat_id=chat_id,
                request_id=request_id,
                actor_user_id=int(user.id),
                telegram_user_id=getattr(_telegram_user, "id", None),
                role=_normalize_staff_role(getattr(user, "role", None)),
                command_key=command if command.startswith("/") else "staff_menu_item",
                result="denied",
                reason="role_not_allowed",
            )
            db.commit()
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE,
            TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        return True

    menu = _staff_menu_keyboard(role_menu)
    role = _normalize_staff_role(getattr(user, "role", None))
    if state_change_operation is not None:
        operation_key = str(state_change_operation.get("key") or "staff_action")
        allowed_roles = {
            _normalize_staff_role(role_key)
            for role_key in state_change_operation.get("roles", [])
        }
        reason = (
            "telegram_state_changes_disabled"
            if role in allowed_roles
            else "role_not_allowed"
        )
        _record_staff_action_denied_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=role,
            operation_key=operation_key,
            command_key=command,
            reason=reason,
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            (
                TELEGRAM_STAFF_ACTION_DENIED_MESSAGE
                if role in allowed_roles
                else TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE
            ),
            menu,
        )
        return True

    if command in {"/start", "/staff", "/help", "/menu"}:
        _record_staff_command_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=_normalize_staff_role(getattr(user, "role", None)),
            command_key=command,
            menu_item_key="staff_menu",
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            _staff_menu_message(user, role_menu),
            menu,
        )
        return True

    menu_item = _staff_menu_item_for_text(role_menu, text)
    if not menu_item and command in read_only_commands:
        menu_item = _staff_menu_item_for_command(role_menu, command)

    command_key = command if command in read_only_commands else "staff_menu_item"
    if command in read_only_commands and not menu_item:
        _record_staff_command_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=_normalize_staff_role(getattr(user, "role", None)),
            command_key=command_key,
            result="denied",
            reason="role_not_allowed",
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE,
            menu,
        )
        return True

    domain_data_message = _staff_read_only_domain_data_message(db, menu_item, user)
    _record_staff_command_audit(
        db,
        chat_id=chat_id,
        request_id=request_id,
        actor_user_id=int(user.id),
        telegram_user_id=getattr(_telegram_user, "id", None),
        role=_normalize_staff_role(getattr(user, "role", None)),
        command_key=command_key,
        menu_item_key=str(menu_item.get("key")) if menu_item else None,
    )
    db.commit()
    await bot_service._send_message(
        chat_id,
        domain_data_message or TELEGRAM_STAFF_MENU_PLACEHOLDER_MESSAGE,
        menu,
    )
    return True


async def _handle_ticket_qr_start(update: Dict[str, Any], db: Session, bot_service) -> bool:
    extracted = _extract_ticket_qr_start_payload(update)
    if not extracted:
        return False

    token, message = extracted
    chat_id = (message.get("chat") or {}).get("id")
    visit = consume_telegram_ticket_start_token(db, token)
    if visit:
        if chat_id is None:
            db.rollback()
            return True

        try:
            _upsert_ticket_qr_telegram_user(db, message, visit.patient_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Telegram ticket QR user link failed error_type=%s",
                type(exc).__name__,
            )
            language = _normalize_patient_language(
                (message.get("from") or {}).get("language_code")
            )
            await bot_service._send_message(
                int(chat_id),
                _localized_text("ticket_qr_link_failed", language),
                _localized_main_menu(language),
            )
            return True

        await bot_service._send_message(
            int(chat_id),
            _telegram_chat_text(db, int(chat_id), "ticket_qr_linked"),
            _telegram_chat_menu(db, int(chat_id)),
        )
    elif chat_id is not None:
        language = _telegram_chat_language(db, int(chat_id))
        await bot_service._send_message(
            int(chat_id),
            _localized_text("ticket_qr_expired", language),
            _localized_main_menu(language),
        )

    return True


async def _handle_staff_link_start(
    update: Dict[str, Any], db: Session, bot_service
) -> bool:
    extracted = _extract_staff_link_start_payload(update)
    if not extracted:
        return False

    token, message = extracted
    chat_id = _message_chat_id(message)
    if chat_id is None:
        return True

    update_id = update.get("update_id")
    request_id = f"telegram-update:{update_id}" if update_id is not None else None

    try:
        validation = validate_staff_link_start_token(
            db, token, telegram_chat_id=chat_id
        )
        if not validation.get("valid"):
            logger.info(
                "Telegram staff link token rejected reason=%s",
                validation.get("reason"),
            )
            _record_staff_link_audit(
                db,
                action="staff_link_token_rejected",
                chat_id=chat_id,
                request_id=request_id,
                reason=str(validation.get("reason") or "invalid"),
            )
            db.commit()
            await bot_service._send_message(
                chat_id,
                TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
                TELEGRAM_STAFF_LINK_REPLY_MARKUP,
            )
            return True

        linked_user = _upsert_staff_link_telegram_user(
            db,
            message,
            linked_user_id=int(validation["user_id"]),
        )
        if not linked_user:
            logger.warning("Telegram staff link failed because chat row was missing")
            await bot_service._send_message(
                chat_id,
                TELEGRAM_STAFF_LINK_FAILED_MESSAGE,
                TELEGRAM_STAFF_LINK_REPLY_MARKUP,
            )
            return True

        role = validation.get("role") or "staff"
        _record_staff_link_audit(
            db,
            action="staff_link_created",
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(validation["user_id"]),
            telegram_user_id=getattr(linked_user, "id", None),
            role=str(role),
        )
        db.commit()
        logger.info("Telegram staff link created role=%s", role)
        role_menu = _staff_menu_for_role(role)
        reply_markup = (
            _staff_menu_keyboard(role_menu)
            if role_menu
            else TELEGRAM_STAFF_LINK_REPLY_MARKUP
        )
        await bot_service._send_message(
            chat_id,
            f"{TELEGRAM_STAFF_LINKED_MESSAGE}\nРоль: {role}",
            reply_markup,
        )
        return True
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram staff link handler failed error_type=%s",
            type(exc).__name__,
        )
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_LINK_FAILED_MESSAGE,
            TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        return True

def _message_from_update(update: Dict[str, Any]) -> Dict[str, Any]:
    return update.get("message") or {}


def _message_chat_id(message: Dict[str, Any]) -> int | None:
    chat_id = (message.get("chat") or {}).get("id")
    return int(chat_id) if chat_id is not None else None


def _message_text(message: Dict[str, Any]) -> str:
    return str(message.get("text") or "").strip()


def _find_patient_by_phone(db: Session, phone: str) -> Patient | None:
    normalized_phone = normalize_phone_uz(phone)
    if not normalized_phone:
        return None

    patient_info = crud_telegram.find_patient_by_phone(db, normalized_phone)
    patient_id = patient_info.get("id") if patient_info else None
    if not patient_id:
        return None

    return db.query(Patient).filter(Patient.id == int(patient_id)).first()


def _patient_display_name(patient: Patient | None) -> str:
    if not patient:
        return "пациент"
    return patient.short_name()


def _recent_visit_summary(
    db: Session, patient_id: int, language_code: str = TELEGRAM_LANGUAGE_RU
) -> str:
    visit = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .first()
    )
    if not visit:
        return _localized_text("recent_visit_none", language_code)

    visit_date = (
        visit.visit_date.isoformat()
        if visit.visit_date
        else _localized_text("recent_visit_unknown_date", language_code)
    )
    return _localized_text("recent_visit_summary", language_code).format(
        visit_id=visit.id,
        visit_date=visit_date,
        status=visit.status,
    )


def _html_text(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _money_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _format_money(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral_value():
        return f"{int(normalized):,}".replace(",", " ")
    return f"{normalized:,.2f}".replace(",", " ")


def _telegram_user_for_chat(db: Session, chat_id: int) -> TelegramUser | None:
    return crud_telegram.get_telegram_user_by_chat_id(db, chat_id)


def _patient_for_telegram_chat(
    db: Session, chat_id: int
) -> tuple[TelegramUser | None, Patient | None]:
    telegram_user = _telegram_user_for_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return telegram_user, None
    patient = db.query(Patient).filter(Patient.id == telegram_user.patient_id).first()
    return telegram_user, patient


def _patient_today_queue_entries(db: Session, patient_id: int) -> list[OnlineQueueEntry]:
    return (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            OnlineQueueEntry.patient_id == patient_id,
            DailyQueue.day == date.today(),
            ~OnlineQueueEntry.status.in_(QUEUE_TERMINAL_STATUSES),
        )
        .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())
        .all()
    )


def _queue_entry_position(db: Session, entry: OnlineQueueEntry) -> int | None:
    if entry.status not in QUEUE_WAITING_STATUSES:
        return None

    waiting_entries = (
        db.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.status.in_(QUEUE_WAITING_STATUSES),
        )
        .order_by(
            OnlineQueueEntry.priority.desc(),
            OnlineQueueEntry.queue_time.asc(),
            OnlineQueueEntry.id.asc(),
        )
        .all()
    )
    for position, waiting_entry in enumerate(waiting_entries, start=1):
        if waiting_entry.id == entry.id:
            return position
    return None


def _queue_entry_name(
    entry: OnlineQueueEntry, language_code: str = TELEGRAM_LANGUAGE_RU
) -> str:
    queue = getattr(entry, "queue", None)
    queue_tag = getattr(queue, "queue_tag", None)
    if queue_tag:
        language = _normalize_patient_language(language_code)
        labels = QUEUE_TAG_LABELS_BY_LANGUAGE.get(language, QUEUE_TAG_LABELS)
        return labels.get(queue_tag) or QUEUE_TAG_LABELS.get(queue_tag, queue_tag)

    services = entry.services or []
    if services:
        first_service = services[0] or {}
        return str(
            first_service.get("name")
            or first_service.get("title")
            or _localized_text("queue_default_name", language_code)
        )
    return _localized_text("queue_default_name", language_code)


def _queue_status_label(status: str, language_code: str = TELEGRAM_LANGUAGE_RU) -> str:
    language = _normalize_patient_language(language_code)
    labels = QUEUE_STATUS_LABELS_BY_LANGUAGE.get(language, QUEUE_STATUS_LABELS)
    return labels.get(status) or QUEUE_STATUS_LABELS.get(status, status)


def _queue_entry_cabinet(
    entry: OnlineQueueEntry, language_code: str = TELEGRAM_LANGUAGE_RU
) -> str | None:
    queue = getattr(entry, "queue", None)
    cabinet_number = getattr(queue, "cabinet_number", None)
    if not cabinet_number:
        return None
    return _localized_text("queue_cabinet", language_code).format(
        cabinet=_html_text(cabinet_number)
    )


def _clinic_queue_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "needs_link")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    entries = _patient_today_queue_entries(db, telegram_user.patient_id)
    if not entries:
        return _localized_text("queue_empty", language).format(
            patient=patient_name,
            visit_summary=_html_text(
                _recent_visit_summary(db, telegram_user.patient_id, language)
            ),
        )

    lines = [
        _localized_text("queue_patient", language).format(patient=patient_name),
        _localized_text("queue_title", language),
    ]
    for entry in entries[:5]:
        status_label = _queue_status_label(entry.status, language)
        position = _queue_entry_position(db, entry)
        cabinet = _queue_entry_cabinet(entry, language)
        details = [
            f"№{entry.number}",
            _html_text(_queue_entry_name(entry, language)),
            _localized_text("queue_status", language).format(
                status=_html_text(status_label)
            ),
        ]
        if position:
            details.append(
                _localized_text("queue_position", language).format(position=position)
            )
        if cabinet:
            details.append(cabinet)
        lines.append(" • ".join(details))

    if len(entries) > 5:
        lines.append(
            _localized_text("queue_more", language).format(count=len(entries) - 5)
        )
    return "\n".join(lines)


def _visit_services_total(visit: Visit) -> Decimal:
    total = Decimal("0")
    for service in getattr(visit, "services", []) or []:
        total += _money_decimal(getattr(service, "price", None)) * _money_decimal(
            getattr(service, "qty", 1) or 1
        )
    return total


def _patient_relevant_visits(
    db: Session, patient_id: int, entries: list[OnlineQueueEntry]
) -> list[Visit]:
    visit_ids = sorted({int(entry.visit_id) for entry in entries if entry.visit_id})
    if visit_ids:
        return (
            db.query(Visit)
            .filter(Visit.patient_id == patient_id, Visit.id.in_(visit_ids))
            .order_by(Visit.created_at.desc(), Visit.id.desc())
            .all()
        )

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id, Visit.visit_date == date.today())
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .limit(3)
        .all()
    )
    if visits:
        return visits

    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id, Visit.status == "open")
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .limit(3)
        .all()
    )


def _payment_total_for_visits(
    db: Session, visit_ids: list[int], statuses: set[str]
) -> Decimal:
    if not visit_ids:
        return Decimal("0")

    total = Decimal("0")
    status_values = tuple(statuses)
    junction_visit_ids: set[int] = set()
    junction_rows = (
        db.query(PaymentVisit.visit_id, PaymentVisit.amount)
        .join(Payment, Payment.id == PaymentVisit.payment_id)
        .filter(
            PaymentVisit.visit_id.in_(visit_ids),
            Payment.status.in_(status_values),
        )
        .all()
    )
    for visit_id, amount in junction_rows:
        junction_visit_ids.add(int(visit_id))
        total += _money_decimal(amount)

    direct_payments = (
        db.query(Payment)
        .filter(Payment.visit_id.in_(visit_ids), Payment.status.in_(status_values))
        .all()
    )
    for payment in direct_payments:
        if int(payment.visit_id) in junction_visit_ids:
            continue
        total += _money_decimal(payment.amount)

    return total


def _billing_totals(
    db: Session, patient_id: int
) -> tuple[list[OnlineQueueEntry], list[Visit], Decimal, Decimal, Decimal, Decimal]:
    entries = _patient_today_queue_entries(db, patient_id)
    visits = _patient_relevant_visits(db, patient_id, entries)
    visits_by_id = {visit.id: visit for visit in visits}
    entry_total_by_visit: dict[int, Decimal] = {}
    unlinked_entry_total = Decimal("0")

    for entry in entries:
        entry_total = _money_decimal(entry.total_amount)
        if entry.visit_id:
            current = entry_total_by_visit.get(int(entry.visit_id), Decimal("0"))
            entry_total_by_visit[int(entry.visit_id)] = max(current, entry_total)
        else:
            unlinked_entry_total += entry_total

    expected_total = unlinked_entry_total
    for visit in visits:
        queue_total = entry_total_by_visit.get(visit.id, Decimal("0"))
        expected_total += queue_total if queue_total > 0 else _visit_services_total(visit)

    visit_ids = sorted(visits_by_id)
    paid_total = _payment_total_for_visits(db, visit_ids, PAYMENT_PAID_STATUSES)
    pending_total = _payment_total_for_visits(db, visit_ids, PAYMENT_PENDING_STATUSES)
    debt_total = max(expected_total - paid_total, Decimal("0"))
    return entries, visits, expected_total, paid_total, pending_total, debt_total


def _clinic_payments_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "needs_link")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    entries, visits, expected_total, paid_total, pending_total, debt_total = _billing_totals(
        db, telegram_user.patient_id
    )
    if not entries and not visits and expected_total <= 0 and paid_total <= 0:
        return _localized_text("payments_empty", language).format(patient=patient_name)

    lines = [
        _localized_text("payments_patient", language).format(patient=patient_name),
        _localized_text("payments_title", language),
        _localized_text("payments_billed", language).format(
            amount=_format_money(expected_total)
        ),
        _localized_text("payments_paid", language).format(
            amount=_format_money(paid_total)
        ),
        _localized_text("payments_debt", language).format(
            amount=_format_money(debt_total)
        ),
    ]
    if pending_total > 0:
        lines.append(
            _localized_text("payments_pending", language).format(
                amount=_format_money(pending_total)
            )
        )
    if visits:
        visit_numbers = ", ".join(f"#{visit.id}" for visit in visits[:5])
        lines.append(
            _localized_text("payments_visits", language).format(visits=visit_numbers)
        )
    lines.append(_localized_text("payments_online_unavailable", language))
    return "\n".join(lines)


def _latest_ready_lab_report_instances(
    db: Session, patient_id: int, limit: int = MAX_TELEGRAM_LAB_REPORTS
) -> list[LabReportInstance]:
    return (
        db.query(LabReportInstance)
        .filter(
            LabReportInstance.patient_id == patient_id,
            LabReportInstance.status.in_(LAB_REPORT_READY_STATUSES),
        )
        .order_by(LabReportInstance.created_at.desc(), LabReportInstance.id.desc())
        .limit(limit)
        .all()
    )


def _lab_report_document_caption(
    instance: LabReportInstance,
    report_date: datetime,
    language_code: str = TELEGRAM_LANGUAGE_RU,
) -> str:
    caption = _localized_text("lab_result_document_caption", language_code).format(
        template_name=_html_text(instance.template.name),
        report_id=instance.id,
        report_date=report_date.strftime("%d.%m.%Y"),
    )
    if len(caption) > 1000:
        return f"{caption[:997]}..."
    return caption


def _build_lab_report_pdf(db: Session, instance: LabReportInstance) -> tuple[str, bytes, str]:
    service = LabReportingService(db)
    materialized_sections = service.materialize_instance(instance)
    critical_findings = service.summarize_critical_findings(materialized_sections)
    report_date = instance.finalized_at or instance.created_at or datetime.utcnow()
    pdf_bytes = lab_report_pdf_service.render_report(
        {
            "template_name": instance.template.name,
            "layout_preset": instance.template_version.layout_preset,
            "page_settings": instance.template_version.page_settings or {},
            "branding": instance.branding_snapshot or {},
            "patient": instance.patient_snapshot or {},
            "signers": instance.signer_snapshot or {},
            "sections": materialized_sections,
            "critical_findings": critical_findings,
            "footer_notes": instance.template_version.footer_notes,
            "report_date": report_date.strftime("%d.%m.%Y"),
        }
    )
    filename = f"kosmed-lab-report-{instance.id}.pdf"
    caption = _lab_report_document_caption(
        instance, report_date, TELEGRAM_LANGUAGE_RU
    )
    return filename, pdf_bytes, caption


def _log_lab_report_document_send(
    db: Session,
    chat_id: int,
    instance_id: int,
    caption: str,
    status_value: str,
    message_id: int | None = None,
    error_message: str | None = None,
) -> None:
    try:
        db.add(
            TelegramMessage(
                chat_id=chat_id,
                message_id=message_id,
                message_type="lab_result_pdf",
                template_key="telegram_lab_result_pdf",
                message_text=caption,
                status=status_value,
                error_message=error_message,
                related_entity_type="lab_report_instance",
                related_entity_id=instance_id,
                sent_at=datetime.utcnow() if status_value == "sent" else None,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram lab report document log failed error_type=%s",
            type(exc).__name__,
        )


async def _send_clinic_lab_results(db: Session, bot_service, chat_id: int) -> None:
    telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
    language = _telegram_chat_language(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        await bot_service._send_message(
            chat_id,
            _telegram_chat_text(db, chat_id, "needs_link"),
            _telegram_chat_menu(db, chat_id),
        )
        return

    instances = _latest_ready_lab_report_instances(db, telegram_user.patient_id)
    if not instances:
        await bot_service._send_message(
            chat_id,
            _localized_text("lab_results_empty", language),
            _telegram_chat_menu(db, chat_id),
        )
        return

    await bot_service._send_message(
        chat_id,
        _localized_text("lab_results_found", language).format(count=len(instances)),
        _telegram_chat_menu(db, chat_id),
    )
    sent_count = 0
    for instance in instances:
        try:
            filename, pdf_bytes, caption = _build_lab_report_pdf(db, instance)
            if language == TELEGRAM_LANGUAGE_UZ:
                report_date = (
                    instance.finalized_at or instance.created_at or datetime.utcnow()
                )
                caption = _lab_report_document_caption(instance, report_date, language)
            send_document = getattr(bot_service, "_send_document", None)
            if callable(send_document):
                ok, message_id, error_message = await send_document(
                    chat_id,
                    filename,
                    pdf_bytes,
                    caption,
                )
            else:
                logger.error("Telegram bot service does not support document send")
                ok, message_id, error_message = False, None, "send_document_not_supported"
            _log_lab_report_document_send(
                db,
                chat_id,
                instance.id,
                caption,
                "sent" if ok else "failed",
                message_id=message_id,
                error_message=error_message,
            )
            if ok:
                sent_count += 1
        except Exception as exc:
            logger.warning(
                "Telegram lab report PDF send failed instance_id=%s error_type=%s",
                instance.id,
                type(exc).__name__,
            )
            _log_lab_report_document_send(
                db,
                chat_id,
                instance.id,
                _localized_text(
                    "lab_result_document_failed_caption", language
                ).format(report_id=instance.id),
                "failed",
                error_message=type(exc).__name__,
            )

    if sent_count == 0:
        await bot_service._send_message(
            chat_id,
            _localized_text("lab_results_send_failed", language),
            _telegram_chat_menu(db, chat_id),
        )


def _clinic_status_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "needs_link")

    language = _telegram_chat_language(db, chat_id)
    return _localized_text("profile_linked", language).format(
        patient=_html_text(_patient_display_name(patient)),
        visit_summary=_html_text(
            _recent_visit_summary(db, telegram_user.patient_id, language)
        ),
    )


def _clinic_results_message(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "needs_link")

    return _telegram_chat_text(db, chat_id, "results_hint")


async def _send_language_choice(bot_service, chat_id: int) -> None:
    await bot_service._send_message(
        chat_id,
        _localized_text("language_prompt", TELEGRAM_LANGUAGE_RU),
        TELEGRAM_LANGUAGE_MENU,
    )


async def _send_clinic_welcome(
    bot_service, chat_id: int, language_code: str = TELEGRAM_LANGUAGE_RU
) -> None:
    await bot_service._send_message(
        chat_id,
        _localized_text("welcome", language_code),
        _localized_main_menu(language_code),
    )


async def _send_notification_consent(
    bot_service, chat_id: int, language_code: str = TELEGRAM_LANGUAGE_RU
) -> None:
    await bot_service._send_message(
        chat_id,
        _localized_text("notification_consent", language_code),
        _localized_notification_consent_menu(language_code),
    )


async def _set_notification_consent(
    db: Session, bot_service, chat_id: int, enabled: bool
) -> None:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    language = _normalize_patient_language(getattr(telegram_user, "language_code", None))
    if telegram_user:
        telegram_user.notifications_enabled = enabled
        telegram_user.appointment_reminders = enabled
        telegram_user.lab_notifications = enabled
        telegram_user.last_activity = datetime.utcnow()
        db.commit()

    result_key = "notifications_enabled" if enabled else "notifications_disabled"
    await bot_service._send_message(
        chat_id,
        _localized_text(result_key, language),
        _localized_main_menu(language),
    )


async def _handle_contact_link(
    message: Dict[str, Any], db: Session, bot_service
) -> bool:
    contact = message.get("contact")
    if not contact:
        return False

    chat_id = _message_chat_id(message)
    from_user_id = (message.get("from") or {}).get("id")
    contact_user_id = contact.get("user_id")
    if chat_id is None:
        return True

    if from_user_id is None or contact_user_id != from_user_id:
        await bot_service._send_message(
            chat_id,
            _telegram_chat_text(db, chat_id, "contact_rejected"),
            _telegram_chat_menu(db, chat_id),
        )
        return True

    patient = _find_patient_by_phone(db, str(contact.get("phone_number") or ""))
    if not patient:
        await bot_service._send_message(
            chat_id,
            _telegram_chat_text(db, chat_id, "patient_not_found"),
            _telegram_chat_menu(db, chat_id),
        )
        return True

    try:
        _upsert_ticket_qr_telegram_user(db, message, patient.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram contact link failed error_type=%s",
            type(exc).__name__,
        )
        await bot_service._send_message(
            chat_id,
            _telegram_chat_text(db, chat_id, "ticket_qr_link_failed"),
            _telegram_chat_menu(db, chat_id),
        )
        return True

    language = _telegram_chat_language(db, chat_id)
    patient_label = "Bemor" if language == TELEGRAM_LANGUAGE_UZ else "Пациент"
    await bot_service._send_message(
        chat_id,
        f"{_localized_text('contact_linked', language)}\n{patient_label}: {_patient_display_name(patient)}",
        _localized_main_menu(language),
    )
    return True


async def _handle_clinic_bot_update(
    update: Dict[str, Any], db: Session, bot_service
) -> bool:
    async def start_handler(chat_id: int, message: Dict[str, Any]) -> None:
        _upsert_ticket_qr_telegram_user(db, message)
        db.commit()
        await _send_language_choice(bot_service, chat_id)

    async def language_handler(chat_id: int, language_code: str) -> None:
        message = _message_from_update(update)
        _upsert_ticket_qr_telegram_user(
            db,
            message,
            language_code=language_code,
            notifications_enabled=False,
        )
        db.commit()
        logger.info(
            "Telegram patient bot language selected",
            extra={"language_code": _normalize_patient_language(language_code)},
        )
        await _send_notification_consent(bot_service, chat_id, language_code)

    async def help_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await bot_service._send_message(
            chat_id,
            _localized_text("help", language),
            _localized_main_menu(language),
        )

    async def settings_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await bot_service._send_message(
            chat_id,
            _localized_text("settings", language),
            _localized_settings_menu(language),
        )

    async def queue_handler(chat_id: int) -> None:
        await bot_service._send_message(
            chat_id, _clinic_queue_message(db, chat_id), _telegram_chat_menu(db, chat_id)
        )

    async def payments_handler(chat_id: int) -> None:
        await bot_service._send_message(
            chat_id, _clinic_payments_message(db, chat_id), _telegram_chat_menu(db, chat_id)
        )

    async def profile_handler(chat_id: int) -> None:
        await bot_service._send_message(
            chat_id, _clinic_status_message(db, chat_id), _telegram_chat_menu(db, chat_id)
        )

    async def results_handler(chat_id: int) -> None:
        await _send_clinic_lab_results(db, bot_service, chat_id)

    async def share_contact_handler(chat_id: int) -> None:
        await bot_service._send_message(
            chat_id,
            _telegram_chat_text(db, chat_id, "share_contact"),
            _telegram_chat_menu(db, chat_id),
        )

    async def enable_notifications_handler(chat_id: int) -> None:
        await _set_notification_consent(db, bot_service, chat_id, True)

    async def disable_notifications_handler(chat_id: int) -> None:
        await _set_notification_consent(db, bot_service, chat_id, False)

    async def russian_language_handler(chat_id: int) -> None:
        await language_handler(chat_id, TELEGRAM_LANGUAGE_RU)

    async def uzbek_language_handler(chat_id: int) -> None:
        await language_handler(chat_id, TELEGRAM_LANGUAGE_UZ)

    command_handlers = {
        "/help": help_handler,
        "/queue": queue_handler,
        "/payments": payments_handler,
        "/profile": profile_handler,
        "/results": results_handler,
        "/settings": settings_handler,
    }
    text_handlers = {
        "помощь": help_handler,
        "настройки": settings_handler,
        "моя очередь": queue_handler,
        "оплаты и долг": payments_handler,
        "мой статус": profile_handler,
        "результаты": results_handler,
        "поделиться номером": share_contact_handler,
        "русский": russian_language_handler,
        "o'zbekcha": uzbek_language_handler,
        "ozbekcha": uzbek_language_handler,
        "uzbekcha": uzbek_language_handler,
        "разрешить уведомления": enable_notifications_handler,
        "без уведомлений": disable_notifications_handler,
        "xabarnomalarga roziman": enable_notifications_handler,
        "xabarnomasiz": disable_notifications_handler,
        "yordam": help_handler,
        "sozlamalar": settings_handler,
        "mening navbatim": queue_handler,
        "to'lovlar va qarz": payments_handler,
        "mening holatim": profile_handler,
        "natijalar": results_handler,
        "telefon raqamni ulashish": share_contact_handler,
    }

    dispatch = getattr(bot_service, "process_patient_bot_update", None)
    if callable(dispatch):
        return await dispatch(
            update,
            db,
            staff_start_handler=_handle_staff_link_start,
            staff_menu_handler=_handle_staff_read_only_menu,
            ticket_start_handler=_handle_ticket_qr_start,
            contact_handler=_handle_contact_link,
            start_handler=start_handler,
            command_handlers=command_handlers,
            text_handlers=text_handlers,
        )

    if await _handle_staff_link_start(update, db, bot_service):
        return True

    if await _handle_staff_read_only_menu(update, db, bot_service):
        return True

    if await _handle_ticket_qr_start(update, db, bot_service):
        return True

    message = _message_from_update(update)
    if not message:
        return False

    chat_id = _message_chat_id(message)
    if chat_id is None:
        return False

    if await _handle_contact_link(message, db, bot_service):
        return True

    text = _message_text(message)
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    handler = command_handlers.get(command) or text_handlers.get(text.lower())
    if command == "/start":
        await start_handler(chat_id, message)
        return True
    if handler:
        await handler(chat_id)
        return True
    return False


def _validate_webhook_secret(request: Request, db: Session) -> None:
    config = crud_telegram.get_telegram_config(db)
    expected_secret = getattr(config, "webhook_secret", None)
    if not expected_secret:
        logger.error("Telegram webhook rejected because webhook secret is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook secret is not configured",
        )

    received_secret = request.headers.get(WEBHOOK_SECRET_HEADER)
    if received_secret != expected_secret:
        logger.warning("Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )


def _raise_telegram_webhook_internal_error(
    operation: str, public_detail: str, exc: Exception
) -> NoReturn:
    logger.warning(
        "Telegram webhook endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=public_detail,
    ) from exc


def _telegram_bot_info_failure(exc: Exception) -> Dict[str, Any]:
    logger.warning(
        "Telegram webhook endpoint failed operation=get_bot_info error_type=%s",
        type(exc).__name__,
    )
    return {"active": False, "message": TELEGRAM_BOT_INFO_PUBLIC_MESSAGE}


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any], request: Request, db: Session = Depends(get_db)
):
    """
    Webhook endpoint для получения обновлений от Telegram
    """
    try:
        _validate_webhook_secret(request, db)
        logger.info(
            "Telegram webhook update accepted",
            extra=_telegram_update_summary(update),
        )

        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()

        # Инициализируем бота если нужно
        if not bot_service.active:
            await bot_service.initialize(db)

        # Обрабатываем обновление
        if await _handle_clinic_bot_update(update, db, bot_service):
            return {"status": "ok", "handled": "clinic_bot_update"}

        await bot_service.process_webhook_update(update, db)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        _raise_telegram_webhook_internal_error(
            "telegram_webhook",
            TELEGRAM_WEBHOOK_PUBLIC_ERROR,
            e,
        )


@router.get("/webhook")
async def verify_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Проверка webhook (для верификации)
    """
    try:
        # Telegram может отправлять GET запросы для проверки webhook
        return {"status": "webhook_verified"}

    except HTTPException:
        raise
    except Exception as e:
        _raise_telegram_webhook_internal_error(
            "verify_webhook",
            "Ошибка проверки webhook",
            e,
        )


@router.post("/send-message")
async def send_message_to_user(
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    reply_markup: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Отправка сообщения пользователю через бота
    """
    try:
        bot_service = await get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        success = await bot_service._send_message(
            chat_id=chat_id, text=message, reply_markup=reply_markup
        )

        if success:
            return {"status": "sent", "chat_id": chat_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка отправки сообщения",
            )

    except HTTPException:
        raise
    except Exception as e:
        _raise_telegram_webhook_internal_error(
            "send_message_to_user",
            TELEGRAM_SEND_PUBLIC_ERROR,
            e,
        )


@router.get("/bot-info", operation_id="telegram_webhook_get_bot_info")
async def get_bot_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить информацию о боте
    """
    try:
        bot_service = await get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        if not bot_service.bot_token:
            return {"active": False, "message": "Бот не настроен"}

        # Получаем информацию о боте через API
        import requests

        response = requests.get(
            f"https://api.telegram.org/bot{bot_service.bot_token}/getMe", timeout=10
        )

        if response.status_code == 200:
            bot_data = response.json()
            if bot_data.get("ok"):
                return {
                    "active": True,
                    "bot_info": bot_data["result"],
                    "webhook_url": bot_service.webhook_url,
                }

        return {"active": False, "message": "Ошибка получения информации о боте"}

    except HTTPException:
        raise
    except Exception as e:
        return _telegram_bot_info_failure(e)
