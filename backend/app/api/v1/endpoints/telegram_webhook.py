"""
Webhook endpoint для обработки входящих сообщений от Telegram
"""

import logging
from datetime import datetime
from typing import Any, Dict, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.crud import telegram_config as crud_telegram
from app.db.session import get_db
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.visit import Visit
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
        [{"text": "Мой статус"}, {"text": "Результаты"}],
        [{"text": "Помощь"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
}
TELEGRAM_WEBHOOK_PUBLIC_ERROR = "Ошибка обработки webhook"
TELEGRAM_SEND_PUBLIC_ERROR = "Ошибка отправки сообщения"
TELEGRAM_BOT_INFO_PUBLIC_MESSAGE = "Ошибка получения информации о боте"


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


def _upsert_ticket_qr_telegram_user(
    db: Session,
    message: Dict[str, Any],
    patient_id: int | None = None,
) -> None:
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    payload = {
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "language_code": from_user.get("language_code") or "ru",
        "active": True,
        "blocked": False,
        "last_activity": datetime.utcnow(),
    }
    if patient_id is not None:
        payload["patient_id"] = patient_id
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, int(chat_id))

    if telegram_user:
        for field, value in payload.items():
            if hasattr(telegram_user, field):
                setattr(telegram_user, field, value)
        db.flush()
        return

    db.add(
        TelegramUser(
            **payload,
            chat_id=int(chat_id),
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
        )
    )
    db.flush()


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
            await bot_service._send_message(
                int(chat_id),
                TELEGRAM_TICKET_QR_LINK_FAILED_MESSAGE,
                TELEGRAM_MAIN_MENU,
            )
            return True

        await bot_service._send_message(
            int(chat_id),
            TELEGRAM_TICKET_QR_LINKED_MESSAGE,
            TELEGRAM_MAIN_MENU,
        )
    elif chat_id is not None:
        await bot_service._send_message(
            int(chat_id),
            TELEGRAM_TICKET_QR_EXPIRED_MESSAGE,
            TELEGRAM_MAIN_MENU,
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


def _recent_visit_summary(db: Session, patient_id: int) -> str:
    visit = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .first()
    )
    if not visit:
        return "Последних визитов пока нет."

    visit_date = visit.visit_date.isoformat() if visit.visit_date else "дата не указана"
    return f"Последний визит: #{visit.id}, {visit_date}, статус: {visit.status}."


def _clinic_status_message(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return TELEGRAM_NEEDS_LINK_MESSAGE

    patient = db.query(Patient).filter(Patient.id == telegram_user.patient_id).first()
    return (
        f"Telegram привязан к пациенту: {_patient_display_name(patient)}.\n"
        f"{_recent_visit_summary(db, telegram_user.patient_id)}"
    )


def _clinic_results_message(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return TELEGRAM_NEEDS_LINK_MESSAGE

    return (
        "Результаты будут приходить сюда, когда лаборатория или врач отметит их "
        "готовыми к выдаче. Если результат нужен срочно, обратитесь в регистратуру."
    )


async def _send_clinic_welcome(bot_service, chat_id: int) -> None:
    await bot_service._send_message(
        chat_id,
        (
            "Добро пожаловать в Kosmed Clinic.\n\n"
            "Через бота можно привязать Telegram к карте пациента, получать "
            "уведомления клиники и открывать результаты, когда они готовы."
        ),
        TELEGRAM_MAIN_MENU,
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
        await bot_service._send_message(chat_id, TELEGRAM_CONTACT_REJECTED_MESSAGE, TELEGRAM_MAIN_MENU)
        return True

    patient = _find_patient_by_phone(db, str(contact.get("phone_number") or ""))
    if not patient:
        await bot_service._send_message(chat_id, TELEGRAM_PATIENT_NOT_FOUND_MESSAGE, TELEGRAM_MAIN_MENU)
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
        await bot_service._send_message(chat_id, TELEGRAM_TICKET_QR_LINK_FAILED_MESSAGE, TELEGRAM_MAIN_MENU)
        return True

    await bot_service._send_message(
        chat_id,
        f"{TELEGRAM_CONTACT_LINKED_MESSAGE}\nПациент: {_patient_display_name(patient)}",
        TELEGRAM_MAIN_MENU,
    )
    return True


async def _handle_clinic_bot_update(
    update: Dict[str, Any], db: Session, bot_service
) -> bool:
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
    normalized_text = text.lower()

    if command == "/start":
        _upsert_ticket_qr_telegram_user(db, message)
        db.commit()
        await _send_clinic_welcome(bot_service, chat_id)
        return True

    if command == "/help" or normalized_text == "помощь":
        await bot_service._send_message(
            chat_id,
            (
                "Команды бота:\n"
                "/start - главное меню\n"
                "/profile - статус привязки\n"
                "/results - информация о результатах\n\n"
                "Для привязки можно отсканировать QR с чека или нажать "
                "\"Поделиться номером\"."
            ),
            TELEGRAM_MAIN_MENU,
        )
        return True

    if command == "/profile" or normalized_text == "мой статус":
        await bot_service._send_message(chat_id, _clinic_status_message(db, chat_id), TELEGRAM_MAIN_MENU)
        return True

    if command == "/results" or normalized_text == "результаты":
        await bot_service._send_message(chat_id, _clinic_results_message(db, chat_id), TELEGRAM_MAIN_MENU)
        return True

    if normalized_text == "поделиться номером":
        await bot_service._send_message(chat_id, TELEGRAM_SHARE_CONTACT_MESSAGE, TELEGRAM_MAIN_MENU)
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
