"""
Сервис для бизнес-логики очереди
"""
from __future__ import annotations

import copy
import logging
import secrets
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.crud.clinic import get_queue_settings
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.user import User

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
        "cardio": 1,      # Кардиолог - с №1
        "derma": 15,      # Дерматолог - с №15 
        "dental": 3,      # Стоматолог - с №3
        "general": 1,     # Общий врач - с №1
        "default": 1      # По умолчанию - с №1
    }
    
    # Время работы онлайн-записи
    ONLINE_QUEUE_START_TIME = time(7, 0)  # 07:00
    
    # Лимиты по умолчанию
    DEFAULT_MAX_SLOTS = 15

    def __init__(self) -> None:
        self._cached_settings: Optional[Dict[str, Any]] = None

    @staticmethod
    def _increment_token_usage(queue_token: QueueToken) -> None:
        """Унифицированно увеличивает счётчик использования QR-токена."""
        if hasattr(queue_token, "usage_count"):
            current = getattr(queue_token, "usage_count") or 0
            queue_token.usage_count = current + 1
        else:
            current = getattr(queue_token, "current_uses", 0) or 0
            setattr(queue_token, "current_uses", current + 1)

    def _load_queue_settings(self, db: Session) -> Dict[str, Any]:
        if self._cached_settings is None:
            self._cached_settings = get_queue_settings(db) or {}
        return self._cached_settings

    def get_local_timestamp(
        self, db: Optional[Session] = None, timezone: Optional[str] = None
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

    def normalize_queue_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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

    def validate_queue_input(self, payload: Dict[str, Any]) -> None:
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
        return cls.SPECIALTY_START_NUMBERS.get(specialty, cls.SPECIALTY_START_NUMBERS["default"])
    
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
    def check_queue_time_window(cls, target_date: date, queue_opened_at: Optional[datetime] = None) -> Tuple[bool, str]:
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
                return False, f"⏰ Онлайн-запись откроется в {cls.ONLINE_QUEUE_START_TIME.strftime('%H:%M')}. Текущее время: {current_time.strftime('%H:%M')}"
            
            if queue_opened_at:
                opened_time = queue_opened_at.strftime('%H:%M')
                return False, f"🚪 Прием уже открыт в {opened_time}. Онлайн-запись закрыта. Обратитесь в регистратуру."
        
        # Для будущих дней разрешаем запись
        return True, ""
    
    @classmethod
    def check_queue_limits(cls, db: Session, daily_queue: DailyQueue) -> Tuple[bool, str]:
        """
        Проверить лимиты очереди
        
        Returns:
            (is_allowed, message)
        """
        current_entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).count()
        
        max_slots = getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS
        
        if current_entries >= max_slots:
            return False, f"🚫 Достигнут лимит мест ({max_slots}). Обратитесь в регистратуру."
        
        return True, ""
    
    @classmethod
    def check_uniqueness(cls, db: Session, daily_queue: DailyQueue, phone: Optional[str] = None, 
                        telegram_id: Optional[str] = None) -> Tuple[Optional[OnlineQueueEntry], str]:
        """
        Проверить уникальность записи
        
        Returns:
            (existing_entry, duplicate_reason)
        """
        if not phone and not telegram_id:
            return None, ""
        
        # Проверяем по телефону
        if phone:
            phone_entry = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.phone == phone,
                OnlineQueueEntry.status.in_(["waiting", "called"])
            ).first()
            
            if phone_entry:
                return phone_entry, f"телефону {phone}"
        
        # Проверяем по Telegram ID
        if telegram_id:
            telegram_entry = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.telegram_id == telegram_id,
                OnlineQueueEntry.status.in_(["waiting", "called"])
            ).first()
            
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

        start_number = getattr(daily_queue, "start_number", None) or cls.SPECIALTY_START_NUMBERS.get(
            "default", 1
        )
        return max(max_number + 1, start_number)
    
    @classmethod
    def get_queue_statistics(cls, db: Session, daily_queue: DailyQueue) -> Dict:
        """Получить статистику очереди"""
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id
        ).all()
        
        stats = {
            "total_entries": len(entries),
            "waiting": len([e for e in entries if e.status == "waiting"]),
            "called": len([e for e in entries if e.status == "called"]),
            "completed": len([e for e in entries if e.status == "completed"]),
            "cancelled": len([e for e in entries if e.status == "cancelled"]),
            "max_slots": getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS,
            "available_slots": max(0, (getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS) - len([e for e in entries if e.status in ["waiting", "called"]])),
            "is_open": daily_queue.opened_at is not None,
            "opened_at": daily_queue.opened_at.isoformat() if daily_queue.opened_at else None
        }
        
        return stats
    
    @classmethod
    def validate_queue_entry_data(cls, patient_name: str, phone: Optional[str] = None, 
                                 telegram_id: Optional[str] = None) -> Tuple[bool, str]:
        """Валидация данных записи в очередь"""
        if not patient_name or not patient_name.strip():
            return False, "❌ Укажите ваше ФИО"
        
        if not phone and not telegram_id:
            return False, "❌ Укажите телефон или Telegram ID"
        
        if phone:
            # Простая валидация телефона
            cleaned_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
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
        queue_tag: Optional[str] = None,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> DailyQueue:
        defaults = defaults or {}
        query = db.query(DailyQueue).filter(
            DailyQueue.day == day,
            DailyQueue.specialist_id == specialist_id,
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
            specialist_id=specialist_id,
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
        db.flush()
        logger.info(
            "Created DailyQueue id=%s day=%s specialist=%s queue_tag=%s",
            daily_queue.id,
            day,
            specialist_id,
            queue_tag,
        )
        return daily_queue

    def get_next_queue_number(
        self,
        db: Session,
        *,
        daily_queue: Optional[DailyQueue] = None,
        queue_id: Optional[int] = None,
        default_start: Optional[int] = None,
        queue_tag: Optional[str] = None,
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
            daily_queue = (
                db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
            )
            if not daily_queue:
                raise QueueNotFoundError(f"DailyQueue {queue_id} not found")

        # start_number не является полем DailyQueue, используется только для вычисления номера записи
        # Не нужно устанавливать его в daily_queue

        return self.calculate_next_number(db, daily_queue)

    def assign_queue_token(
        self,
        db: Session,
        *,
        specialist_id: Optional[int],
        department: Optional[str],
        generated_by_user_id: Optional[int],
        target_date: Optional[date] = None,
        expires_hours: int = 24,
        is_clinic_wide: bool = False,
        queue_tag: Optional[str] = None,
        commit: bool = True,
    ) -> Tuple[str, Dict[str, Any]]:
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

        doctor: Optional[Doctor] = None
        daily_queue: Optional[DailyQueue] = None
        queue_user_id = specialist_id
        doctor_id: Optional[int] = None

        if not is_clinic_wide:
            if specialist_id is None:
                raise QueueValidationError("specialist_id is required for QR токена")

            doctor = (
                db.query(Doctor)
                .filter(
                    or_(
                        Doctor.id == specialist_id,
                        Doctor.user_id == specialist_id,
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
            if doctor.user_id:
                queue_user_id = doctor.user_id

            daily_queue = self.get_or_create_daily_queue(
                db,
                day=day,
                specialist_id=queue_user_id,
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

        expires_delta = max(1, int(expires_hours))
        expires_at = now_local + timedelta(hours=expires_delta)

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
            (doctor.specialty if doctor else "clinic"), queue_settings.get("default_max_slots", 15)
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
        elif queue_user_id:
            user_obj = db.query(User).filter(User.id == queue_user_id).first()
            if user_obj:
                specialist_name = user_obj.full_name or user_obj.username

        metadata = {
            "day": day,
            "queue_id": daily_queue.id if daily_queue else None,
            "specialist_name": specialist_name or ("Все специалисты" if is_clinic_wide else None),
            "specialty": doctor.specialty if doctor else "clinic",
            "cabinet": getattr(doctor, "cabinet", None) if doctor else None,
            "start_time": daily_queue.online_start_time if daily_queue else f"{queue_settings.get('queue_start_hour', 7):02d}:00",
            "end_time": daily_queue.online_end_time if daily_queue else f"{queue_settings.get('queue_end_hour', 9):02d}:00",
            "max_slots": max_slots,
            "current_count": current_count,
            "expires_at": queue_token.expires_at,
            "is_clinic_wide": is_clinic_wide,
        }

        return token_value, metadata

    def validate_queue_token(
        self, db: Session, token: str
    ) -> Tuple[QueueToken, Dict[str, Any]]:
        queue_token = (
            db.query(QueueToken)
            .filter(QueueToken.token == token)
            .first()
        )
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

        daily_queue: Optional[DailyQueue] = None
        queue_user_id: Optional[int] = None
        if not queue_token.is_clinic_wide and queue_token.specialist_id:
            doctor = queue_token.specialist
            if doctor and doctor.user_id:
                queue_user_id = doctor.user_id
            else:
                queue_user_id = queue_token.specialist_id

            daily_queue = (
                db.query(DailyQueue)
                .filter(
                    DailyQueue.day == queue_token.day,
                    DailyQueue.specialist_id == queue_user_id,
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
            "specialist_name": queue_token.specialist.user.full_name
            if queue_token.specialist
            and queue_token.specialist.user
            and queue_token.specialist.user.full_name
            else None,
        }
        return queue_token, metadata

    def join_queue_with_token(
        self,
        db: Session,
        *,
        token_str: str,
        patient_name: str,
        phone: Optional[str] = None,
        telegram_id: Optional[int] = None,
        specialist_id_override: Optional[int] = None,
        patient_id: Optional[int] = None,
        source: str = "online",
    ) -> Dict[str, Any]:
        """
        Единая точка входа для присоединения к очереди через QR-токен.

        Returns:
            dict с полями entry, duplicate, specialist_name и т.д.
        """
        token_obj, token_meta = self.validate_queue_token(db, token_str)
        queue_settings = self._load_queue_settings(db)

        day = token_meta.get("day") or token_obj.day
        daily_queue: Optional[DailyQueue] = token_meta.get("daily_queue")
        specialist_name = token_meta.get("specialist_name")
        cabinet = token_meta.get("cabinet")

        # Поддержка общего QR (clinic-wide)
        if token_obj.is_clinic_wide:
            if specialist_id_override is None:
                raise QueueValidationError("Выберите специалиста для записи")

            doctor = (
                db.query(Doctor)
                .filter(
                    Doctor.active.is_(True),
                    or_(
                        Doctor.id == specialist_id_override,
                        Doctor.user_id == specialist_id_override,
                    ),
                )
                .first()
            )
            if not doctor:
                raise QueueValidationError("Специалист недоступен для записи")

            queue_user_id = doctor.user_id or doctor.id
            queue_tag = doctor.specialty
            defaults = {
                "start_number": doctor.start_number_online,
                "max_online_entries": doctor.max_online_per_day,
                "cabinet_number": doctor.cabinet,
            }
            daily_queue = self.get_or_create_daily_queue(
                db,
                day=day,
                specialist_id=queue_user_id,
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
                    token_obj.specialist.user_id
                    if token_obj.specialist and token_obj.specialist.user
                    else None,
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
            db, daily_queue, phone, telegram_id
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
        daily_queue: Optional[DailyQueue] = None,
        payload: Optional[Dict[str, Any]] = None,
        queue_id: Optional[int] = None,
        number: Optional[int] = None,
        patient_id: Optional[int] = None,
        patient_name: Optional[str] = None,
        phone: Optional[str] = None,
        telegram_id: Optional[str] = None,
        visit_id: Optional[int] = None,
        visit_type: str = "paid",
        discount_mode: str = "none",
        services: Optional[List[Dict[str, Any]]] = None,
        service_codes: Optional[List[str]] = None,
        total_amount: Optional[int] = None,
        source: str = "desk",
        status: str = "waiting",
        queue_time: Optional[datetime] = None,
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
            total_amount=total_amount or 0,
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

    def update_queue_status(
        self,
        db: Session,
        *,
        entry_id: int,
        new_status: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("update_queue_status is pending implementation")

    def validate_status_transition(self, current_status: str, new_status: str) -> None:
        raise NotImplementedError("validate_status_transition is pending implementation")

    def close_queue_entry(
        self,
        db: Session,
        *,
        entry_id: int,
        result_status: str = "served",
        closed_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("close_queue_entry is pending implementation")

    def calculate_wait_time(self, entry: OnlineQueueEntry) -> Dict[str, Any]:
        raise NotImplementedError("calculate_wait_time is pending implementation")

    def get_visit_history(
        self, db: Session, *, patient_id: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError("get_visit_history is pending implementation")

    def reorder_queue(
        self, db: Session, *, queue_id: int, entry_orders: List[Dict[str, int]]
    ) -> Dict[str, Any]:
        raise NotImplementedError("reorder_queue is pending implementation")

    def resolve_conflicts(
        self, db: Session, *, queue_id: int, strategy: str = "compact"
    ) -> Dict[str, Any]:
        raise NotImplementedError("resolve_conflicts is pending implementation")


# Глобальный экземпляр сервиса
queue_service = QueueBusinessService()

def get_queue_service() -> QueueBusinessService:
    """Получить экземпляр сервиса очереди"""
    return queue_service
