"""
Webhook endpoint для обработки входящих сообщений от Telegram
"""

import hashlib
import hmac
import html
import ipaddress
import logging
import secrets
import socket
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, NoReturn
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.v1.endpoints.admin_telegram import (
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
from app.core.config import settings
from app.crud import audit as crud_audit
from app.crud import telegram_config as crud_telegram
from app.crud.appointment import appointment as appointment_crud
from app.db.session import get_db
from app.models.appointment import Appointment
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
from app.schemas import appointment as appointment_schemas
from app.schemas.patient_onboarding import (
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
from app.services.lab_report_pdf_service import lab_report_pdf_service
from app.services.lab_reporting_service import LabReportingService
from app.services.patient_onboarding_service import PatientOnboardingService
from app.services.payment_reconciliation_api_service import (
    PaymentReconciliationApiService,
)
from app.services.telegram_bot import (
    get_telegram_bot_service,
    telegram_text_corruption_reason,
)
from app.services.telegram_mini_app_init_data import (
    TelegramMiniAppInitDataError,
    TelegramMiniAppSessionScope,
    TelegramMiniAppSessionScopeError,
    build_telegram_mini_app_appointment_booking_preview,
    build_telegram_mini_app_patient_forms_preview,
    resolve_telegram_mini_app_session_scope,
    save_telegram_mini_app_patient_form_submission,
    validate_telegram_mini_app_init_data,
)
from app.services.telegram_staff_confirmation_token_service import (
    TelegramStaffConfirmationTokenService,
)
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


def _build_patient_mini_app_entry_token(chat_id: int, section: str) -> str:
    expires_at = datetime.utcnow() + timedelta(
        seconds=PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS
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
    expires_at = datetime.utcnow() + timedelta(
        seconds=PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS
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


async def _send_patient_bot_reply(
    db: Session,
    bot_service,
    chat_id: int,
    text: str,
    reply_markup: dict[str, Any],
    template_key: str,
) -> bool:
    corruption_reason = telegram_text_corruption_reason(text)
    if corruption_reason:
        try:
            db.add(
                TelegramMessage(
                    chat_id=chat_id,
                    message_type="patient_bot_reply",
                    template_key=template_key,
                    message_text="[blocked_corrupted_text]",
                    status="failed",
                    error_message=f"blocked_corrupted_text:{corruption_reason}",
                )
            )
            db.commit()
            logger.warning(
                "Telegram patient bot reply blocked template_key=%s reason=%s",
                template_key,
                corruption_reason,
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Telegram patient bot reply block log failed template_key=%s error_type=%s",
                template_key,
                type(exc).__name__,
            )
        return False

    sent = bool(await bot_service._send_message(chat_id, text, reply_markup))
    try:
        db.add(
            TelegramMessage(
                chat_id=chat_id,
                message_type="patient_bot_reply",
                template_key=template_key,
                message_text=str(text or ""),
                status="sent" if sent else "failed",
                sent_at=datetime.utcnow() if sent else None,
            )
        )
        db.commit()
        logger.info(
            "Telegram patient bot reply recorded template_key=%s status=%s",
            template_key,
            "sent" if sent else "failed",
        )
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram patient bot reply log failed template_key=%s error_type=%s",
            template_key,
            type(exc).__name__,
        )
    return sent


def _latest_patient_bot_template_key(db: Session, chat_id: int) -> str | None:
    row = (
        db.query(TelegramMessage.template_key)
        .filter(
            TelegramMessage.chat_id == chat_id,
            TelegramMessage.message_type == "patient_bot_reply",
        )
        .order_by(TelegramMessage.id.desc())
        .first()
    )
    return str(row[0]) if row and row[0] else None


def _is_patient_settings_context_template(template_key: str | None) -> bool:
    return template_key in {
        "telegram_patient_settings",
        "telegram_patient_settings_language_selected",
        "telegram_patient_settings_notifications_enabled",
        "telegram_patient_settings_notifications_disabled",
    }


def _upsert_ticket_qr_telegram_user(
    db: Session,
    message: dict[str, Any],
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

    create_notifications_enabled = payload.pop("notifications_enabled", False)
    create_appointment_reminders = payload.pop("appointment_reminders", False)
    create_lab_notifications = payload.pop("lab_notifications", False)
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
    digest = hashlib.sha256(f"staff-telegram-chat:{chat_id}".encode()).hexdigest()
    return f"telegram_chat:{digest[:24]}"


def _upsert_staff_link_telegram_user(
    db: Session,
    message: dict[str, Any],
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


def _staff_confirmation_token_hash(raw_token: str) -> str:
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    return f"staff_confirmation_token:{digest}"


def _staff_action_payload_hash(
    *, operation_key: str, command_key: str, role: str
) -> str:
    digest = hashlib.sha256(
        f"{operation_key}|{command_key}|{role}".encode()
    ).hexdigest()
    return f"staff_action_payload:{digest}"


def _staff_action_idempotency_key_hash(
    *,
    token_hash: str,
    action_payload_hash: str,
    target_reference_hash: str,
    request_id: str | None,
) -> str:
    material = "|".join(
        [
            token_hash,
            action_payload_hash,
            target_reference_hash,
            str(request_id or ""),
        ]
    )
    digest = hashlib.sha256(material.encode()).hexdigest()
    return f"staff_action_idempotency:{digest}"


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


def _record_staff_action_confirmation_requested_audit(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int,
    telegram_user_id: int | None,
    role: str,
    operation_key: str,
    command_key: str,
    target_reference_hash: str,
    expires_at: datetime,
    confirmation_window_seconds: int,
) -> None:
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": "staff_action_confirmation_requested",
        "target_type": "telegram_staff_action",
        "target_reference_hash": target_reference_hash,
        "result": "confirmation_requested",
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "operation_key": operation_key,
        "command_key": command_key,
        "confirmation_required": True,
        "confirmation_token_hash_stored": True,
        "confirmation_token_returned_to_telegram": False,
        "confirmation_expires_at": expires_at.isoformat(),
        "confirmation_window_seconds": confirmation_window_seconds,
        "idempotency_key_present": True,
        "idempotency_key_hash_stored": True,
        "idempotency_key_returned_to_telegram": False,
        "telegram_execution_enabled": False,
        "domain_mutation": False,
        "state_changing_action": True,
        "redacted": True,
    }
    crud_audit.log(
        db,
        action="staff_action_confirmation_requested",
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _create_staff_action_confirmation_request(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int,
    telegram_user_id: int | None,
    role: str,
    operation: dict[str, Any],
    command_key: str,
) -> str:
    operation_key = str(operation.get("key") or "staff_action").strip()
    confirmation_window_seconds = int(
        STAFF_BOT_CONFIRMATION_CONTRACT.get("confirmation_window_seconds") or 120
    )
    expires_at = datetime.now(UTC) + timedelta(
        seconds=confirmation_window_seconds
    )
    target_reference_hash = _staff_action_reference_hash(operation_key)
    action_payload_hash = _staff_action_payload_hash(
        operation_key=operation_key,
        command_key=command_key,
        role=role,
    )
    raw_token = secrets.token_urlsafe(32)
    token_hash = _staff_confirmation_token_hash(raw_token)
    idempotency_key_hash = _staff_action_idempotency_key_hash(
        token_hash=token_hash,
        action_payload_hash=action_payload_hash,
        target_reference_hash=target_reference_hash,
        request_id=request_id,
    )

    _record_staff_action_confirmation_requested_audit(
        db,
        chat_id=chat_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        telegram_user_id=telegram_user_id,
        role=role,
        operation_key=operation_key,
        command_key=command_key,
        target_reference_hash=target_reference_hash,
        expires_at=expires_at,
        confirmation_window_seconds=confirmation_window_seconds,
    )
    TelegramStaffConfirmationTokenService(db).issue_token(
        token_hash=token_hash,
        staff_user_id=actor_user_id,
        telegram_chat_id=chat_id,
        operation_key=operation_key,
        command_key=command_key,
        action_payload_hash=action_payload_hash,
        target_type="telegram_staff_action",
        target_reference_hash=target_reference_hash,
        idempotency_key_hash=idempotency_key_hash,
        expires_at=expires_at,
        request_id=request_id,
    )

    operation_label = str(operation.get("label") or operation_key).strip()
    domain = str(operation.get("domain_service_required") or "domain").strip()
    return "\n".join(
        [
            TELEGRAM_STAFF_ACTION_CONFIRMATION_REQUESTED_MESSAGE,
            f"Action: {operation_label}",
            f"Domain: {domain}",
            f"Expires in: {confirmation_window_seconds} seconds",
            "Status: awaiting confirmation in the protected clinic app",
            "Telegram execution: disabled",
            "Domain mutation: not performed",
        ]
    )


def _staff_read_only_commands() -> set[str]:
    return {
        str(item.get("command") or "").lower()
        for item in STAFF_BOT_COMMAND_REGISTRATION_CONTRACT.get("commands", [])
        if item.get("intent") == "read_only" and item.get("command")
    }


def _staff_menu_for_role(role: Any) -> dict[str, Any] | None:
    role_key = _normalize_staff_role(role)
    for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT:
        if role_menu.get("role") == role_key:
            return role_menu
    return None


STAFF_MENU_ITEM_ICONS = {
    "queue_overview": "📋",
    "next_patient": "➡️",
    "payment_status": "💳",
    "today_schedule": "📅",
    "emr_reminders": "🩺",
    "unpaid_invoices": "🧾",
    "paid_invoices": "✅",
    "reconciliation_alerts": "🔁",
    "ready_reports": "📄",
    "pending_reports": "⏳",
    "delivery_status": "📬",
    "daily_summary": "📊",
    "integration_errors": "⚠️",
    "staff_readiness": "🛠️",
    "revenue_summary": "💰",
}

STAFF_MENU_BUTTON_ICON_PREFIXES = tuple(
    dict.fromkeys(
        [
            *STAFF_MENU_ITEM_ICONS.values(),
            "🏠",
            "❓",
        ]
    )
)


def _staff_menu_item_label(item: dict[str, Any]) -> str:
    key = str(item.get("key") or "").strip()
    label = str(item.get("label") or key).strip()
    icon = STAFF_MENU_ITEM_ICONS.get(key)
    return f"{icon} {label}" if icon else label


def _normalize_staff_button_text(text: Any) -> str:
    value = " ".join(str(text or "").strip().lower().split())
    value = value.replace("\ufe0f", "").strip()
    for prefix in STAFF_MENU_BUTTON_ICON_PREFIXES:
        normalized_prefix = prefix.replace("\ufe0f", "").strip().lower()
        if normalized_prefix and value.startswith(normalized_prefix):
            value = value[len(normalized_prefix):].strip()
            break
    return value


def _staff_menu_keyboard(role_menu: dict[str, Any]) -> dict[str, Any]:
    rows = [
        [{"text": _staff_menu_item_label(item)}]
        for item in role_menu.get("items", [])
        if item.get("intent") == "read_only"
    ]
    rows.append([{"text": "/staff"}, {"text": "/help"}])
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def _staff_menu_message(user: User, role_menu: dict[str, Any]) -> str:
    items = [
        _staff_menu_item_label(item)
        for item in role_menu.get("items", [])
        if item.get("intent") == "read_only"
    ]
    role_key = _normalize_staff_role(getattr(user, "role", None))
    role_label = str(role_menu.get("label") or role_key).strip()
    lines = [
        "👥 Меню сотрудника (только просмотр)",
        "Staff read-only menu",
        f"Роль: {role_label} ({role_key})",
        f"Role: {role_key}",
        "",
        "Что можно смотреть в Telegram:",
    ]
    lines.extend(f"- {item}" for item in items)
    lines.extend(
        [
            "",
            "Команды:",
            "/staff или /help - открыть это меню",
            "/queue - очередь по роли",
            "/schedule - расписание",
            "/payments - статусы оплат",
            "/reports - готовность результатов",
            "/summary - операционная сводка",
            "",
            "Действия, которые меняют данные, в Telegram отключены.",
            "State-changing actions are disabled in Telegram.",
            "Для вызова пациента, изменения очереди, оплаты или EMR откройте приложение клиники.",
            "No patient names, phone numbers, diagnoses, or full EMR content are shown here.",
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
                labels.add(_normalize_staff_button_text(label))
            key = str(item.get("key") or "").strip().lower()
            if key:
                labels.add(key)
            display_label = _staff_menu_item_label(item)
            if display_label:
                labels.add(_normalize_staff_button_text(display_label))
    return labels


def _staff_menu_item_for_text(
    role_menu: dict[str, Any], text: str
) -> dict[str, Any] | None:
    normalized_text = _normalize_staff_button_text(text)
    for item in role_menu.get("items", []):
        label = str(item.get("label") or "").strip().lower()
        key = str(item.get("key") or "").strip().lower()
        display_label = _normalize_staff_button_text(_staff_menu_item_label(item))
        if normalized_text in {label, key, display_label}:
            return item
    return None


def _staff_menu_item_for_command(
    role_menu: dict[str, Any], command: str
) -> dict[str, Any] | None:
    allowed_keys = set(STAFF_COMMAND_DOMAIN_ITEM_KEYS.get(command, ()))
    if not allowed_keys:
        return None
    for item in role_menu.get("items", []):
        if str(item.get("key") or "").strip().lower() in allowed_keys:
            return item
    return None


def _today_start() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


def _status_counts(rows: list[tuple[Any, Any]]) -> dict[str, int]:
    return {str(status or "unknown"): int(count or 0) for status, count in rows}


def _format_money(amount: Any) -> str:
    value = amount if isinstance(amount, Decimal) else Decimal(str(amount or 0))
    return f"{value.quantize(Decimal('0.01'))} UZS"


def _queue_status_counts(db: Session) -> dict[str, int]:
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


def _lab_status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(LabReportInstance.status, func.count(LabReportInstance.id))
        .filter(LabReportInstance.created_at >= _today_start())
        .group_by(LabReportInstance.status)
        .all()
    )
    return _status_counts(rows)


def _lab_delivery_status_counts(db: Session) -> dict[str, int]:
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


def _integration_error_counts(db: Session) -> dict[str, int]:
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


def _visit_status_counts(db: Session, user: User | None = None) -> dict[str, int]:
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


def _staff_revenue_summary_message(db: Session) -> str:
    rows = _payment_invoice_status_rows(db)
    invoice_count = sum(count for _status, count, _amount in rows)
    gross_total = sum((amount for _status, _count, amount in rows), Decimal("0"))
    collected_total = sum(
        (amount for status, _count, amount in rows if status in PAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    pending_total = sum(
        (amount for status, _count, amount in rows if status in UNPAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    other_total = max(gross_total - collected_total - pending_total, Decimal("0"))
    return "\n".join(
        [
            "Revenue summary",
            f"Date: {date.today().isoformat()}",
            f"Invoices today: {invoice_count}",
            f"Gross invoiced: {_format_money(gross_total)}",
            f"Collected revenue: {_format_money(collected_total)}",
            f"Pending revenue: {_format_money(pending_total)}",
            f"Other invoice total: {_format_money(other_total)}",
            "Mode: read-only revenue aggregate snapshot",
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
    db: Session, menu_item: dict[str, Any] | None, user: User | None = None
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
    if item_key == "revenue_summary":
        return _staff_revenue_summary_message(db)
    if item_key == "daily_summary":
        return _staff_daily_summary_message(db)
    return None


def _staff_state_change_operations_by_command() -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for operation in STAFF_BOT_CONFIRMATION_CONTRACT.get("operations", []):
        for command in operation.get("telegram_commands", []):
            command_key = str(command or "").strip().lower()
            if command_key:
                operations[command_key] = operation
    return operations


def _staff_state_change_operation_for_command(
    command: str,
) -> dict[str, Any] | None:
    return _staff_state_change_operations_by_command().get(command)


def _linked_staff_for_chat(
    db: Session, chat_id: int
) -> tuple[TelegramUser | None, User | None, dict[str, Any] | None]:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.user_id:
        return telegram_user, None, None

    user = db.query(User).filter(User.id == telegram_user.user_id).first()
    if not user or not getattr(user, "is_active", True):
        return telegram_user, user, None

    return telegram_user, user, _staff_menu_for_role(getattr(user, "role", None))


async def _handle_staff_read_only_menu(
    update: dict[str, Any], db: Session, bot_service
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
    normalized_text = _normalize_staff_button_text(text)
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
        if command == "/staff":
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
        if role in allowed_roles:
            try:
                confirmation_message = _create_staff_action_confirmation_request(
                    db,
                    chat_id=chat_id,
                    request_id=request_id,
                    actor_user_id=int(user.id),
                    telegram_user_id=getattr(_telegram_user, "id", None),
                    role=role,
                    operation=state_change_operation,
                    command_key=command,
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "Staff action confirmation request failed operation_key=%s error_type=%s",
                    operation_key,
                    type(exc).__name__,
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
                    reason="confirmation_request_failed",
                )
                db.commit()
                await bot_service._send_message(
                    chat_id,
                    TELEGRAM_STAFF_ACTION_DENIED_MESSAGE,
                    menu,
                )
                return True

            await bot_service._send_message(chat_id, confirmation_message, menu)
            return True

        _record_staff_action_denied_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=role,
            operation_key=operation_key,
            command_key=command,
            reason="role_not_allowed",
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE,
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


async def _handle_ticket_qr_start(update: dict[str, Any], db: Session, bot_service) -> bool:
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
            existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(
                db, int(chat_id)
            )
            notifications_already_enabled = bool(
                getattr(existing_telegram_user, "notifications_enabled", False)
            )
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

        language = _telegram_chat_language(db, int(chat_id))
        reply_text = _telegram_chat_text(db, int(chat_id), "ticket_qr_linked")
        reply_markup = _telegram_chat_menu(db, int(chat_id))
        if not notifications_already_enabled:
            reply_text = (
                f"{reply_text}\n\n{_localized_text('notification_consent', language)}"
            )
            reply_markup = _localized_notification_consent_menu(language)
        await bot_service._send_message(int(chat_id), reply_text, reply_markup)
    elif chat_id is not None:
        language = _telegram_chat_language(db, int(chat_id))
        await bot_service._send_message(
            int(chat_id),
            _localized_text("ticket_qr_expired", language),
            _localized_main_menu(language),
        )

    return True


async def _handle_staff_link_start(
    update: dict[str, Any], db: Session, bot_service
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

def _message_from_update(update: dict[str, Any]) -> dict[str, Any]:
    return update.get("message") or {}


def _message_chat_id(message: dict[str, Any]) -> int | None:
    chat_id = (message.get("chat") or {}).get("id")
    return int(chat_id) if chat_id is not None else None


def _message_text(message: dict[str, Any]) -> str:
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


def _patient_recent_visits(
    db: Session, patient_id: int, limit: int = 3
) -> list[Visit]:
    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.desc(), Visit.created_at.desc(), Visit.id.desc())
        .limit(limit)
        .all()
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
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    entries = _patient_today_queue_entries(db, telegram_user.patient_id)
    open_hint = _localized_text("queue_open_hint", language)
    if not entries:
        queue_empty = _localized_text("queue_empty", language).format(
            patient=patient_name,
            visit_summary=_html_text(
                _recent_visit_summary(db, telegram_user.patient_id, language)
            ),
        )
        return f"{queue_empty}\n\n{open_hint}"

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
    lines.extend(["", open_hint])
    return "\n".join(lines)


def _clinic_visits_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    visits = _patient_recent_visits(db, telegram_user.patient_id)
    open_hint = _localized_text("visits_open_hint", language)
    if not visits:
        visits_empty = _localized_text("visits_empty", language).format(
            patient=patient_name
        )
        return f"{visits_empty}\n\n{open_hint}"

    lines = [
        _localized_text("visits_patient", language).format(patient=patient_name),
        _localized_text("visits_title", language),
    ]
    for index, visit in enumerate(visits, start=1):
        visit_date = (
            visit.visit_date.isoformat()
            if visit.visit_date
            else _localized_text("recent_visit_unknown_date", language)
        )
        lines.append(
            _localized_text("visits_line", language).format(
                index=index,
                visit_id=visit.id,
                visit_date=_html_text(visit_date),
                status=_html_text(visit.status),
            )
        )
    lines.extend([_localized_text("visits_privacy_note", language), "", open_hint])
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
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

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
        lines.append(
            _localized_text("payments_visits", language).format(count=len(visits))
        )
    if _patient_payment_entry_url():
        lines.append(_localized_text("payments_protected_entry", language))
    else:
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
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "unlinked_protected_action"),
            _telegram_onboarding_entry_markup(db, chat_id) or _telegram_chat_menu(db, chat_id),
            "telegram_patient_results_needs_link",
        )
        return

    instances = _latest_ready_lab_report_instances(db, telegram_user.patient_id)
    if not instances:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("lab_results_empty", language),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_lab_results_empty",
        )
        return

    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("lab_results_found", language).format(count=len(instances)),
        _telegram_chat_menu(db, chat_id),
        "telegram_patient_lab_results_found",
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
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("lab_results_send_failed", language),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_lab_results_send_failed",
        )


def _clinic_status_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

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
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    return _telegram_chat_text(db, chat_id, "results_hint")


async def _send_language_choice(db: Session, bot_service, chat_id: int) -> None:
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("language_prompt", TELEGRAM_LANGUAGE_RU),
        TELEGRAM_LANGUAGE_MENU,
        "telegram_patient_language_prompt",
    )


async def _send_clinic_welcome(
    db: Session,
    bot_service,
    chat_id: int,
    language_code: str = TELEGRAM_LANGUAGE_RU,
) -> None:
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("welcome", language_code),
        _localized_main_menu(language_code),
        "telegram_patient_welcome",
    )


async def _send_notification_consent(
    db: Session,
    bot_service,
    chat_id: int,
    language_code: str = TELEGRAM_LANGUAGE_RU,
) -> None:
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("notification_consent", language_code),
        _localized_notification_consent_menu(language_code),
        "telegram_patient_notification_consent",
    )


def _patient_contact_linked_text(
    language_code: str,
    patient_label: str,
    patient_name: str,
    include_notification_consent: bool,
) -> str:
    text = (
        f"{_localized_text('contact_linked', language_code)}\n"
        f"{patient_label}: {patient_name}"
    )
    if include_notification_consent:
        return f"{text}\n\n{_localized_text('notification_consent', language_code)}"
    return text


async def _set_notification_consent(
    db: Session, bot_service, chat_id: int, enabled: bool
) -> None:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    language = _normalize_patient_language(getattr(telegram_user, "language_code", None))
    previous_template_key = _latest_patient_bot_template_key(db, chat_id)
    if telegram_user:
        telegram_user.notifications_enabled = enabled
        telegram_user.appointment_reminders = enabled
        telegram_user.lab_notifications = enabled
        telegram_user.last_activity = datetime.utcnow()
        db.commit()

    result_key = "notifications_enabled" if enabled else "notifications_disabled"
    settings_context = _is_patient_settings_context_template(previous_template_key)
    reply_text = _localized_text(result_key, language)
    reply_markup = _localized_main_menu(language)
    template_key = f"telegram_patient_{result_key}"
    if settings_context:
        reply_text = f"{reply_text}\n\n{_telegram_settings_message(db, chat_id)}"
        reply_markup = _localized_settings_menu(language)
        template_key = f"telegram_patient_settings_{result_key}"
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        reply_text,
        reply_markup,
        template_key,
    )


async def _handle_contact_link(
    message: dict[str, Any], db: Session, bot_service
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
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "contact_rejected"),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_contact_rejected",
        )
        return True

    patient = _find_patient_by_phone(db, str(contact.get("phone_number") or ""))
    if not patient:
        existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(
            db, int(chat_id)
        )
        _upsert_ticket_qr_telegram_user(
            db,
            message,
            notifications_enabled=False if existing_telegram_user is None else None,
        )
        db.commit()
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "patient_not_found"),
            _telegram_onboarding_entry_markup(db, chat_id) or _telegram_chat_menu(db, chat_id),
            "telegram_patient_not_found",
        )
        return True

    try:
        existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(
            db, int(chat_id)
        )
        notifications_already_enabled = bool(
            getattr(existing_telegram_user, "notifications_enabled", False)
        )
        _upsert_ticket_qr_telegram_user(db, message, patient.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram contact link failed error_type=%s",
            type(exc).__name__,
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "ticket_qr_link_failed"),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_ticket_qr_link_failed",
        )
        return True

    language = _telegram_chat_language(db, chat_id)
    reply_markup = _localized_main_menu(language)
    if not notifications_already_enabled:
        reply_markup = _localized_notification_consent_menu(language)
    patient_label = "Bemor" if language == TELEGRAM_LANGUAGE_UZ else "Пациент"
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _patient_contact_linked_text(
            language,
            patient_label,
            _patient_display_name(patient),
            not notifications_already_enabled,
        ),
        reply_markup,
        "telegram_patient_contact_linked",
    )
    return True


