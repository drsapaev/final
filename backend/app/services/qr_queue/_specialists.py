"""Specialists mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


class SpecialistsMixin(QRQueueServiceMixinBase):
    """Specialists methods for QRQueueService."""

    @staticmethod
    def _normalize_specialty_key(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        aliases = {
            "cardio": "cardiology",
            "derma": "dermatology",
            "dentist": "stomatology",
            "dentistry": "stomatology",
            "laboratory": "lab",
        }
        return aliases.get(normalized, normalized)

    @staticmethod
    def _queue_profile_icon(key: str, configured_icon: str | None) -> str:
        emoji_map = {
            "cardiology": "❤️",
            "ecg": "📊",
            "dermatology": "✨",
            "stomatology": "🦷",
            "lab": "🔬",
            "laboratory": "🔬",
            "procedures": "💉",
            "cosmetology": "💄",
            "general": "👥",
        }
        return emoji_map.get(key, configured_icon or "👨‍⚕️")


    def _get_clinic_wide_selectable_specialists(self) -> list[dict[str, Any]]:
        from sqlalchemy.orm import joinedload

        from app.models.queue_profile import INITIAL_QUEUE_PROFILES, QueueProfile

        hidden_profile_keys = {"ecg", "general"}
        try:
            profiles = (
                self.db.query(QueueProfile)
                .filter(
                    QueueProfile.is_active == True,
                    QueueProfile.show_on_qr_page == True,
                )
                .order_by(QueueProfile.display_order)
                .all()
            )
        except Exception:
            logger.warning(
                "[QRQueueService] queue_profiles unavailable; using initial profile fallback",
                exc_info=True,
            )
            profiles = []

        if profiles:
            profile_items = [
                {
                    "key": profile.key,
                    "title": profile.title,
                    "title_ru": profile.title_ru,
                    "queue_tags": profile.queue_tags or [],
                    "color": profile.color,
                    "icon": profile.icon,
                    "order": profile.display_order,
                }
                for profile in profiles
            ]
        else:
            profile_items = [
                {
                    "key": profile["key"],
                    "title": profile["title"],
                    "title_ru": profile.get("title_ru"),
                    "queue_tags": profile.get("queue_tags") or [],
                    "color": profile.get("color"),
                    "icon": profile.get("icon"),
                    "order": profile.get("order", 0),
                }
                for profile in INITIAL_QUEUE_PROFILES
            ]

        profile_by_specialty: dict[str, dict[str, Any]] = {}
        for profile in profile_items:
            profile_key = self._normalize_specialty_key(profile.get("key"))
            if not profile_key or profile_key in hidden_profile_keys:
                continue
            keys = {profile_key}
            keys.update(
                self._normalize_specialty_key(tag)
                for tag in (profile.get("queue_tags") or [])
            )
            for key in keys:
                if key and key not in hidden_profile_keys:
                    profile_by_specialty.setdefault(key, profile)

        if not profile_by_specialty:
            return []

        doctors = (
            self.db.query(Doctor)
            .filter(Doctor.active == True)
            .options(joinedload(Doctor.user))
            .order_by(Doctor.id.asc())
            .all()
        )
        selectable: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for doctor in doctors:
            specialty = self._normalize_specialty_key(getattr(doctor, "specialty", None))
            profile = profile_by_specialty.get(specialty)
            if not profile or doctor.id in seen_ids:
                continue
            profile_key = self._normalize_specialty_key(profile.get("key"))
            selectable.append(
                {
                    "id": doctor.id,
                    "specialty": profile_key,
                    "specialty_display": (
                        profile.get("title_ru")
                        or profile.get("title")
                        or profile_key
                    ),
                    "icon": self._queue_profile_icon(profile_key, profile.get("icon")),
                    "color": profile.get("color") or "#6b7280",
                    "doctor_name": (
                        doctor.user.full_name
                        if getattr(doctor, "user", None)
                        else f"Doctor #{doctor.id}"
                    ),
                    "cabinet": doctor.cabinet,
                }
            )
            seen_ids.add(doctor.id)

        return selectable


