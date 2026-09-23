"""
API эндпоинты для QR очередей

ACTIVE: Этот модуль содержит активные, рекомендуемые endpoints для работы с очередями.

Основные возможности:
- Генерация QR токенов (специалист/клиника)
- Session-based присоединение к очереди (двухэтапный процесс)
- Управление записями в очереди
- Аналитика и статистика
- Административные функции

Префикс: /api/v1/queue/*

Для legacy endpoints см.: queue.py (DEPRECATED)
Для переупорядочения очереди см.: queue_reorder.py

Документация:
- docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md - Migration guide
- docs/QUEUE_SYSTEM_ARCHITECTURE.md - Архитектура системы
"""

import logging  # noqa: F401
import re  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import (  # noqa: F401
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import get_db, require_roles  # noqa: F401
from app.models.user import User  # noqa: F401

logger = logging.getLogger(__name__)


def _queue_phone_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _queue_phone_matches(left: Any, right: Any) -> bool:
    left_digits = _queue_phone_digits(left)
    right_digits = _queue_phone_digits(right)
    if not left_digits or not right_digits:
        return False
    if left_digits == right_digits:
        return True

    shortest = min(len(left_digits), len(right_digits))
    return shortest >= 9 and (
        left_digits.endswith(right_digits) or right_digits.endswith(left_digits)
    )

# NOTE: Doctor импортируется внутри функций для избежания circular dependency
QUEUE_DOCTOR_MUTATION_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "cardiologist",
    "derma",
    "dermatologist",
    "dentist",
}


def _role_name(user: User) -> str:
    role = getattr(user, "role", "")
    return str(getattr(role, "value", role) or "")


def _ensure_doctor_can_mutate_specialist_queue(
    db: Session,
    *,
    specialist_id: int | None,
    current_user: User,
) -> None:
    if _role_name(current_user).strip().lower() not in QUEUE_DOCTOR_MUTATION_ROLES:
        return

    from app.models.clinic import Doctor

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor or specialist_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


def _ensure_doctor_can_mutate_queue_entry(
    db: Session,
    *,
    entry: Any,
    current_user: User,
) -> None:
    queue = getattr(entry, "queue", None)
    _ensure_doctor_can_mutate_specialist_queue(
        db,
        specialist_id=getattr(queue, "specialist_id", None),
        current_user=current_user,
    )


from app.services.qr_queue_service import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    QRQueueService,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.services.queue_service import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    QueueNotFoundError,
    QueueValidationError,
    queue_service,
)
from app.services.queue_session import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    get_or_create_session_id,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.services.service_mapping import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    get_queue_group_for_service,
    get_service_code,
)

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class QRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию QR токена"""

    specialist_id: int = Field(..., description="ID специалиста")
    department: str = Field(..., description="Отделение")
    expires_hours: int = Field(
        default=24, ge=1, le=168, description="Время жизни токена в часах"
    )
    target_date: str | None = Field(
        None, description="Целевая дата для очереди (YYYY-MM-DD)"
    )
    visit_type: str = Field(
        default="paid", description="Тип визита: paid, repeat, benefit"
    )


class ClinicQRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию общего QR токена клиники"""

    target_date: str | None = Field(
        None, description="Целевая дата для очереди (YYYY-MM-DD)"
    )
    expires_hours: int = Field(
        default=24, ge=1, le=168, description="Время жизни токена в часах"
    )


class QRTokenResponse(BaseModel):
    """Ответ с QR токеном"""

    token: str
    qr_url: str
    qr_code_base64: str
    specialist_id: int
    department: str
    expires_at: str
    active: bool


class QRTokenInfoResponse(BaseModel):
    """Информация о QR токене"""

    token: str
    specialist_id: int | None = None  # None для общего QR клиники
    specialist_name: str
    department: str
    department_name: str
    queue_length: int
    queue_active: bool
    expires_at: str | None = None
    is_clinic_wide: bool | None = False  # Флаг общего QR
    target_date: str | None = None  # Дата очереди
    selectable_specialists: list[dict[str, Any]] | None = None
    allowed: bool | None = None
    status: str | None = None
    message: str | None = None


class JoinSessionStartRequest(BaseModel):
    """Запрос на начало сессии присоединения"""

    token: str = Field(..., description="QR токен")


class JoinSessionStartResponse(BaseModel):
    """Ответ с данными сессии"""

    session_token: str
    expires_at: str
    queue_info: dict[str, Any]
    # Round-6 (PR #3362 review, P1-3): the server-computed attempt-identity
    # horizon. ``target_date`` is the queue-day the token is bound to
    # (tomorrow when the start happened after the cutoff);
    # ``attempt_expires_at`` is the end of THAT day in the clinic timezone
    # plus a safety grace — the earliest instant the client may drop the
    # attempt envelope. Both optional/nullable for older token shapes.
    target_date: str | None = Field(
        None, description="Целевая дата очереди токена (YYYY-MM-DD)"
    )
    attempt_expires_at: str | None = Field(
        None,
        description=(
            "Абсолютный horizon (ISO-8601, UTC) жизни идентичности попытки: "
            "конец целевого queue-day в timezone клиники + safety grace"
        ),
    )