async def _handle_clinic_bot_update(
    update: dict[str, Any], db: Session, bot_service
) -> bool:
    async def start_handler(chat_id: int, message: dict[str, Any]) -> None:
        _upsert_ticket_qr_telegram_user(db, message, notifications_enabled=False)
        db.commit()
        await _send_language_choice(db, bot_service, chat_id)

    async def language_handler(chat_id: int, language_code: str) -> None:
        message = _message_from_update(update)
        telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
        previous_template_key = _latest_patient_bot_template_key(db, chat_id)
        _upsert_ticket_qr_telegram_user(
            db,
            message,
            language_code=language_code,
            notifications_enabled=False if telegram_user is None else None,
        )
        db.commit()
        language = _normalize_patient_language(language_code)
        logger.info(
            "Telegram patient bot language selected",
            extra={"language_code": language},
        )
        settings_context = _is_patient_settings_context_template(previous_template_key)
        reply_text = _localized_text("language_selected", language)
        reply_markup = _localized_main_menu(language)
        template_key = "telegram_patient_language_selected"
        linked_telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
        if not settings_context and not getattr(linked_telegram_user, "patient_id", None):
            reply_text = f"{reply_text}\n\n{_localized_text('share_contact', language)}"
            template_key = "telegram_patient_language_selected_needs_contact"
        if settings_context:
            reply_text = f"{reply_text}\n\n{_telegram_settings_message(db, chat_id)}"
            reply_markup = _localized_settings_menu(language)
            template_key = "telegram_patient_settings_language_selected"
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            template_key,
        )

    async def help_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("help", language),
            _localized_main_menu(language),
            "telegram_patient_help",
        )

    async def menu_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("main_menu_refreshed", language),
            _localized_main_menu(language),
            "telegram_patient_main_menu_refreshed",
        )

    async def services_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("services_menu", language),
            _localized_services_menu(language),
            "telegram_patient_services_menu",
        )

    async def settings_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_settings_message(db, chat_id),
            _localized_settings_menu(language),
            "telegram_patient_settings",
        )

    async def queue_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_queue_message(db, chat_id),
            _telegram_queue_entry_markup(db, chat_id)
            or _telegram_chat_menu(db, chat_id),
            "telegram_patient_queue",
        )

    async def visits_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_visits_message(db, chat_id),
            _telegram_visits_entry_markup(db, chat_id)
            or _telegram_chat_menu(db, chat_id),
            "telegram_patient_visits",
        )

    async def payments_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_payments_message(db, chat_id),
            _telegram_payment_entry_markup(db, chat_id)
            or _telegram_chat_menu(db, chat_id),
            "telegram_patient_payments",
        )

    async def profile_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_status_message(db, chat_id),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_profile",
        )

    async def results_handler(chat_id: int) -> None:
        await _send_clinic_lab_results(db, bot_service, chat_id)

    async def share_contact_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "share_contact"),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_share_contact",
        )

    async def book_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        reply_markup = _telegram_booking_entry_markup(db, chat_id) or _localized_main_menu(language)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("book", language),
            reply_markup,
            "telegram_patient_book",
        )

    async def patient_forms_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
        reply_text = (
            _localized_text("patient_forms", language)
            if telegram_user and telegram_user.patient_id
            else _localized_text("unlinked_protected_action", language)
        )
        reply_markup = (
            _telegram_patient_forms_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            "telegram_patient_forms_placeholder",
        )

    async def patient_documents_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
        reply_text = (
            _localized_text("patient_documents", language)
            if telegram_user and telegram_user.patient_id
            else _localized_text("unlinked_protected_action", language)
        )
        reply_markup = (
            _telegram_patient_documents_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            "telegram_patient_documents_placeholder",
        )

    async def doctor_schedule_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        reply_markup = (
            _telegram_patient_doctors_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("doctor_schedule", language),
            reply_markup,
            "telegram_patient_doctor_schedule_placeholder",
        )

    async def patient_cabinet_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
        reply_text = (
            _localized_text("patient_cabinet", language)
            if telegram_user and telegram_user.patient_id
            else _localized_text("unlinked_protected_action", language)
        )
        reply_markup = (
            _telegram_patient_cabinet_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            "telegram_patient_cabinet_placeholder",
        )

    async def staff_entry_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("staff_entry", language),
            _localized_main_menu(language),
            "telegram_patient_staff_entry_placeholder",
        )

    async def support_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("support", language),
            _localized_main_menu(language),
            "telegram_patient_support",
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
        "/menu": menu_handler,
        "/book": book_handler,
        "/queue": queue_handler,
        "/visits": visits_handler,
        "/payments": payments_handler,
        "/profile": profile_handler,
        "/results": results_handler,
        "/services": services_handler,
        "/forms": patient_forms_handler,
        "/documents": patient_documents_handler,
        "/doctors": doctor_schedule_handler,
        "/cabinet": patient_cabinet_handler,
        "/settings": settings_handler,
        "/support": support_handler,
    }
    text_handlers = _patient_text_handler_aliases(
        [
            ("🏥 Записаться на приём", book_handler),
            ("❓ Помощь", help_handler),
            ("⚙️ Настройки", settings_handler),
            ("🎫 Моя очередь", queue_handler),
            ("📅 Мои визиты", visits_handler),
            ("💳 Оплаты и долг", payments_handler),
            ("👤 Мой статус", profile_handler),
            ("📄 Результаты", results_handler),
            ("📱 Поделиться номером", share_contact_handler),
            ("📲 Онлайн-сервисы", services_handler),
            ("📋 Анкеты пациента", patient_forms_handler),
            ("🧾 Документы и чеки", patient_documents_handler),
            ("🧑‍⚕️ Врачи и расписание", doctor_schedule_handler),
            ("📲 Кабинет пациента", patient_cabinet_handler),
            ("👥 Режим сотрудника", staff_entry_handler),
            ("⬅️ Главное меню", menu_handler),
            ("☎️ Связаться с клиникой", support_handler),
            ("меню", menu_handler),
            ("menu", menu_handler),
            ("menyu", menu_handler),
            ("staff", staff_entry_handler),
            ("сотрудник", staff_entry_handler),
            ("🇷🇺 Русский", russian_language_handler),
            ("🇺🇿 O'zbekcha", uzbek_language_handler),
            ("ozbekcha", uzbek_language_handler),
            ("uzbekcha", uzbek_language_handler),
            ("🔔 Разрешить уведомления", enable_notifications_handler),
            ("🔕 Без уведомлений", disable_notifications_handler),
            ("🔔 Xabarnomalarga roziman", enable_notifications_handler),
            ("🔕 Xabarnomasiz", disable_notifications_handler),
            ("🏥 Qabulga yozilish", book_handler),
            ("❓ Yordam", help_handler),
            ("⚙️ Sozlamalar", settings_handler),
            ("🎫 Mening navbatim", queue_handler),
            ("📅 Mening tashriflarim", visits_handler),
            ("💳 To'lovlar va qarz", payments_handler),
            ("👤 Mening holatim", profile_handler),
            ("📄 Natijalar", results_handler),
            ("📱 Telefon raqamni ulashish", share_contact_handler),
            ("📲 Onlayn xizmatlar", services_handler),
            ("📋 Bemor anketalari", patient_forms_handler),
            ("🧾 Hujjatlar va cheklar", patient_documents_handler),
            ("🧑‍⚕️ Shifokorlar jadvali", doctor_schedule_handler),
            ("📲 Bemor kabineti", patient_cabinet_handler),
            ("👥 Xodim rejimi", staff_entry_handler),
            ("⬅️ Asosiy menyu", menu_handler),
            ("☎️ Klinikaga bog'lanish", support_handler),
            ("Menyu", menu_handler),
            ("Asosiy menyu", menu_handler),
            ("xodim", staff_entry_handler),
        ]
    )

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

    existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if existing_telegram_user is None:
        _upsert_ticket_qr_telegram_user(db, message, notifications_enabled=False)
        db.commit()

    text = _message_text(message)
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    handler = command_handlers.get(command) or text_handlers.get(
        _normalize_patient_button_text(text)
    )
    if command == "/start":
        await start_handler(chat_id, message)
        return True
    if handler:
        await handler(chat_id)
        return True
    return False


class TelegramMiniAppAppointmentPreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None
    appointment_date: date = Field(..., alias="appointmentDate")
    appointment_time: str | None = Field(default=None, alias="appointmentTime")
    doctor_id: int | None = Field(default=None, alias="doctorId")
    department: str | None = None
    notes: str | None = None
    services: list[str] | None = None


class TelegramMiniAppPatientManifestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    section: str | None = None


class TelegramMiniAppPatientFormsPreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None


class TelegramMiniAppPatientCabinetSummaryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None


class TelegramMiniAppPatientReportDownloadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None
    report_id: int = Field(..., alias="reportId", ge=1)


class TelegramMiniAppPatientFormSubmissionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None
    form_id: str = Field(..., alias="formId", min_length=1, max_length=64)
    answers: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="submitted")


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
    if not hmac.compare_digest(received_secret or "", expected_secret or ""):
        logger.warning("Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )


# TG-AUDIT-28 P0-8: webhook должен возвращать 200 даже при ошибке,
# чтобы Telegram не retry'ил (дублирующая обработка). Ошибка логируется.
def _acknowledge_webhook_error(operation: str, exc: Exception) -> JSONResponse:
    logger.error(
        "Telegram webhook error operation=%s error_type=%s: %s",
        operation, type(exc).__name__, exc,
    )
    return JSONResponse(status_code=200, content={"status": "error", "message": "Internal error logged"})


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


def _telegram_bot_info_failure(exc: Exception) -> dict[str, Any]:
    logger.warning(
        "Telegram webhook endpoint failed operation=get_bot_info error_type=%s",
        type(exc).__name__,
    )
    return {"active": False, "message": TELEGRAM_BOT_INFO_PUBLIC_MESSAGE}


def _mini_app_booking_scope_status_code(reason: str) -> int:
    if reason in MINI_APP_BOOKING_REQUEST_ERROR_REASONS:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_403_FORBIDDEN


def _mini_app_forms_scope_status_code(reason: str) -> int:
    if reason in MINI_APP_FORMS_REQUEST_ERROR_REASONS:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_403_FORBIDDEN


def _build_mini_app_appointment_booking_preview_from_request(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    db: Session,
    *,
    allow_entry_token: bool = False,
):
    try:
        if allow_entry_token:
            scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
                db,
                init_data_payload=request_body.init_data,
                entry_token=request_body.entry_token,
                expected_section=request_body.section or "appointments",
            )
        else:
            if not request_body.init_data:
                raise TelegramMiniAppInitDataError("init_data_required")
            scope = _resolve_mini_app_patient_scope_from_init_data(
                db,
                request_body.init_data,
            )

        preview = build_telegram_mini_app_appointment_booking_preview(
            scope,
            patient_id=request_body.patient_id,
            appointment_date=request_body.appointment_date,
            appointment_time=request_body.appointment_time,
            doctor_id=request_body.doctor_id,
            department=request_body.department,
            notes=request_body.notes,
            services=request_body.services,
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=_mini_app_booking_scope_status_code(exc.reason),
            detail={"reason": exc.reason},
        ) from exc

    return preview


