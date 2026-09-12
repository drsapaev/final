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
        """RQ-09: the PUBLIC clinic-wide selection mirrors the JOIN contract.

        Visibility — ADMIN-controlled SSOT (PR-28):
        ``QueueProfile.is_active`` + ``show_on_qr_page`` are the only
        profile constraints. No hard-coded hidden keys
        (``QueueBusinessService.QR_HIDDEN_PROFILE_KEYS == set()``) and no
        ``INITIAL_QUEUE_PROFILES`` fallback: when every direction is
        hidden the public page must offer a correct EMPTY state (the
        QueueJoin UI renders «нет направлений» + refresh), not default
        suggestions the join then rejects.

        Doctor eligibility — canonical owner-eligibility contract
        (``services/appointment_eligibility.py``, decision #13): an
        active Doctor with a completed specialty whose owner account
        exists, is active and carries a doctor-family role. Deactivated
        ghosts, incomplete «general» placeholders and the seeded 0055
        RESOURCE synthetics (owner roles «Lab»/«Nurse») belong to the
        resource surface, never to joinable doctor cards.
        """
        from sqlalchemy.orm import joinedload

        from app.models.queue_profile import QueueProfile

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
                "[QRQueueService] queue_profiles unavailable; offering empty selection",
                exc_info=True,
            )
            profiles = []

        profile_by_specialty: dict[str, dict[str, Any]] = {}
        for profile in profiles:
            profile_key = self._normalize_specialty_key(profile.key)
            if not profile_key:
                continue
            item = {
                "key": profile.key,
                "title": profile.title,
                "title_ru": profile.title_ru,
                "queue_tags": profile.queue_tags or [],
                "color": profile.color,
                "icon": profile.icon,
                "order": profile.display_order,
            }
            keys = {profile_key}
            keys.update(
                self._normalize_specialty_key(tag)
                for tag in (profile.queue_tags or [])
            )
            for key in keys:
                if key and key not in profile_by_specialty:
                    profile_by_specialty[key] = item

        if not profile_by_specialty:
            return []

        from app.core.roles import is_doctor_role_spelling
        from app.services.user_mgmt._base import is_doctor_profile_incomplete

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
            raw_specialty = getattr(doctor, "specialty", None)
            if is_doctor_profile_incomplete(raw_specialty):
                continue
            specialty = self._normalize_specialty_key(raw_specialty)
            profile = profile_by_specialty.get(specialty)
            if not profile or doctor.id in seen_ids:
                continue
            owner = getattr(doctor, "user", None)
            if (
                owner is None
                or not getattr(owner, "is_active", False)
                or not is_doctor_role_spelling(getattr(owner, "role", None))
            ):
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
                        owner.full_name
                        if owner
                        else f"Doctor #{doctor.id}"
                    ),
                    "cabinet": doctor.cabinet,
                }
            )
            seen_ids.add(doctor.id)

        return selectable


