"""
Сервис для бизнес-логики очереди
"""

from __future__ import annotations

import copy
import logging
import secrets
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.crud.clinic import get_queue_settings
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.user import User
from app.models.visit import Visit
from app.services.queue_session import (
    get_or_create_session_id,
)

logger = logging.getLogger(__name__)


class QueueError(Exception):
    """Базовое исключение для сервиса очереди."""


class QueueValidationError(QueueError):
    """Ошибки валидации входных данных."""


class QueueConflictError(QueueError):
    """Конфликты (дубликаты, лимиты, блокировки)."""


class QueueNotFoundError(QueueError):
    """Запрашиваемая очередь или запись не найдены."""


class QueueBusinessService:
    """Сервис для управления бизнес-логикой очереди"""

    # Стартовые номера по специальностям (согласно MASTER TODO LIST)
    SPECIALTY_START_NUMBERS = {
        "cardio": 1,  # Кардиолог - с №1
        "derma": 15,  # Дерматолог - с №15
        "dental": 3,  # Стоматолог - с №3
        "general": 1,  # Общий врач - с №1
        "default": 1,  # По умолчанию - с №1
    }

    # Время работы онлайн-записи
    ONLINE_QUEUE_START_TIME = time(7, 0)  # 07:00

    # Лимиты по умолчанию
    DEFAULT_MAX_SLOTS = 15
    QUEUE_QR_TOKEN_MIN_TTL_MINUTES = 5
    QUEUE_QR_TOKEN_MAX_TTL_MINUTES = 15
    QR_HIDDEN_PROFILE_KEYS = {"ecg", "general"}
    QR_SPECIALTY_ALIASES = {
        "cardio": "cardiology",
        "derma": "dermatology",
        "dentist": "stomatology",
        "dentistry": "stomatology",
        "laboratory": "lab",
    }

    def __init__(self) -> None:
        self._cached_settings: dict[str, Any] | None = None

    @classmethod
    def _normalize_qr_specialty_key(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return cls.QR_SPECIALTY_ALIASES.get(normalized, normalized)

    @classmethod
    def _is_qr_visible_profile(cls, profile: Any) -> bool:
        key = cls._normalize_qr_specialty_key(getattr(profile, "key", None))
        return (
            bool(key)
            and key not in cls.QR_HIDDEN_PROFILE_KEYS
            and bool(getattr(profile, "is_active", False))
            and bool(getattr(profile, "show_on_qr_page", False))
        )

    @classmethod
    def _get_qr_visible_profile_for_doctor(cls, db: Session, doctor: Doctor):
        from app.models.queue_profile import QueueProfile

        doctor_specialty = cls._normalize_qr_specialty_key(
            getattr(doctor, "specialty", None)
        )
        if not doctor_specialty:
            return None

        profiles = (
            db.query(QueueProfile)
            .filter(
                QueueProfile.is_active == True,
                QueueProfile.show_on_qr_page == True,
            )
            .all()
        )
        for profile in profiles:
            if not cls._is_qr_visible_profile(profile):
                continue
            profile_keys = {
                cls._normalize_qr_specialty_key(profile.key),
                *(
                    cls._normalize_qr_specialty_key(tag)
                    for tag in (profile.queue_tags or [])
                ),
            }
            if doctor_specialty in profile_keys:
                return profile
        return None

    @staticmethod
    def _increment_token_usage(queue_token: QueueToken) -> None:
        """Унифицированно увеличивает счётчик использования QR-токена."""
        if hasattr(queue_token, "usage_count"):
            current = queue_token.usage_count or 0
            queue_token.usage_count = current + 1
        else:
            current = getattr(queue_token, "current_uses", 0) or 0
            queue_token.current_uses = current + 1

    @classmethod
    def _bounded_queue_token_ttl_minutes(cls, expires_hours: int | None) -> int:
        try:
            requested_minutes = (
                int(expires_hours) * 60
                if expires_hours is not None
                else cls.QUEUE_QR_TOKEN_MAX_TTL_MINUTES
            )
        except (TypeError, ValueError):
            requested_minutes = cls.QUEUE_QR_TOKEN_MAX_TTL_MINUTES

        return min(
            max(requested_minutes, cls.QUEUE_QR_TOKEN_MIN_TTL_MINUTES),
            cls.QUEUE_QR_TOKEN_MAX_TTL_MINUTES,
        )

    def _load_queue_settings(self, db: Session) -> dict[str, Any]:
        if self._cached_settings is None:
            self._cached_settings = get_queue_settings(db) or {}
        return self._cached_settings

    def get_local_timestamp(
        self, db: Session | None = None, timezone: str | None = None
    ) -> datetime:
        tz = timezone
        if tz is None and db is not None:
            settings = self._load_queue_settings(db)
            tz = settings.get("timezone")
        tz = tz or "Asia/Tashkent"
        try:
            zone = ZoneInfo(tz)
        except Exception:
            logger.warning("Unknown timezone '%s', falling back to Asia/Tashkent", tz)
            zone = ZoneInfo("Asia/Tashkent")
        return datetime.now(zone)

    def normalize_queue_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise QueueValidationError("Payload must be a dictionary")

        normalized = copy.deepcopy(payload)
        patient_name = (
            normalized.pop("full_name", None)
            or normalized.get("patient_name")
            or normalized.get("fio")
        )
        normalized["patient_name"] = patient_name.strip() if patient_name else None
        normalized["patient_id"] = normalized.get("patient_id")
        normalized["phone"] = normalized.get("phone")
        normalized["telegram_id"] = normalized.get("telegram_id")
        normalized["visit_id"] = normalized.get("visit_id")
        normalized["queue_tag"] = normalized.get("queue_tag")
        normalized["source"] = (normalized.get("source") or "desk").strip().lower()
        normalized.setdefault("services", [])
        normalized.setdefault("metadata", {})
        return normalized

    def validate_queue_input(self, payload: dict[str, Any]) -> None:
        if not payload.get("source"):
            raise QueueValidationError("source is required")

        if not payload.get("patient_name") and not payload.get("patient_id"):
            raise QueueValidationError(
                "Either patient_id or patient_name must be provided"
            )

    @classmethod
    def get_start_number_for_specialist(cls, specialist: User) -> int:
        """Получить стартовый номер для специалиста"""
        # Определяем специальность по роли или другим атрибутам
        specialty = cls._determine_specialty(specialist)
        return cls.SPECIALTY_START_NUMBERS.get(
            specialty, cls.SPECIALTY_START_NUMBERS["default"]
        )

    @classmethod
    def _determine_specialty(cls, specialist: User) -> str:
        """Определить специальность врача"""
        # Можно расширить логику определения специальности
        if hasattr(specialist, 'specialty'):
            return specialist.specialty.lower()

        # Пока используем роль или username
        username = specialist.username.lower()
        if 'cardio' in username or 'кардио' in username:
            return "cardio"
        elif 'derma' in username or 'дерма' in username:
            return "derma"
        elif 'dental' in username or 'стомат' in username:
            return "dental"
        else:
            return "general"

    @classmethod
    def check_queue_time_window(
        cls, target_date: date, queue_opened_at: datetime | None = None
    ) -> tuple[bool, str]:
        """
        Проверить, доступна ли онлайн-запись по времени

        Returns:
            (is_allowed, message)
        """
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        if target_date < today:
            return False, "❌ QR код устарел. Обратитесь в регистратуру за новым кодом."

        if target_date == today:
            # Проверяем время для сегодняшнего дня
            if current_time < cls.ONLINE_QUEUE_START_TIME:
                return (
                    False,
                    f"⏰ Онлайн-запись откроется в {cls.ONLINE_QUEUE_START_TIME.strftime('%H:%M')}. Текущее время: {current_time.strftime('%H:%M')}",
                )

            if queue_opened_at:
                opened_time = queue_opened_at.strftime('%H:%M')
                return (
                    False,
                    f"🚪 Прием уже открыт в {opened_time}. Онлайн-запись закрыта. Обратитесь в регистратуру.",
                )

        # Для будущих дней разрешаем запись
        return True, ""

    @classmethod
    def check_queue_limits(
        cls, db: Session, daily_queue: DailyQueue
    ) -> tuple[bool, str]:
        """
        Проверить лимиты очереди

        Returns:
            (is_allowed, message)
        """
        current_entries = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .count()
        )

        max_slots = getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS

        if current_entries >= max_slots:
            return (
                False,
                f"🚫 Достигнут лимит мест ({max_slots}). Обратитесь в регистратуру.",
            )

        return True, ""

    @classmethod
    def check_uniqueness(
        cls,
        db: Session,
        daily_queue: DailyQueue,
        phone: str | None = None,
        telegram_id: str | None = None,
        source: str = "online",  # ✅ Added source parameter
    ) -> tuple[OnlineQueueEntry | None, str]:
        """
        Проверить уникальность записи

        Returns:
            (existing_entry, duplicate_reason)
        """
        if not phone and not telegram_id:
            return None, ""

        # ✅ SKIP CHECK for trusted sources (desk, morning_assignment)
        # This allows registrars to add multiple services/appointments for the same patient
        # The uniqueness check is primarily for online/QR users to prevent spam
        # We need to pass 'source' to check_uniqueness or check it before calling
        # ✅ ALLOW DUPLICATES for trusted sources
        if source in ["desk", "morning_assignment"]:
            return None, ""

        if phone:
            phone_entry = (
                db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.phone == phone,
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .first()
            )

            if phone_entry:
                return phone_entry, f"телефону {phone}"

        # Проверяем по Telegram ID
        if telegram_id:
            telegram_entry = (
                db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.telegram_id == telegram_id,
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .first()
            )

            if telegram_entry:
                return telegram_entry, f"Telegram ID {telegram_id}"

        return None, ""

    @classmethod
    def calculate_next_number(cls, db: Session, daily_queue: DailyQueue) -> int:
        """Вычислить следующий номер в очереди"""
        max_number = (
            db.query(func.max(OnlineQueueEntry.number))
            .filter(OnlineQueueEntry.queue_id == daily_queue.id)
            .scalar()
        ) or 0

        start_number = getattr(
            daily_queue, "start_number", None
        ) or cls.SPECIALTY_START_NUMBERS.get("default", 1)
        return max(max_number + 1, start_number)

    @classmethod
    def get_queue_statistics(cls, db: Session, daily_queue: DailyQueue) -> dict:
        """Получить статистику очереди"""
        entries = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == daily_queue.id)
            .all()
        )

        stats = {
            "total_entries": len(entries),
            "waiting": len([e for e in entries if e.status == "waiting"]),
            "called": len([e for e in entries if e.status == "called"]),
            "completed": len([e for e in entries if e.status == "completed"]),
            "cancelled": len([e for e in entries if e.status == "cancelled"]),
            "max_slots": getattr(daily_queue, 'max_slots', None)
            or cls.DEFAULT_MAX_SLOTS,
            "available_slots": max(
                0,
                (getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS)
                - len([e for e in entries if e.status in ["waiting", "called"]]),
            ),
            "is_open": daily_queue.opened_at is not None,
            "opened_at": (
                daily_queue.opened_at.isoformat() if daily_queue.opened_at else None
            ),
        }

        return stats

    @classmethod
    def validate_queue_entry_data(
        cls,
        patient_name: str,
        phone: str | None = None,
        telegram_id: str | None = None,
    ) -> tuple[bool, str]:
        """Валидация данных записи в очередь"""
        if not patient_name or not patient_name.strip():
            return False, "❌ Укажите ваше ФИО"

        if not phone and not telegram_id:
            return False, "❌ Укажите телефон или Telegram ID"

        if phone:
            # Простая валидация телефона
            cleaned_phone = (
                phone.replace("+", "")
                .replace("-", "")
                .replace(" ", "")
                .replace("(", "")
                .replace(")", "")
            )
            if not cleaned_phone.isdigit() or len(cleaned_phone) < 9:
                return False, "❌ Неверный формат телефона"

        return True, ""

    # ----- Новые SSOT-функции (будут внедряться в следующих подэтапах) -----

    def get_or_create_daily_queue(
        self,
        db: Session,
        *,
        day: date,
        specialist_id: int,
        queue_tag: str | None = None,
        defaults: dict[str, Any] | None = None,
    ) -> DailyQueue:
        """
        Получить или создать ежедневную очередь

        Args:
            db: Database session
            day: Дата очереди
            specialist_id: ID врача (ForeignKey на doctors.id)
            queue_tag: Тег очереди (опционально)
            defaults: Значения по умолчанию

        Returns:
            DailyQueue instance

        Raises:
            IntegrityError: Если врач с specialist_id не существует
        """
        defaults = defaults or {}

        # ✅ SECURITY: Проверяем существование врача перед созданием очереди
        # SSOT: DailyQueue.specialist_id ссылается на Doctor.id
        doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
        if not doctor:
            logger.error(
                f"Cannot create DailyQueue: Doctor with ID={specialist_id} does not exist"
            )
            raise ValueError(
                f"Врач с ID {specialist_id} не найден. Невозможно создать очередь."
            )
        # ✅ ИСПРАВЛЕНО: Используем doctor.id для specialist_id (ForeignKey на doctors.id)
        # DailyQueue.specialist_id должен быть doctor.id
        actual_specialist_id = doctor.id

        # ⭐ SSOT FIX: Сначала ищем очередь по (day, queue_tag), игнорируя specialist_id
        # Это предотвращает создание дубликатов очередей с разными specialist_id
        if queue_tag:
            # Ищем существующую очередь по queue_tag (более приоритетно)
            existing_by_tag = db.query(DailyQueue).filter(
                DailyQueue.day == day,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active == True,
            ).first()
            if existing_by_tag:
                return existing_by_tag

        # Fallback: ищем по specialist_id (для legacy совместимости или без queue_tag)
        query = db.query(DailyQueue).filter(
            DailyQueue.day == day,
            DailyQueue.specialist_id == actual_specialist_id,
        )
        if queue_tag:
            query = query.filter(DailyQueue.queue_tag == queue_tag)
        daily_queue = query.first()
        if daily_queue:
            return daily_queue

        settings = self._load_queue_settings(db)
        queue_start_hour = settings.get("queue_start_hour", 7)
        queue_end_hour = settings.get("queue_end_hour", 9)

        daily_queue = DailyQueue(
            day=day,
            specialist_id=actual_specialist_id,  # ✅ Используем doctor.id для ForeignKey
            queue_tag=queue_tag,
            active=True,
            online_start_time=f"{int(queue_start_hour):02d}:00",
            online_end_time=f"{int(queue_end_hour):02d}:00",
            max_online_entries=defaults.get("max_online_entries"),
            cabinet_number=defaults.get("cabinet_number"),
            cabinet_floor=defaults.get("cabinet_floor"),
            cabinet_building=defaults.get("cabinet_building"),
        )
        db.add(daily_queue)
        try:
            db.flush()
            logger.info(
                "Created DailyQueue id=%s day=%s specialist=%s queue_tag=%s",
                daily_queue.id,
                day,
                actual_specialist_id,
                queue_tag,
            )
            return daily_queue
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to create DailyQueue: day={day}, specialist_id={actual_specialist_id}, "
                f"queue_tag={queue_tag}, error={e}"
            )
            raise

    def get_next_queue_number(
        self,
        db: Session,
        *,
        daily_queue: DailyQueue | None = None,
        queue_id: int | None = None,
        default_start: int | None = None,
        queue_tag: str | None = None,
        scope: str = "per_queue",
    ) -> int:
        """
        Возвращает следующий номер в очереди.

        Args:
            daily_queue: уже загруженная очередь (предпочтительно)
            queue_id: если очередь не загружена, можно передать её ID
            default_start: стартовое значение, если в daily_queue отсутствует start_number
            queue_tag: используется для выбора дефолтного стартового номера из настроек
            scope: 'per_queue' (по умолчанию) или 'global' для глобального счётчика
        """
        if scope not in {"per_queue", "global"}:
            raise QueueValidationError("scope must be 'per_queue' or 'global'")

        settings = self._load_queue_settings(db)
        start_numbers = settings.get("start_numbers", {})

        fallback_start = default_start
        if fallback_start is None:
            if daily_queue and getattr(daily_queue, "start_number", None):
                fallback_start = daily_queue.start_number
            else:
                tag_key = queue_tag or "default"
                fallback_start = start_numbers.get(
                    tag_key, self.SPECIALTY_START_NUMBERS.get(tag_key, 1)
                )

        if fallback_start is None:
            fallback_start = self.SPECIALTY_START_NUMBERS.get("default", 1)

        if scope == "global":
            max_number = db.query(func.max(OnlineQueueEntry.number)).scalar() or 0
            return max(max_number + 1, fallback_start)

        if daily_queue is None:
            if queue_id is None:
                raise QueueValidationError("daily_queue or queue_id must be provided")
            daily_queue = db.query(DailyQueue).filter(DailyQueue.id == queue_id).with_for_update().first()
            if not daily_queue:
                raise QueueNotFoundError(f"DailyQueue {queue_id} not found")

        # start_number не является полем DailyQueue, используется только для вычисления номера записи
        # Не нужно устанавливать его в daily_queue

        return self.calculate_next_number(db, daily_queue)

    def assign_queue_token(
        self,
        db: Session,
        *,
        specialist_id: int | None,
        department: str | None,
        generated_by_user_id: int | None,
        target_date: date | None = None,
        expires_hours: int = 24,
        is_clinic_wide: bool = False,
        queue_tag: str | None = None,
        commit: bool = True,
    ) -> tuple[str, dict[str, Any]]:
        """
        Создаёт QR-токен для очереди и возвращает его вместе с метаданными.
        """
        queue_settings = self._load_queue_settings(db)
        timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
        now_local = datetime.now(timezone)

        day = target_date
        if day is None:
            cutoff_hour = queue_settings.get("queue_qr_cutoff_hour", 9)
            day = now_local.date()
            if now_local.hour >= int(cutoff_hour):
                day += timedelta(days=1)

        doctor: Doctor | None = None
        daily_queue: DailyQueue | None = None
        doctor_id: int | None = None

        if not is_clinic_wide:
            if specialist_id is None:
                raise QueueValidationError("specialist_id is required for QR токена")

            doctor = (
                db.query(Doctor)
                .filter(
                    or_(
                        Doctor.id == specialist_id,
                    ),
                    Doctor.active.is_(True),
                )
                .first()
            )
            if not doctor:
                raise QueueValidationError(
                    f"Doctor {specialist_id} not found or inactive"
                )
            doctor_id = doctor.id

            daily_queue = self.get_or_create_daily_queue(
                db,
                day=day,
                specialist_id=doctor.id,
                queue_tag=queue_tag or doctor.specialty,
                defaults={
                    "start_number": queue_settings.get("start_numbers", {}).get(
                        doctor.specialty or "default", 1
                    ),
                    "max_online_entries": queue_settings.get("max_per_day", {}).get(
                        doctor.specialty or "default", 15
                    ),
                },
            )

        expires_minutes = self._bounded_queue_token_ttl_minutes(expires_hours)
        expires_at = now_local + timedelta(minutes=expires_minutes)

        token_value = secrets.token_urlsafe(32)
        queue_token = QueueToken(
            token=token_value,
            day=day,
            specialist_id=doctor_id if not is_clinic_wide else None,
            department=department or (doctor.specialty if doctor else None),
            is_clinic_wide=is_clinic_wide,
            generated_by_user_id=generated_by_user_id,
            expires_at=expires_at,
            active=True,
        )
        db.add(queue_token)
        if commit:
            db.commit()
            db.refresh(queue_token)
        else:
            db.flush()

        current_count = 0
        max_slots = queue_settings.get("max_per_day", {}).get(
            (doctor.specialty if doctor else "clinic"),
            queue_settings.get("default_max_slots", 15),
        )
        if daily_queue:
            current_count = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == daily_queue.id)
                .count()
            )
            if daily_queue.max_online_entries:
                max_slots = daily_queue.max_online_entries

        specialist_name = None
        if doctor and doctor.user:
            specialist_name = doctor.user.full_name or doctor.user.username

        metadata = {
            "day": day,
            "queue_id": daily_queue.id if daily_queue else None,
            "specialist_name": specialist_name
            or ("Все специалисты" if is_clinic_wide else None),
            "specialty": doctor.specialty if doctor else "clinic",
            "cabinet": getattr(doctor, "cabinet", None) if doctor else None,
            "start_time": (
                daily_queue.online_start_time
                if daily_queue
                else f"{queue_settings.get('queue_start_hour', 7):02d}:00"
            ),
            "end_time": (
                daily_queue.online_end_time
                if daily_queue
                else f"{queue_settings.get('queue_end_hour', 9):02d}:00"
            ),
            "max_slots": max_slots,
            "current_count": current_count,
            "expires_at": queue_token.expires_at,
            "ttl_minutes": expires_minutes,
            "is_clinic_wide": is_clinic_wide,
        }

        return token_value, metadata

    def validate_queue_token(
        self, db: Session, token: str
    ) -> tuple[QueueToken, dict[str, Any]]:
        queue_token = db.query(QueueToken).filter(QueueToken.token == token).first()
        if not queue_token:
            raise QueueValidationError("Неверный или истёкший QR токен")

        if not queue_token.active:
            raise QueueValidationError("QR токен деактивирован")

        queue_settings = self._load_queue_settings(db)
        timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
        now_local = datetime.now(timezone)

        expires_cmp = queue_token.expires_at
        if expires_cmp:
            if expires_cmp.tzinfo is None:
                expires_cmp = expires_cmp.replace(tzinfo=timezone)
            if expires_cmp <= now_local:
                raise QueueValidationError("Срок действия QR токена истёк")

        daily_queue: DailyQueue | None = None
        if not queue_token.is_clinic_wide and queue_token.specialist_id:
            # ✅ ИСПРАВЛЕНО: DailyQueue.specialist_id ссылается на doctors.id,
            # а не на users.id. queue_token.specialist_id уже содержит doctor.id
            daily_queue = (
                db.query(DailyQueue)
                .filter(
                    DailyQueue.day == queue_token.day,
                    DailyQueue.specialist_id == queue_token.specialist_id,
                )
                .first()
            )
            if not daily_queue:
                raise QueueNotFoundError(
                    "Очередь ещё не создана для выбранного специалиста"
                )

        metadata = {
            "day": queue_token.day,
            "expires_at": expires_cmp,
            "timezone": timezone,
            "daily_queue": daily_queue,
            "is_clinic_wide": queue_token.is_clinic_wide,
            "department": queue_token.department,
            "specialist_name": (
                queue_token.specialist.user.full_name
                if queue_token.specialist
                and queue_token.specialist.user
                and queue_token.specialist.user.full_name
                else None
            ),
        }
        return queue_token, metadata

    def join_queue_with_token(
        self,
        db: Session,
        *,
        token_str: str,
        patient_name: str,
        phone: str | None = None,
        telegram_id: int | None = None,
        specialist_id_override: int | None = None,
        patient_id: int | None = None,
        source: str = "online",
    ) -> dict[str, Any]:
        """
        Единая точка входа для присоединения к очереди через QR-токен.

        Returns:
            dict с полями entry, duplicate, specialist_name и т.д.
        """
        token_obj, token_meta = self.validate_queue_token(db, token_str)
        queue_settings = self._load_queue_settings(db)

        day = token_meta.get("day") or token_obj.day
        daily_queue: DailyQueue | None = token_meta.get("daily_queue")
        specialist_name = token_meta.get("specialist_name")
        cabinet = token_meta.get("cabinet")

        # Поддержка общего QR (clinic-wide)
        if token_obj.is_clinic_wide:
            if specialist_id_override is None:
                raise QueueValidationError("Выберите специалиста для записи")

            # ⭐ SSOT FIX: specialist_id_override может быть:
            # 1. QueueProfile.id (когда пользователь выбирает профиль на QR странице)
            # 2. Doctor.id (legacy)
            # Сначала проверяем, не является ли это QueueProfile.id
            from app.models.queue_profile import QueueProfile

            queue_profile_by_id = db.query(QueueProfile).filter(
                QueueProfile.id == specialist_id_override,
            ).first()
            if queue_profile_by_id and not self._is_qr_visible_profile(
                queue_profile_by_id
            ):
                raise QueueValidationError("Специалист недоступен для QR-записи")

            queue_profile = (
                queue_profile_by_id
                if queue_profile_by_id
                and self._is_qr_visible_profile(queue_profile_by_id)
                else None
            )

            if queue_profile:
                # ⭐ Это QueueProfile.id - ищем врача по specialty, соответствующему профилю
                # QueueProfile.key - это "cardiology", "dermatology", etc.
                # QueueProfile.queue_tags - это список возможных doctor.specialty значений
                profile_key = queue_profile.key
                queue_tags = queue_profile.queue_tags or [profile_key]

                # Ищем врача с specialty из queue_tags профиля
                doctor = (
                    db.query(Doctor)
                    .filter(
                        Doctor.active.is_(True),
                        Doctor.specialty.in_(queue_tags),
                    )
                    .first()
                )

                # Если не нашли - это ошибка сопоставления профиля, а не повод
                # подставлять случайного активного врача.
                if not doctor:
                    raise QueueValidationError(
                        f"Нет активных врачей для профиля {queue_profile.title_ru or queue_profile.title}"
                    )
                else:
                    # Нашли врача - используем его данные
                    queue_tag = profile_key  # ⭐ Используем ключ профиля, не doctor.specialty
                    defaults = {
                        "start_number": doctor.start_number_online,
                        "max_online_entries": doctor.max_online_per_day,
                        "cabinet_number": doctor.cabinet,
                    }
                    daily_queue = self.get_or_create_daily_queue(
                        db,
                        day=day,
                        specialist_id=doctor.id,
                        queue_tag=queue_tag,
                        defaults=defaults,
                    )
                    if doctor.user:
                        specialist_name = doctor.user.full_name or doctor.user.username
                    specialist_name = specialist_name or queue_profile.title_ru or f"Врач #{doctor.id}"
                    cabinet = doctor.cabinet
            else:
                # Legacy: specialist_id_override is Doctor.id
                doctor = (
                    db.query(Doctor)
                    .filter(
                        Doctor.active.is_(True),
                        or_(
                            Doctor.id == specialist_id_override,
                        ),
                    )
                    .first()
                )
                if not doctor:
                    raise QueueValidationError("Специалист недоступен для записи")

                qr_profile = self._get_qr_visible_profile_for_doctor(db, doctor)
                if not qr_profile:
                    raise QueueValidationError("Специалист недоступен для QR-записи")

                queue_tag = doctor.specialty
                defaults = {
                    "start_number": doctor.start_number_online,
                    "max_online_entries": doctor.max_online_per_day,
                    "cabinet_number": doctor.cabinet,
                }
                daily_queue = self.get_or_create_daily_queue(
                    db,
                    day=day,
                    specialist_id=doctor.id,
                    queue_tag=queue_tag,
                    defaults=defaults,
                )
                if doctor.user:
                    specialist_name = doctor.user.full_name or doctor.user.username
                specialist_name = specialist_name or f"Врач #{doctor.id}"
                cabinet = doctor.cabinet
        else:
            if specialist_id_override and token_obj.specialist_id:
                if specialist_id_override not in {
                    token_obj.specialist_id,
                    (
                        token_obj.specialist.user_id
                        if token_obj.specialist and token_obj.specialist.user
                        else None
                    ),
                }:
                    raise QueueValidationError(
                        "QR токен принадлежит другому специалисту"
                    )
            if not daily_queue:
                raise QueueNotFoundError("Очередь ещё не активна")

        # Валидации пациента
        is_valid, validation_message = self.validate_queue_entry_data(
            patient_name, phone, telegram_id
        )
        if not is_valid:
            raise QueueValidationError(validation_message)

        time_allowed, time_message = self.check_queue_time_window(
            day, daily_queue.opened_at
        )
        if not time_allowed:
            raise QueueValidationError(time_message)

        limits_ok, limits_message = self.check_queue_limits(db, daily_queue)
        if not limits_ok:
            raise QueueConflictError(limits_message)

        existing_entry, duplicate_reason = self.check_uniqueness(
            db, daily_queue, phone, telegram_id, source=source
        )

        queue_length_before = (
            db.query(func.count(OnlineQueueEntry.id))
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .scalar()
            or 0
        )
        estimated_wait_minutes = queue_length_before * int(
            queue_settings.get("estimated_wait_minutes", 15)
        )

        if existing_entry:
            return {
                "entry": existing_entry,
                "duplicate": True,
                "duplicate_reason": duplicate_reason,
                "specialist_name": specialist_name,
                "cabinet": cabinet,
                "queue_length_before": queue_length_before,
                "estimated_wait_minutes": estimated_wait_minutes,
                "daily_queue": daily_queue,
                "token": token_obj,
            }

        entry = self.create_queue_entry(
            db,
            daily_queue=daily_queue,
            patient_id=patient_id,
            patient_name=patient_name,
            phone=phone,
            telegram_id=telegram_id,
            source=source,
            auto_number=True,
            commit=False,
        )

        self._increment_token_usage(token_obj)
        db.commit()
        db.refresh(entry)

        return {
            "entry": entry,
            "duplicate": False,
            "duplicate_reason": "",
            "specialist_name": specialist_name,
            "cabinet": cabinet,
            "queue_length_before": queue_length_before,
            "estimated_wait_minutes": estimated_wait_minutes,
            "daily_queue": daily_queue,
            "token": token_obj,
        }

    def create_queue_entry(
        self,
        db: Session,
        *,
        daily_queue: DailyQueue | None = None,
        payload: dict[str, Any] | None = None,
        queue_id: int | None = None,
        number: int | None = None,
        patient_id: int | None = None,
        patient_name: str | None = None,
        phone: str | None = None,
        telegram_id: str | None = None,
        visit_id: int | None = None,
        visit_type: str = "paid",
        discount_mode: str = "none",
        services: list[dict[str, Any]] | None = None,
        service_codes: list[str] | None = None,
        total_amount: int | None = None,
        source: str = "desk",
        status: str = "waiting",
        queue_time: datetime | None = None,
        auto_number: bool = False,
        commit: bool = True,
    ) -> OnlineQueueEntry:
        """
        Создаёт запись в очереди и возвращает её.
        """
        queue_obj = daily_queue
        if queue_obj is None:
            if queue_id is None:
                raise QueueValidationError("daily_queue or queue_id must be provided")
            queue_obj = db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
            if not queue_obj:
                raise QueueNotFoundError(f"DailyQueue {queue_id} not found")

        if payload:
            normalized = self.normalize_queue_payload(payload)
            patient_id = normalized.get("patient_id") or patient_id
            patient_name = normalized.get("patient_name") or patient_name
            phone = normalized.get("phone") or phone
            telegram_id = normalized.get("telegram_id") or telegram_id
            source = normalized.get("source") or source

        if number is None or auto_number:
            number = self.get_next_queue_number(
                db,
                daily_queue=queue_obj,
                queue_tag=queue_obj.queue_tag,
            )

        queue_dt = queue_time or self.get_local_timestamp(db)

        # ⭐ session_id для группировки услуг пациента в одной очереди
        session_id = None
        if patient_id:
            session_id = get_or_create_session_id(
                db, patient_id, queue_obj.id, queue_obj.day
            )
        else:
            # Fallback for entries without patient
            session_id = None  # Will be filled after flush with entry.id

        entry = OnlineQueueEntry(
            queue_id=queue_obj.id,
            number=number,
            patient_id=patient_id,
            patient_name=patient_name,
            phone=phone,
            telegram_id=telegram_id,
            visit_id=visit_id,
            visit_type=visit_type,
            discount_mode=discount_mode,
            source=source,
            status=status,
            queue_time=queue_dt,
            updated_at=queue_dt,
            total_amount=total_amount or 0,
            session_id=session_id,  # ⭐ NEW: Session grouping
        )

        if services is not None:
            entry.services = services
            if service_codes is None:
                service_codes = [
                    svc.get("code")
                    for svc in services
                    if isinstance(svc, dict) and svc.get("code")
                ]
        if service_codes is not None:
            entry.service_codes = service_codes

        db.add(entry)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return entry

    def _staff_action_result(
        self,
        entry: OnlineQueueEntry,
        *,
        action: str,
        previous_status: str,
        original_queue_time: datetime | None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "action": action,
            "entry_id": entry.id,
            "queue_id": entry.queue_id,
            "visit_id": entry.visit_id,
            "number": entry.number,
            "previous_status": previous_status,
            "status": entry.status,
            "queue_time": entry.queue_time,
            "queue_time_preserved": entry.queue_time == original_queue_time,
            "called_at": entry.called_at,
        }

    def staff_call_next_patient(
        self,
        db: Session,
        *,
        queue_id: int | None = None,
        specialist_id: int | None = None,
        queue_tag: str | None = None,
        target_date: date | None = None,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        target_day = target_date or date.today()
        query = (
            db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                DailyQueue.day == target_day,
                DailyQueue.active.is_(True),
                OnlineQueueEntry.status == "waiting",
            )
        )
        if queue_id is not None:
            query = query.filter(OnlineQueueEntry.queue_id == queue_id)
        if specialist_id is not None:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        if queue_tag:
            query = query.filter(DailyQueue.queue_tag == queue_tag)

        entry = (
            query.order_by(
                OnlineQueueEntry.priority.desc(),
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .first()
        )
        if not entry:
            raise QueueNotFoundError("No waiting queue entry found for staff call")

        original_queue_time = entry.queue_time
        previous_status = entry.status
        changed_at = self.get_local_timestamp(db)
        entry.status = "called"
        entry.called_at = changed_at
        entry.updated_at = changed_at
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_call_next_patient",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )

    def staff_skip_queue_entry(
        self,
        db: Session,
        *,
        entry_id: int,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        entry = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .first()
        )
        if not entry:
            raise QueueNotFoundError(f"Queue entry {entry_id} not found")
        if entry.status not in {"waiting", "called"}:
            raise QueueConflictError(
                f"Queue entry {entry_id} cannot be skipped from status {entry.status}"
            )

        original_queue_time = entry.queue_time
        previous_status = entry.status
        entry.status = "no_show"
        entry.updated_at = self.get_local_timestamp(db)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_skip_queue_entry",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )

    def _staff_visit_queue_link_entry(
        self,
        db: Session,
        *,
        visit_id: int,
    ) -> OnlineQueueEntry:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise QueueNotFoundError(f"Visit {visit_id} not found")
        if visit.patient_id is None:
            raise QueueConflictError(f"Visit {visit_id} has no patient owner")

        active_statuses = {"waiting", "called", "in_service", "diagnostics"}
        entries = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.visit_id == visit_id,
                OnlineQueueEntry.patient_id == visit.patient_id,
                OnlineQueueEntry.status.in_(active_statuses),
            )
            .order_by(
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .all()
        )
        if not entries:
            raise QueueNotFoundError(f"Active queue link for visit {visit_id} not found")
        if len(entries) > 1:
            raise QueueConflictError(
                f"Visit {visit_id} has multiple active queue links"
            )
        return entries[0]

    def staff_cancel_visit_queue_link(
        self,
        db: Session,
        *,
        visit_id: int,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        entry = self._staff_visit_queue_link_entry(db, visit_id=visit_id)
        original_queue_time = entry.queue_time
        previous_status = entry.status
        entry.status = "cancelled"
        entry.updated_at = self.get_local_timestamp(db)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_cancel_visit_queue_link",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )

    def staff_move_visit_queue_link(
        self,
        db: Session,
        *,
        visit_id: int,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        entry = self._staff_visit_queue_link_entry(db, visit_id=visit_id)
        original_queue_time = entry.queue_time
        previous_status = entry.status
        entry.status = "rescheduled"
        entry.updated_at = self.get_local_timestamp(db)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_move_visit_queue_link",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )

    def update_queue_status(
        self,
        db: Session,
        *,
        entry_id: int,
        new_status: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("update_queue_status is pending implementation")

    def validate_status_transition(self, current_status: str, new_status: str) -> None:
        raise NotImplementedError(
            "validate_status_transition is pending implementation"
        )

    def close_queue_entry(
        self,
        db: Session,
        *,
        entry_id: int,
        result_status: str = "served",
        closed_by: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("close_queue_entry is pending implementation")

    def calculate_wait_time(self, entry: OnlineQueueEntry) -> dict[str, Any]:
        raise NotImplementedError("calculate_wait_time is pending implementation")

    def get_visit_history(
        self, db: Session, *, patient_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("get_visit_history is pending implementation")

    def reorder_queue(
        self, db: Session, *, queue_id: int, entry_orders: list[dict[str, int]]
    ) -> dict[str, Any]:
        raise NotImplementedError("reorder_queue is pending implementation")

    def resolve_conflicts(
        self, db: Session, *, queue_id: int, strategy: str = "compact"
    ) -> dict[str, Any]:
        raise NotImplementedError("resolve_conflicts is pending implementation")


# Глобальный экземпляр сервиса
queue_service = QueueBusinessService()


def get_queue_service() -> QueueBusinessService:
    """Получить экземпляр сервиса очереди"""
    return queue_service
