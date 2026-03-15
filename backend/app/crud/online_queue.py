"""
CRUD операции для онлайн-очереди согласно detail.md стр. 224-257

============================================================================
⚠️ TRANSITIONAL: Mixed CRUD + Business Logic (Legacy)
============================================================================

WARNING: This file contains a mix of CRUD operations and business logic.

Current State:
  - Contains both DB queries (CRUD) and business logic
  - Used by 8 endpoints for backward compatibility
  - Imports queue_service but also duplicates some functionality

For NEW Features:
  ✅ USE: app/services/queue_service.py (QueueBusinessService - SSOT)
  ❌ AVOID: Adding new business logic to this file

Migration Path:
  - New endpoints should use queue_service.py directly
  - Existing endpoints will be gradually migrated
  - This file will eventually contain only pure CRUD operations

See Also:
  - app/services/queue_service.py (SSOT for business logic)
  - docs/QUEUE_SYSTEM_ARCHITECTURE.md (architecture guide)
============================================================================
"""

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.crud.clinic import get_queue_settings
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.services.queue_service import queue_service  # ✅ SSOT for business logic

logger = logging.getLogger(__name__)


# ===================== ВСТУПЛЕНИЕ В ОЧЕРЕДЬ =====================


def join_online_queue(
    db: Session,
    token: str,
    phone: str | None = None,
    telegram_id: int | None = None,
    patient_name: str | None = None,
) -> dict[str, Any]:
    """
    Вступление в онлайн-очередь
    Из detail.md стр. 235: POST /api/online-queue/join { token, phone?, telegram_id? } → номер
    """

    # Проверяем токен
    queue_token = (
        db.query(QueueToken)
        .filter(and_(QueueToken.token == token, QueueToken.active == True))
        .first()
    )

    if not queue_token:
        return {
            "success": False,
            "error_code": "INVALID_TOKEN",
            "message": "Неверный или истекший токен QR кода",
        }

    # Проверяем срок действия токена
    # SQLite возвращает naive datetime в локальном времени
    # Сравниваем с текущим временем в локальном timezone
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
    now_local = datetime.now(timezone).replace(tzinfo=None)

    if now_local > queue_token.expires_at:
        return {
            "success": False,
            "error_code": "TOKEN_EXPIRED",
            "message": "Срок действия QR кода истек",
        }

    # Получаем дневную очередь
    daily_queue = (
        db.query(DailyQueue)
        .filter(
            and_(
                DailyQueue.day == queue_token.day,
                DailyQueue.specialist_id == queue_token.specialist_id,
                DailyQueue.active == True,
            )
        )
        .first()
    )

    if not daily_queue:
        return {
            "success": False,
            "error_code": "QUEUE_NOT_FOUND",
            "message": "Очередь не найдена",
        }

    # Проверяем что очередь еще не открыта (opened_at == None)
    if daily_queue.opened_at:
        return {
            "success": False,
            "error_code": "QUEUE_CLOSED",
            "message": "Онлайн-набор закрыт. Обратитесь в регистратуру.",
            "queue_closed": True,
        }

    # Получаем настройки очереди
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))

    # Проверяем рабочие часы (с 07:00)
    current_time = datetime.now(timezone)
    queue_start_hour = queue_settings.get("queue_start_hour", 7)

    if current_time.hour < queue_start_hour:
        return {
            "success": False,
            "error_code": "OUTSIDE_HOURS",
            "message": f"Онлайн-запись доступна с {queue_start_hour}:00",
            "outside_hours": True,
        }

    # Проверяем дубликат по телефону или telegram_id
    existing_entry = None
    if phone:
        existing_entry = (
            db.query(OnlineQueueEntry)
            .filter(
                and_(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.phone == phone,
                )
            )
            .first()
        )
    elif telegram_id:
        existing_entry = (
            db.query(OnlineQueueEntry)
            .filter(
                and_(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.telegram_id == telegram_id,
                )
            )
            .first()
        )

    if existing_entry:
        # Возвращаем существующий номер
        return {
            "success": True,
            "number": existing_entry.number,
            "duplicate": True,
            "message": f"Вы уже записаны под номером {existing_entry.number}",
            "specialist_name": (
                queue_token.specialist.user.full_name
                if queue_token.specialist.user
                else "Врач"
            ),
            "cabinet": queue_token.specialist.cabinet,
        }

    # Проверяем лимит мест (приоритет: индивидуальный лимит врача -> настройки специальности -> по умолчанию)
    current_count = (
        db.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
    )

    # Сначала проверяем индивидуальный лимит врача на этот день
    if daily_queue.max_online_entries is not None:
        max_slots = daily_queue.max_online_entries
    else:
        # Иначе используем настройки специальности
        max_slots = queue_settings.get("max_per_day", {}).get(
            queue_token.specialist.specialty, 15
        )

    if current_count >= max_slots:
        return {
            "success": False,
            "error_code": "QUEUE_FULL",
            "message": f"Все места заняты ({max_slots}/{max_slots})",
            "queue_full": True,
        }

    queue_tag_hint = None
    if queue_token.specialist and getattr(queue_token.specialist, "specialty", None):
        queue_tag_hint = queue_token.specialist.specialty
    elif queue_token.department:
        queue_tag_hint = queue_token.department

    next_number = queue_service.get_next_queue_number(
        db,
        daily_queue=daily_queue,
        queue_tag=queue_tag_hint,
    )

    logger.info(
        "[join_online_queue] next_number (SSOT) = %d, queue_tag=%s",
        next_number,
        queue_tag_hint,
    )

    # Создаем запись в очереди
    # queue_time - бизнес-время регистрации, не меняется при редактировании
    queue_time = datetime.now(timezone)
    queue_entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=next_number,
        patient_name=patient_name,
        phone=phone,
        telegram_id=telegram_id,
        source="online",
        status="waiting",
        queue_time=queue_time,  # Устанавливаем время регистрации
    )
    db.add(queue_entry)

    # Увеличиваем счетчик использования токена
    queue_token.usage_count += 1

    db.commit()
    db.refresh(queue_entry)

    return {
        "success": True,
        "number": queue_entry.number,
        "duplicate": False,
        "message": f"Ваш номер в очереди: {queue_entry.number}",
        "specialist_name": (
            queue_token.specialist.user.full_name
            if queue_token.specialist.user
            else "Врач"
        ),
        "cabinet": queue_token.specialist.cabinet,
        "estimated_time": f"Примерно в {queue_start_hour + 2}:00",
    }