def _resolve_mini_app_patient_scope_from_init_data(
    db: Session,
    init_data_payload: str,
):
    bot_token = _get_configured_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "bot_token_required"},
        )

    init_data = validate_telegram_mini_app_init_data(
        init_data_payload,
        bot_token=bot_token,
    )
    return resolve_telegram_mini_app_session_scope(
        db,
        init_data,
        expected_scope="patient",
    )


def _resolve_mini_app_patient_scope_from_entry_token(
    db: Session,
    entry_token: str,
    *,
    expected_section: str | None = None,
) -> TelegramMiniAppSessionScope:
    parsed = _parse_patient_mini_app_entry_token(
        entry_token,
        expected_section=expected_section,
    )
    if not parsed:
        raise TelegramMiniAppSessionScopeError("entry_token_invalid")

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(
        db,
        int(parsed["chat_id"]),
    )
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")
    if not getattr(telegram_user, "patient_id", None):
        raise TelegramMiniAppSessionScopeError("patient_scope_required")

    return TelegramMiniAppSessionScope(
        scope_type="patient",
        telegram_user_id=int(telegram_user.id),
        telegram_chat_id=int(telegram_user.chat_id),
        patient_id=int(telegram_user.patient_id),
    )


def _resolve_mini_app_patient_scope_from_auth(
    db: Session,
    *,
    init_data_payload: str | None = None,
    entry_token: str | None = None,
    expected_section: str | None = None,
) -> tuple[TelegramMiniAppSessionScope, str]:
    normalized_init_data = str(init_data_payload or "").strip()
    if normalized_init_data:
        return _resolve_mini_app_patient_scope_from_init_data(
            db,
            normalized_init_data,
        ), "init_data"

    normalized_entry_token = str(entry_token or "").strip()
    if normalized_entry_token:
        return _resolve_mini_app_patient_scope_from_entry_token(
            db,
            normalized_entry_token,
            expected_section=expected_section,
        ), "entry_token"

    raise TelegramMiniAppInitDataError("init_data_required")