class JoinSessionRefusalDetail(BaseModel):
    """Один per-specialist отказ аллокатора (round-6, P2-1)."""

    specialist_id: int | None = Field(
        None, description="ID выбора (Doctor.id или QueueProfile.id); None для одиночного пути"
    )
    error: str = Field(..., description="Человекочитаемое сообщение домена")


class JoinSessionRefusalResponse(BaseModel):
    """Структурированный отказ complete-попытки (round-6, P2-1/P2-2).

    400 — session-state / pre-execution refusals (incl. the
    rollback-proven ``join_session_not_executed``); 409 — immutable
    payload mismatch. ``reason`` vocabulary:
    join_session_not_found | join_session_expired | join_session_processing |
    join_session_used | join_session_payload_mismatch | join_session_not_executed.
    """

    reason: str = Field(..., description="Машиночитаемая причина отказа")
    message: str = Field(..., description="Человекочитаемое сообщение")
    details: list[JoinSessionRefusalDetail] | None = Field(
        None, description="Per-specialist ошибки (только для join_session_not_executed)"
    )


class JoinSessionRefusalErrorResponse(BaseModel):
    """Полное HTTP-тело отказа complete-попытки (round-9, review P2-1).

    Runtime raises ``HTTPException(detail={reason, message[, details]})``,
    so FastAPI serves the refusal wrapped in the standard ``detail``
    envelope: ``{"detail": {"reason": ..., "message": ...}}``. The
    frontend reads ``response.data.detail.reason`` — the declared OpenAPI
    contract must describe EXACTLY that wire format, so 400/409 reference
    THIS wrapper (not the bare inner payload).
    """

    detail: JoinSessionRefusalResponse


class JoinSessionCompleteRequest(BaseModel):
    """Запрос на завершение сессии присоединения"""

    session_token: str = Field(..., description="Токен сессии")
    patient_name: str = Field(
        ..., min_length=2, max_length=200, description="ФИО пациента"
    )
    phone: str = Field(..., min_length=5, max_length=20, description="Номер телефона")
    telegram_id: int | None = Field(None, description="Telegram ID")
    specialist_ids: list[int] | None = Field(
        None, description="Список ID специалистов (для общего QR)"
    )
    specialist_entity_types: list[str] | None = Field(
        None,
        description=(
            "Типы сущностей specialist_ids, выровненные по индексам "
            "('doctor' | 'profile'); тип выбора передаётся явно (D-01), "
            "тип сущности не определяется по совпадению числового ID"
        ),
    )


class JoinSessionCompleteMultipleResponse(BaseModel):
    """Ответ с результатом присоединения к нескольким очередям"""

    success: bool
    queue_time: str
    entries: list[dict[str, Any]]
    errors: list[dict[str, Any]] | None = None
    message: str
    # Round-4 (PR #3362, P1-2): True — the saved result of an ALREADY
    # joined session was re-served (the retry after a lost response reused
    # the original attempt identity); no second business action happened.
    replayed: bool = False


class JoinSessionCompleteResponse(BaseModel):
    """Ответ с результатом присоединения"""

    success: bool
    queue_number: int
    queue_length: int
    estimated_wait_time: int
    specialist_name: str
    department: str
    # Round-4 (PR #3362, P1-2): idempotent replay marker (see the multi
    # response) — same session token re-served its saved ticket result.
    replayed: bool = False


class QueueStatusResponse(BaseModel):
    """Статус очереди"""

    active: bool
    queue_length: int
    current_number: int | None
    entries: list[dict[str, Any]]


class CallNextPatientResponse(BaseModel):
    """Ответ на вызов следующего пациента"""

    success: bool
    message: str | None = None
    patient: dict[str, Any] | None = None
    queue_length: int | None = None


class ActiveQRTokenResponse(BaseModel):
    """Активный QR токен"""

    token: str
    specialist_id: int
    department: str
    created_at: str
    expires_at: str
    sessions_count: int
    successful_joins: int
    qr_url: str


class CancelServiceRequest(BaseModel):
    """Запрос на отмену услуги"""

    service_id: int = Field(..., description="ID услуги для отмены")
    cancel_reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Причина отмены (минимум 5 символов)",
    )
    was_paid: bool = Field(
        default=False, description="Была ли услуга оплачена до отмены"
    )


class CancelServiceResponse(BaseModel):
    """Ответ на отмену услуги"""

    success: bool
    message: str
    cancelled_service: dict[str, Any]
    new_total_amount: int


# ===================== ЭНДПОИНТЫ =====================