def join_online_queue_multiple(
    db: Session,
    token: str,
    specialist_ids: list[int],
    phone: str | None = None,
    telegram_id: int | None = None,
    patient_name: str | None = None,
) -> dict[str, Any]:
    """
    Вступление в онлайн-очередь для нескольких специалистов одновременно
    Создает отдельные записи OnlineQueueEntry для каждого специалиста с одинаковым queue_time
    """

    # Проверяем токен (может быть общий QR клиники)
    queue_token = (
        db.query(QueueToken)
        .filter(and_(QueueToken.token == token, QueueToken.active == True))
        .first()
    )

    if not queue_token:
        return {
            "success": False,
            "error_code": "INVALID_TOKEN",
            "message": "Неверный или истекший токен QR кода",
        }

    # Проверяем срок действия токена
    # SQLite возвращает naive datetime в локальном времени
    # Сравниваем с текущим временем в локальном timezone
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
    now_local = datetime.now(timezone).replace(tzinfo=None)

    if now_local > queue_token.expires_at:
        return {
            "success": False,
            "error_code": "TOKEN_EXPIRED",
            "message": "Срок действия QR кода истек",
        }

    # Валидация: должен быть выбран хотя бы один специалист
    if not specialist_ids or len(specialist_ids) == 0:
        return {
            "success": False,
            "error_code": "NO_SPECIALISTS",
            "message": "Выберите хотя бы одного специалиста",
        }

    # Получаем настройки очереди
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))

    # Проверяем рабочие часы
    current_time = datetime.now(timezone)
    queue_start_hour = queue_settings.get("queue_start_hour", 7)

    if current_time.hour < queue_start_hour:
        return {
            "success": False,
            "error_code": "OUTSIDE_HOURS",
            "message": f"Онлайн-запись доступна с {queue_start_hour}:00",
            "outside_hours": True,
        }

    # queue_time одинаковое для всех записей (ранняя регистрация)
    queue_time = datetime.now(timezone)

    # Результаты для каждого специалиста
    results = []
    errors = []

    # Создаем записи для каждого специалиста
    logger.info(
        "[join_online_queue_multiple] Начинаем создание записей для %d специалистов: %s",
        len(specialist_ids),
        specialist_ids,
    )
    for specialist_id in specialist_ids:
        try:
            logger.info(
                "[join_online_queue_multiple] Обрабатываем specialist_id=%d",
                specialist_id,
            )
            # Получаем или создаем дневную очередь для специалиста
            daily_queue = (
                db.query(DailyQueue)
                .filter(
                    and_(
                        DailyQueue.day == queue_token.day,
                        DailyQueue.specialist_id == specialist_id,
                        DailyQueue.active == True,
                    )
                )
                .first()
            )

            if not daily_queue:
                logger.info(
                    "[join_online_queue_multiple] DailyQueue не найдена для specialist_id=%d, создаем новую",
                    specialist_id,
                )
                # Создаем очередь если не существует
                daily_queue = DailyQueue(
                    day=queue_token.day, specialist_id=specialist_id, active=True
                )
                db.add(daily_queue)
                db.commit()
                db.refresh(daily_queue)
                logger.info(
                    "[join_online_queue_multiple] Создана DailyQueue id=%d для specialist_id=%d",
                    daily_queue.id,
                    specialist_id,
                )
            else:
                logger.info(
                    "[join_online_queue_multiple] Найдена DailyQueue id=%d для specialist_id=%d",
                    daily_queue.id,
                    specialist_id,
                )

            # Проверяем что очередь еще не открыта
            if daily_queue.opened_at:
                errors.append(
                    {
                        "specialist_id": specialist_id,
                        "error": "QUEUE_CLOSED",
                        "message": "Онлайн-набор закрыт для этого специалиста",
                    }
                )
                continue

            # Проверяем дубликат по телефону в этой очереди
            existing_entry = None
            if phone:
                existing_entry = (
                    db.query(OnlineQueueEntry)
                    .filter(
                        and_(
                            OnlineQueueEntry.queue_id == daily_queue.id,
                            OnlineQueueEntry.phone == phone,
                        )
                    )
                    .first()
                )

            if existing_entry:
                # Уже записан в эту очередь
                results.append(
                    {
                        "specialist_id": specialist_id,
                        "number": existing_entry.number,
                        "duplicate": True,
                        "message": f"Вы уже записаны под номером {existing_entry.number}",
                    }
                )
                continue

            # Проверяем лимит мест
            current_count = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == daily_queue.id)
                .count()
            )

            max_slots = daily_queue.max_online_entries or queue_settings.get(
                "max_per_day", {}
            ).get("default", 15)

            if current_count >= max_slots:
                errors.append(
                    {
                        "specialist_id": specialist_id,
                        "error": "QUEUE_FULL",
                        "message": f"Все места заняты ({max_slots}/{max_slots})",
                    }
                )
                continue

            doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
            queue_tag_hint = doctor.specialty if doctor and doctor.specialty else None
            next_number = queue_service.get_next_queue_number(
                db,
                daily_queue=daily_queue,
                queue_tag=queue_tag_hint,
            )

            logger.info(
                "[join_online_queue_multiple] specialist_id=%d, queue_tag=%s, next_number=%d",
                specialist_id,
                queue_tag_hint,
                next_number,
            )

            # ✅ УЛУЧШЕНИЕ: Находим или создаем пациента по телефону
            # Используем единые функции из crud.patient для обеспечения Single Source of Truth
            patient_id = None
            if phone:
                from app.crud.patient import (
                    find_or_create_patient,
                    find_patient,
                )

                # Ищем существующего пациента
                existing_patient = find_patient(db, phone=phone)

                if existing_patient:
                    patient_id = existing_patient.id
                    logger.info(
                        "[join_online_queue_multiple] Найден существующий пациент ID=%d для телефона %s",
                        patient_id,
                        phone,
                    )
                else:
                    # ✅ ИСПРАВЛЕНО: Передаем full_name в find_or_create_patient для нормализации
                    # find_or_create_patient сам выполнит нормализацию, не нужно делать это дважды
                    new_patient = find_or_create_patient(
                        db,
                        {
                            "phone": phone,
                            "full_name": patient_name,  # Передаем full_name для нормализации внутри find_or_create_patient
                        },
                    )
                    patient_id = new_patient.id
                    logger.info(
                        "[join_online_queue_multiple] ✅ Создан новый пациент ID=%d для телефона %s",
                        patient_id,
                        phone,
                    )

            # Создаем запись в очереди с одинаковым queue_time
            queue_entry = OnlineQueueEntry(
                queue_id=daily_queue.id,
                number=next_number,
                patient_id=patient_id,  # ✅ Теперь связываем с пациентом
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id,
                source="online",
                status="waiting",
                queue_time=queue_time,  # Одинаковое время для всех записей
            )
            db.add(queue_entry)
            db.flush()  # Получаем ID записи
            logger.info(
                "[join_online_queue_multiple] ✅ Создана OnlineQueueEntry id=%d для specialist_id=%d, queue_id=%d, number=%d, patient_id=%s",
                queue_entry.id,
                specialist_id,
                daily_queue.id,
                next_number,
                patient_id,
            )

            # Получаем информацию о специальности для иконки
            specialty_icon_map = {
                'cardiology': '❤️',
                'cardio': '❤️',
                'dermatology': '✨',
                'derma': '✨',
                'dentistry': '🦷',
                'dentist': '🦷',
                'laboratory': '🔬',
                'lab': '🔬',
            }
            doctor_specialty = (
                doctor.specialty.lower() if doctor and doctor.specialty else ''
            )
            icon = next(
                (
                    icon
                    for key, icon in specialty_icon_map.items()
                    if key in doctor_specialty
                ),
                '👨‍⚕️',
            )

            results.append(
                {
                    "specialist_id": specialist_id,
                    "specialist_name": (
                        doctor.user.full_name
                        if doctor and doctor.user
                        else f"Врач #{specialist_id}"
                    ),
                    "department": doctor.specialty if doctor else None,
                    "number": next_number,
                    "queue_id": daily_queue.id,
                    "queue_time": queue_time.isoformat(),
                    "icon": icon,
                    "duplicate": False,
                }
            )
            logger.info(
                "[join_online_queue_multiple] ✅ Добавлен результат для specialist_id=%d: number=%d, queue_id=%d",
                specialist_id,
                next_number,
                daily_queue.id,
            )

        except Exception as e:
            errors.append(
                {
                    "specialist_id": specialist_id,
                    "error": "INTERNAL_ERROR",
                    "message": str(e),
                }
            )

    # Увеличиваем счетчик использования токена
    queue_token.usage_count += 1

    db.commit()

    # Формируем итоговый ответ
    if len(results) > 0:
        return {
            "success": True,
            "queue_time": queue_time.isoformat(),
            "entries": results,
            "errors": errors if errors else None,
            "message": f"Вы записаны к {len(results)} специалистам",
        }
    else:
        return {
            "success": False,
            "error_code": "ALL_FAILED",
            "errors": errors,
            "message": "Не удалось записаться ни к одному специалисту",
        }