def _telegram_user_from_mini_app_init_data(
    db: Session,
    init_data_payload: str,
) -> TelegramUser:
    bot_token = _get_configured_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "bot_token_required"},
        )

    init_data = validate_telegram_mini_app_init_data(
        init_data_payload,
        bot_token=bot_token,
    )
    user = init_data.user if isinstance(init_data.user, dict) else {}
    try:
        chat_id = int(user.get("id"))
    except (TypeError, ValueError) as exc:
        raise TelegramMiniAppSessionScopeError("telegram_user_id_required") from exc

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")
    return telegram_user


def _onboarding_scope_for_telegram_user(
    telegram_user: TelegramUser,
) -> TelegramMiniAppSessionScope:
    return TelegramMiniAppSessionScope(
        scope_type="onboarding",  # type: ignore[arg-type]
        telegram_user_id=int(telegram_user.id),
        telegram_chat_id=int(telegram_user.chat_id),
        patient_id=None,
    )


def _resolve_mini_app_onboarding_scope_from_init_data(
    db: Session,
    init_data_payload: str,
) -> TelegramMiniAppSessionScope:
    telegram_user = _telegram_user_from_mini_app_init_data(db, init_data_payload)
    return _onboarding_scope_for_telegram_user(telegram_user)


def _resolve_mini_app_onboarding_scope_from_entry_token(
    db: Session,
    entry_token: str,
    *,
    expected_section: str | None = None,
) -> TelegramMiniAppSessionScope:
    parsed = _parse_patient_onboarding_entry_token(
        entry_token,
        expected_section=expected_section,
    )
    if not parsed:
        raise TelegramMiniAppSessionScopeError("entry_token_invalid")

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(
        db,
        int(parsed["chat_id"]),
    )
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")
    return _onboarding_scope_for_telegram_user(telegram_user)


