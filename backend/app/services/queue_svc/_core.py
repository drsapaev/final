"""Core mixin for QueueBusinessService.

Split from queue_service.py.
"""
from __future__ import annotations

from app.services.queue_svc._base import *  # noqa: F401, F403
from app.services.queue_svc._base import QueueBusinessServiceMixinBase


class CoreMixin(QueueBusinessServiceMixinBase):
    """Core methods."""

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