# ===================== ОТКРЫТИЕ ПРИЕМА =====================


def open_daily_queue(
    db: Session, day: date, specialist_id: int, user_id: int | None = None
) -> dict[str, Any]:
    """
    Открытие приема и закрытие онлайн-набора
    Из detail.md стр. 253: POST /api/online-queue/open?day&specialist_id
    """

    # Получаем дневную очередь
    daily_queue = (
        db.query(DailyQueue)
        .filter(and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id))
        .first()
    )

    if not daily_queue:
        # Создаем очередь если не существует
        daily_queue = DailyQueue(day=day, specialist_id=specialist_id, active=True)
        db.add(daily_queue)

    # Отмечаем время открытия
    if not daily_queue.opened_at:
        daily_queue.opened_at = datetime.utcnow()

    db.commit()
    db.refresh(daily_queue)

    # Подсчитываем онлайн-записи
    online_entries_count = (
        db.query(OnlineQueueEntry)
        .filter(
            and_(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.source == "online",
            )
        )
        .count()
    )

    return {
        "success": True,
        "message": "Прием открыт. Онлайн-набор закрыт.",
        "opened_at": daily_queue.opened_at,
        "online_entries_count": online_entries_count,
        "closed_online_registration": True,
    }


# ===================== ПОЛУЧЕНИЕ СОСТОЯНИЯ ОЧЕРЕДИ =====================