def _resolve_mini_app_onboarding_scope_from_auth(
    db: Session,
    *,
    init_data_payload: str | None = None,
    entry_token: str | None = None,
    expected_section: str | None = None,
) -> tuple[TelegramMiniAppSessionScope, str]:
    normalized_init_data = str(init_data_payload or "").strip()
    if normalized_init_data:
        return _resolve_mini_app_onboarding_scope_from_init_data(
            db,
            normalized_init_data,
        ), "init_data"

    normalized_entry_token = str(entry_token or "").strip()
    if normalized_entry_token:
        return _resolve_mini_app_onboarding_scope_from_entry_token(
            db,
            normalized_entry_token,
            expected_section=expected_section,
        ), "entry_token"

    raise TelegramMiniAppInitDataError("init_data_required")


def _mini_app_patient_manifest_payload(
    db: Session,
    scope: TelegramMiniAppSessionScope,
    *,
    auth_source: str,
) -> dict[str, Any]:
    patient = db.query(Patient).filter(Patient.id == int(scope.patient_id)).first()
    telegram_user = (
        db.query(TelegramUser)
        .filter(TelegramUser.id == int(scope.telegram_user_id))
        .first()
    )
    language_code = _normalize_patient_language(
        getattr(telegram_user, "language_code", None)
    )
    return {
        "scope": {
            "type": scope.scope_type,
        },
        "auth": {
            "source": auth_source,
            "entry_token_fallback": auth_source == "entry_token",
        },
        "language": {
            "code": language_code,
            "label": "O'zbekcha"
            if language_code == TELEGRAM_LANGUAGE_UZ
            else "Русский",
        },
        "patient": {
            "linked": True,
            "name": _patient_display_name(patient),
        },
        "capabilities": {
            "appointments": {
                "status": "preview_enabled",
                "preview_enabled": True,
                "create_enabled": False,
            },
            "forms": {
                "status": "preview_enabled",
                "preview_enabled": True,
                "capture_enabled": True,
            },
            "cabinet": {
                "status": "summary_enabled",
                "read_enabled": True,
            },
            "visits": {
                "status": "summary_enabled",
                "read_enabled": True,
            },
            "queue": {
                "status": "summary_enabled",
                "read_enabled": True,
            },
            "payments": {
                "status": "summary_enabled",
                "view_enabled": True,
                "payment_capture_enabled": False,
            },
            "results": {
                "status": "ready_pdf_list_enabled",
                "read_enabled": True,
            },
        },
        "policy": {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "entry_token_ttl_seconds": PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS,
        },
    }


def _mini_app_patient_onboarding_manifest_payload(
    db: Session,
    scope: TelegramMiniAppSessionScope,
    *,
    auth_source: str,
) -> dict[str, Any]:
    telegram_user = (
        db.query(TelegramUser)
        .filter(TelegramUser.id == int(scope.telegram_user_id))
        .first()
    )
    language_code = _normalize_patient_language(
        getattr(telegram_user, "language_code", None)
    )
    onboarding_status = (
        PatientOnboardingService(db).own_status_response(telegram_user)
        if telegram_user is not None
        else {
            "request": None,
            "messageKey": "patient_onboarding_not_found",
            "safeNextAction": "submit_onboarding_request",
        }
    )
    return {
        "scope": {
            "type": "onboarding",
        },
        "auth": {
            "source": auth_source,
            "entry_token_fallback": auth_source == "entry_token",
        },
        "language": {
            "code": language_code,
            "label": "O'zbekcha"
            if language_code == TELEGRAM_LANGUAGE_UZ
            else "Русский",
        },
        "patient": {
            "linked": False,
            "name": None,
        },
        "onboarding": onboarding_status,
        "capabilities": {
            "appointments": {
                "status": "request_review_enabled",
                "preview_enabled": False,
                "create_enabled": False,
                "onboarding_request_enabled": True,
            },
            "forms": {"status": "staff_approval_required", "read_enabled": False},
            "cabinet": {"status": "staff_approval_required", "read_enabled": False},
            "visits": {"status": "staff_approval_required", "read_enabled": False},
            "queue": {"status": "staff_approval_required", "read_enabled": False},
            "payments": {"status": "staff_approval_required", "view_enabled": False},
            "results": {"status": "staff_approval_required", "read_enabled": False},
            "documents": {"status": "staff_approval_required", "read_enabled": False},
        },
        "policy": {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "entry_token_ttl_seconds": PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS,
            "patient_auto_create_allowed": False,
            "confirmed_appointment_create_allowed": False,
        },
    }


def _build_mini_app_patient_manifest_from_request(
    request_body: TelegramMiniAppPatientManifestRequest,
    db: Session,
) -> dict[str, Any]:
    try:
        scope, auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section,
        )
        return _mini_app_patient_manifest_payload(db, scope, auth_source=auth_source)
    except (TelegramMiniAppInitDataError, TelegramMiniAppSessionScopeError):
        try:
            onboarding_scope, onboarding_auth_source = (
                _resolve_mini_app_onboarding_scope_from_auth(
                    db,
                    init_data_payload=request_body.init_data,
                    entry_token=request_body.entry_token,
                    expected_section=request_body.section,
                )
            )
        except TelegramMiniAppInitDataError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": exc.reason},
            ) from exc
        except TelegramMiniAppSessionScopeError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": exc.reason},
            ) from exc
        return _mini_app_patient_onboarding_manifest_payload(
            db,
            onboarding_scope,
            auth_source=onboarding_auth_source,
        )