def get_queue_status(db: Session, day: date, specialist_id: int) -> dict[str, Any]:
    """Получить статус очереди"""

    # Получаем очередь
    daily_queue = (
        db.query(DailyQueue)
        .filter(and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id))
        .first()
    )

    if not daily_queue:
        return {"queue_exists": False, "queue_open": False, "entries_count": 0}

    # Подсчитываем записи
    total_entries = (
        db.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
    )
    waiting_entries = (
        db.query(OnlineQueueEntry)
        .filter(
            and_(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status == "waiting",
            )
        )
        .count()
    )

    return {
        "queue_exists": True,
        "queue_open": daily_queue.opened_at is not None,
        "opened_at": daily_queue.opened_at,
        "total_entries": total_entries,
        "waiting_entries": waiting_entries,
        "queue_id": daily_queue.id,
    }


# ===================== ПРОВЕРКА РАБОЧИХ ЧАСОВ =====================


def check_queue_availability(
    db: Session, day: date, specialist_id: int
) -> dict[str, Any]:
    """
    Проверка доступности онлайн-очереди
    Из detail.md стр. 238-246: правила доступности
    """

    # Получаем настройки
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))

    # Текущее время в часовом поясе клиники
    current_time = datetime.now(timezone)
    queue_start_hour = queue_settings.get("queue_start_hour", 7)

    # Проверяем дату
    if day < date.today():
        return {
            "available": False,
            "reason": "DATE_PAST",
            "message": "Нельзя записаться на прошедшую дату",
        }

    # Если сегодня, проверяем время
    if day == date.today():
        if current_time.hour < queue_start_hour:
            return {
                "available": False,
                "reason": "TOO_EARLY",
                "message": f"Онлайн-запись доступна с {queue_start_hour}:00",
                "available_from": f"{queue_start_hour}:00",
            }

    # Проверяем что очередь не открыта
    daily_queue = (
        db.query(DailyQueue)
        .filter(and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id))
        .first()
    )

    if daily_queue and daily_queue.opened_at:
        return {
            "available": False,
            "reason": "QUEUE_OPENED",
            "message": "Онлайн-набор закрыт. Обратитесь в регистратуру.",
            "opened_at": daily_queue.opened_at,
        }

    # Проверяем лимит мест
    if daily_queue:
        current_count = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == daily_queue.id)
            .count()
        )

        # Приоритет: индивидуальный лимит врача -> настройки специальности -> по умолчанию
        if daily_queue.max_online_entries is not None:
            max_slots = daily_queue.max_online_entries
        else:
            doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
            max_slots = queue_settings.get("max_per_day", {}).get(doctor.specialty, 15)

        if current_count >= max_slots:
            return {
                "available": False,
                "reason": "QUEUE_FULL",
                "message": f"Все места заняты ({current_count}/{max_slots})",
            }

    return {"available": True, "message": "Онлайн-запись доступна"}


# ===================== ПОИСК ДУБЛИКАТОВ =====================


def find_existing_entry(
    db: Session,
    queue_id: int,
    phone: str | None = None,
    telegram_id: int | None = None,
) -> OnlineQueueEntry | None:
    """
    Поиск существующей записи по телефону или Telegram ID
    Из detail.md стр. 241: "Один номер на телефон или Telegram‑чат"
    """

    if phone:
        return (
            db.query(OnlineQueueEntry)
            .filter(
                and_(
                    OnlineQueueEntry.queue_id == queue_id,
                    OnlineQueueEntry.phone == phone,
                )
            )
            .first()
        )
    elif telegram_id:
        return (
            db.query(OnlineQueueEntry)
            .filter(
                and_(
                    OnlineQueueEntry.queue_id == queue_id,
                    OnlineQueueEntry.telegram_id == telegram_id,
                )
            )
            .first()
        )

    return None


# ===================== ВАЛИДАЦИЯ ТОКЕНА =====================


def validate_queue_token(
    db: Session, token: str
) -> tuple[bool, QueueToken | None, str]:
    """Валидация QR токена"""

    queue_token = (
        db.query(QueueToken)
        .filter(and_(QueueToken.token == token, QueueToken.active == True))
        .first()
    )

    if not queue_token:
        return False, None, "Неверный токен QR кода"

    # SQLite возвращает naive datetime в локальном времени
    # Сравниваем с текущим временем в локальном timezone
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
    now_local = datetime.now(timezone).replace(tzinfo=None)

    if now_local > queue_token.expires_at:
        return False, queue_token, "Срок действия QR кода истек"

    return True, queue_token, "Токен валиден"