def _iso_date_value(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def _iso_datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _mini_app_patient_appointments(
    db: Session,
    patient_id: int,
    *,
    limit: int = 3,
) -> list[Appointment]:
    return (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(
            Appointment.appointment_date.desc(),
            Appointment.created_at.desc(),
            Appointment.id.desc(),
        )
        .limit(limit)
        .all()
    )


def _appointment_department_label(appointment: Appointment) -> str | None:
    department = getattr(appointment, "department", None)
    return getattr(department, "name", None)


def _mini_app_patient_cabinet_summary_payload(
    db: Session,
    scope,
) -> dict[str, Any]:
    patient_id = int(scope.patient_id)
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    appointments = _mini_app_patient_appointments(db, patient_id)
    recent_visits = _patient_recent_visits(db, patient_id)
    queue_entries = _patient_today_queue_entries(db, patient_id)
    entries, visits_for_billing, expected_total, paid_total, pending_total, debt_total = (
        _billing_totals(db, patient_id)
    )
    reports = _latest_ready_lab_report_instances(db, patient_id)

    return {
        "scope": {
            "type": scope.scope_type,
            "patient_id": patient_id,
        },
        "patient": {
            "name": _patient_display_name(patient),
        },
        "appointments": [
            {
                "id": int(appointment.id),
                "date": _iso_date_value(appointment.appointment_date),
                "time": appointment.appointment_time,
                "status": appointment.status,
                "department": _appointment_department_label(appointment),
            }
            for appointment in appointments
        ],
        "visits": [
            {
                "id": int(visit.id),
                "date": _iso_date_value(visit.visit_date),
                "status": visit.status,
            }
            for visit in recent_visits
        ],
        "queue": [
            {
                "number": entry.number,
                "status": entry.status,
                "cabinet": getattr(getattr(entry, "queue", None), "cabinet_number", None),
            }
            for entry in queue_entries[:5]
        ],
        "payments": {
            "billed": _format_money(expected_total),
            "paid": _format_money(paid_total),
            "pending": _format_money(pending_total),
            "debt": _format_money(debt_total),
            "linked_visit_count": len(visits_for_billing),
            "active_queue_count": len(entries),
        },
        "reports": [
            {
                "id": int(report.id),
                "name": getattr(getattr(report, "template", None), "name", "Lab report"),
                "ready_at": _iso_datetime_value(report.finalized_at or report.created_at),
                "status": report.status,
            }
            for report in reports
        ],
        "policy": {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "pdf_included": False,
        },
    }


def _build_mini_app_patient_cabinet_summary_from_request(
    request_body: TelegramMiniAppPatientCabinetSummaryRequest,
    db: Session,
) -> dict[str, Any]:
    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "cabinet",
        )
        if request_body.patient_id is not None:
            if int(scope.patient_id) != int(request_body.patient_id):
                raise TelegramMiniAppSessionScopeError("patient_scope_mismatch")
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    return _mini_app_patient_cabinet_summary_payload(db, scope)


def _resolve_mini_app_patient_scope_for_optional_patient(
    db: Session,
    init_data_payload: str | None,
    entry_token: str | None,
    patient_id: int | None,
    *,
    expected_section: str | None = None,
):
    scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
        db,
        init_data_payload=init_data_payload,
        entry_token=entry_token,
        expected_section=expected_section,
    )
    if patient_id is not None and int(scope.patient_id) != int(patient_id):
        raise TelegramMiniAppSessionScopeError("patient_scope_mismatch")
    return scope


def _build_mini_app_patient_report_download_response(
    request_body: TelegramMiniAppPatientReportDownloadRequest,
    db: Session,
) -> Response:
    try:
        scope = _resolve_mini_app_patient_scope_for_optional_patient(
            db,
            request_body.init_data,
            request_body.entry_token,
            request_body.patient_id,
            expected_section=request_body.section or "results",
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    report = (
        db.query(LabReportInstance)
        .filter(
            LabReportInstance.id == int(request_body.report_id),
            LabReportInstance.patient_id == int(scope.patient_id),
            LabReportInstance.status.in_(LAB_REPORT_READY_STATUSES),
        )
        .first()
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "report_not_ready_or_not_found"},
        )

    try:
        filename, pdf_bytes, _caption = _build_lab_report_pdf(db, report)
    except Exception as exc:
        _raise_telegram_webhook_internal_error(
            "mini_app_patient_report_download",
            "Protected report could not be generated",
            exc,
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_mini_app_patient_forms_preview_from_request(
    request_body: TelegramMiniAppPatientFormsPreviewRequest,
    db: Session,
):
    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "forms",
        )
        preview = build_telegram_mini_app_patient_forms_preview(
            db,
            scope,
            patient_id=request_body.patient_id,
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    return preview


def _save_mini_app_patient_form_submission_from_request(
    request_body: TelegramMiniAppPatientFormSubmissionRequest,
    db: Session,
):
    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "forms",
        )
        result = save_telegram_mini_app_patient_form_submission(
            db,
            scope,
            patient_id=request_body.patient_id,
            form_id=request_body.form_id,
            answers=request_body.answers,
            status=request_body.status,
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=_mini_app_forms_scope_status_code(exc.reason),
            detail={"reason": exc.reason},
        ) from exc

    return result


def _telegram_user_from_onboarding_request_auth(
    db: Session,
    request_body: PatientOnboardingAuthRequest,
) -> TelegramUser:
    try:
        scope, _auth_source = _resolve_mini_app_onboarding_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "appointments",
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    telegram_user = (
        db.query(TelegramUser)
        .filter(TelegramUser.id == int(scope.telegram_user_id))
        .first()
    )
    if telegram_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "telegram_link_required"},
        )
    return telegram_user


@router.post(
    "/mini-app/onboarding/requests",
    response_model=PatientOnboardingSubmitResponse,
    operation_id="telegram_mini_app_submit_patient_onboarding_request",
)
def submit_mini_app_patient_onboarding_request(
    request_body: PatientOnboardingSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submit a REQUEST_REVIEW onboarding request without creating a Patient."""

    telegram_user = _telegram_user_from_onboarding_request_auth(db, request_body)
    row, created = PatientOnboardingService(db).submit(
        telegram_user=telegram_user,
        payload=request_body,
    )
    return PatientOnboardingService(db).submit_response(row, created=created)


@router.post(
    "/mini-app/onboarding/status",
    response_model=PatientOnboardingStatusResponse,
    operation_id="telegram_mini_app_read_patient_onboarding_status",
)
def read_mini_app_patient_onboarding_status(
    request_body: PatientOnboardingAuthRequest,
    db: Session = Depends(get_db),
):
    """Return the caller's own onboarding request status."""

    telegram_user = _telegram_user_from_onboarding_request_auth(db, request_body)
    return PatientOnboardingService(db).own_status_response(telegram_user)


@router.get(
    "/onboarding/requests",
    response_model=RegistrarOnboardingListResponse,
    operation_id="telegram_registrar_list_patient_onboarding_requests",
)
def list_registrar_patient_onboarding_requests(
    status_filter: str = "pending_review",
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """List patient onboarding requests for registrar review."""

    allowed_statuses = {
        "pending_review",
        "linked_existing",
        "created_patient",
        "needs_more_info",
        "rejected",
        "cancelled",
        "expired",
    }
    if status_filter and status_filter not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "onboarding_status_invalid"},
        )
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    return PatientOnboardingService(db).list_pending(
        status_filter=status_filter,
        limit=safe_limit,
        offset=safe_offset,
    )