# ===================== СТАТИСТИКА ОЧЕРЕДИ =====================


def get_or_create_daily_queue(
    db: Session,
    day: date,
    specialist_id: int,
    queue_tag: str | None = None,
    cabinet_number: str | None = None,
    cabinet_floor: int | None = None,
    cabinet_building: str | None = None,
) -> DailyQueue:
    """
    Получить или создать дневную очередь с поддержкой queue_tag и информации о кабинете
    Теперь очереди уникальны по (day, specialist_id, queue_tag)

    ⭐ ВАЖНО: DailyQueue.specialist_id хранит doctors.id.
    Для совместимости helper принимает как doctors.id, так и doctors.user_id,
    но всегда канонизирует значение к doctor.id перед чтением/записью.
    """
    doctor = db.query(Doctor).filter(Doctor.user_id == specialist_id).first()
    if not doctor:
        doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
    if not doctor:
        raise ValueError(
            f"Doctor with id or user_id {specialist_id} does not exist in doctors table"
        )

    actual_specialist_id = doctor.id

    # Ищем очередь с учетом queue_tag
    query_filters = [DailyQueue.day == day, DailyQueue.specialist_id == actual_specialist_id]

    if queue_tag:
        query_filters.append(DailyQueue.queue_tag == queue_tag)
    else:
        query_filters.append(DailyQueue.queue_tag.is_(None))

    daily_queue = db.query(DailyQueue).filter(and_(*query_filters)).first()

    if not daily_queue:
        # Если информация о кабинете не передана, получаем из таблицы doctors
        if not cabinet_number and doctor.cabinet:
            cabinet_number = doctor.cabinet

        daily_queue = DailyQueue(
            day=day,
            specialist_id=actual_specialist_id,
            queue_tag=queue_tag,
            cabinet_number=cabinet_number,
            cabinet_floor=cabinet_floor,
            cabinet_building=cabinet_building,
            active=True,
        )
        db.add(daily_queue)
        db.commit()
        db.refresh(daily_queue)
    else:
        # Обновляем информацию о кабинете, если она была передана
        updated = False
        if cabinet_number and daily_queue.cabinet_number != cabinet_number:
            daily_queue.cabinet_number = cabinet_number
            updated = True
        if cabinet_floor is not None and daily_queue.cabinet_floor != cabinet_floor:
            daily_queue.cabinet_floor = cabinet_floor
            updated = True
        if cabinet_building and daily_queue.cabinet_building != cabinet_building:
            daily_queue.cabinet_building = cabinet_building
            updated = True

        if updated:
            db.commit()
            db.refresh(daily_queue)

    return daily_queue


def count_queue_entries(db: Session, queue_id: int) -> int:
    """
    Подсчёт записей в очереди
    """
    return (
        db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == queue_id).count()
    )


def get_queue_statistics(
    db: Session, day: date, specialist_id: int | None = None
) -> dict[str, Any]:
    """Статистика очереди за день"""

    query = db.query(DailyQueue).filter(DailyQueue.day == day)

    if specialist_id:
        query = query.filter(DailyQueue.specialist_id == specialist_id)

    queues = query.all()

    total_entries = 0
    online_entries = 0
    served_entries = 0

    for queue in queues:
        entries = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue.id)
            .all()
        )
        total_entries += len(entries)
        online_entries += len([e for e in entries if e.source == "online"])
        served_entries += len([e for e in entries if e.status == "served"])

    return {
        "day": day,
        "total_queues": len(queues),
        "total_entries": total_entries,
        "online_entries": online_entries,
        "served_entries": served_entries,
        "queues": [
            {
                "specialist_id": q.specialist_id,
                "specialist_name": (
                    q.specialist.user.full_name
                    if q.specialist.user
                    else f"Врач #{q.specialist_id}"
                ),
                "opened_at": q.opened_at,
                "entries_count": db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == q.id)
                .count(),
            }
            for q in queues
        ],
    }