@router.get(
    "/onboarding/analytics/summary",
    response_model=OnboardingAnalyticsSummaryResponse,
    operation_id="telegram_registrar_patient_onboarding_analytics_summary",
)
def get_registrar_patient_onboarding_analytics_summary(
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Return safe onboarding funnel metrics for the registrar/admin dashboard."""

    del current_user
    return PatientOnboardingService(db).analytics_summary()


@router.get(
    "/onboarding/requests/export",
    operation_id="telegram_registrar_export_patient_onboarding_requests_csv",
)
def export_registrar_patient_onboarding_requests_csv(
    status_filter: str = "",
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Export masked onboarding requests for operational review."""

    del current_user
    csv_text = PatientOnboardingService(db).export_requests_csv(
        status_filter=status_filter
    )
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="telegram_onboarding_requests.csv"'
            )
        },
    )


@router.post(
    "/onboarding/requests/{request_id}/search-patients",
    response_model=OnboardingSearchResponse,
    operation_id="telegram_registrar_search_patient_onboarding_candidates",
)
def search_patient_candidates_for_onboarding_request(
    request_id: int,
    request_body: OnboardingPatientSearchRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Search safe duplicate candidates before linking or creating a patient."""

    return PatientOnboardingService(db).search_candidates_for_request(
        request_id=request_id,
        actor=current_user,
        search_payload=request_body,
    )


@router.post(
    "/onboarding/requests/{request_id}/link-existing",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_link_existing_patient_onboarding_request",
)
def link_existing_patient_onboarding_request(
    request_id: int,
    request_body: RegistrarPatientLinkDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Link a reviewed onboarding request to an existing patient."""

    return PatientOnboardingService(db).link_existing_patient(
        request_id=request_id,
        payload=request_body,
        actor=current_user,
    )


@router.post(
    "/onboarding/requests/{request_id}/create-patient",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_create_patient_from_onboarding_request",
)
def create_patient_from_onboarding_request(
    request: Request,
    request_id: int,
    request_body: RegistrarPatientCreateDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Create a Patient only after staff review, then link Telegram."""

    return PatientOnboardingService(db).create_patient_from_request(
        request=request,
        request_id=request_id,
        payload=request_body,
        actor=current_user,
    )


@router.post(
    "/onboarding/requests/{request_id}/request-more-info",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_request_more_info_onboarding_request",
)
def request_more_info_for_onboarding_request(
    request_id: int,
    request_body: RegistrarOnboardingReviewDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Ask the patient for more safe intake details."""

    return PatientOnboardingService(db).request_more_info(
        request_id=request_id,
        actor=current_user,
        reason_code=request_body.reason_code,
        safe_note=request_body.safe_note,
    )


@router.post(
    "/onboarding/requests/{request_id}/reject",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_reject_patient_onboarding_request",
)
def reject_patient_onboarding_request(
    request_id: int,
    request_body: RegistrarOnboardingReviewDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Reject an onboarding request with a safe patient-facing reason."""

    return PatientOnboardingService(db).reject(
        request_id=request_id,
        actor=current_user,
        reason_code=request_body.reason_code,
        safe_note=request_body.safe_note,
    )


@router.post(
    "/mini-app/appointments/preview",
    operation_id="telegram_mini_app_preview_appointment_booking",
)
def preview_mini_app_appointment_booking(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    db: Session = Depends(get_db),
):
    """Return a trusted Mini App appointment preview without creating it."""

    preview = _build_mini_app_appointment_booking_preview_from_request(
        request_body,
        db,
        allow_entry_token=True,
    )
    return preview.to_response_payload()


@router.post(
    "/mini-app/forms/submissions",
    operation_id="telegram_mini_app_submit_patient_form",
)
def submit_mini_app_patient_form(
    request_body: TelegramMiniAppPatientFormSubmissionRequest,
    db: Session = Depends(get_db),
):
    """Create or update one protected Mini App patient form submission."""

    result = _save_mini_app_patient_form_submission_from_request(
        request_body,
        db,
    )
    return result.to_response_payload()


@router.post(
    "/mini-app/cabinet/summary",
    operation_id="telegram_mini_app_patient_cabinet_summary",
)
def preview_mini_app_patient_cabinet_summary(
    request_body: TelegramMiniAppPatientCabinetSummaryRequest,
    db: Session = Depends(get_db),
):
    """Return protected patient cabinet summary without exposing Telegram ids."""

    return _build_mini_app_patient_cabinet_summary_from_request(
        request_body,
        db,
    )


@router.post(
    "/mini-app/reports/download",
    operation_id="telegram_mini_app_patient_report_download",
)
def download_mini_app_patient_report(
    request_body: TelegramMiniAppPatientReportDownloadRequest,
    db: Session = Depends(get_db),
):
    """Return one protected ready PDF report for the linked Mini App patient."""

    return _build_mini_app_patient_report_download_response(request_body, db)


@router.post(
    "/mini-app/patient/manifest",
    operation_id="telegram_mini_app_patient_manifest",
)
def preview_mini_app_patient_manifest(
    request_body: TelegramMiniAppPatientManifestRequest,
    db: Session = Depends(get_db),
):
    """Return safe Mini App capability manifest for a linked patient."""

    return _build_mini_app_patient_manifest_from_request(request_body, db)


@router.post(
    "/mini-app/forms/preview",
    operation_id="telegram_mini_app_preview_patient_forms",
)
def preview_mini_app_patient_forms(
    request_body: TelegramMiniAppPatientFormsPreviewRequest,
    db: Session = Depends(get_db),
):
    """Return trusted Mini App patient form metadata without storing data."""

    preview = _build_mini_app_patient_forms_preview_from_request(
        request_body,
        db,
    )
    return preview.to_response_payload()


@router.post(
    "/mini-app/appointments",
    status_code=status.HTTP_201_CREATED,
    operation_id="telegram_mini_app_create_appointment_booking",
)
def create_mini_app_appointment_booking(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    db: Session = Depends(get_db),
):
    """Create one trusted Mini App appointment for a linked patient."""

    preview = _build_mini_app_appointment_booking_preview_from_request(
        request_body,
        db,
        allow_entry_token=True,
    )
    draft_payload = preview.draft.to_appointment_create_payload()

    if preview.draft.doctor_id is not None and preview.draft.appointment_time:
        slot_occupied = appointment_crud.is_time_slot_occupied(
            db,
            doctor_id=preview.draft.doctor_id,
            appointment_date=preview.draft.appointment_date,
            appointment_time=preview.draft.appointment_time,
        )
        if slot_occupied:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "appointment_time_slot_occupied"},
            )

    appointment_create_payload = dict(draft_payload)
    appointment_create_payload.pop("department", None)
    appointment_in = appointment_schemas.AppointmentCreate(**appointment_create_payload)
    appointment = appointment_crud.create(db=db, obj_in=appointment_in)
    return {
        "created": True,
        "appointment_id": int(appointment.id),
        "preview": preview.to_response_payload(),
    }


@router.post("/webhook")
async def telegram_webhook(
    update: dict[str, Any], request: Request, db: Session = Depends(get_db)
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
    reply_markup: dict[str, Any] = None,
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
            return {"status": "sent"}
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
