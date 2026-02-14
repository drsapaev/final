"""Service layer for queue_limits endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.crud.clinic import get_queue_settings, update_queue_settings
from app.repositories.queue_limits_repository import QueueLimitsRepository


class QueueLimitsApiService:
    """Builds queue limits/status payloads and persists queue limit changes."""

    def __init__(
        self,
        db: Session,
        repository: QueueLimitsRepository | None = None,
        get_settings: Callable[[Session], dict] | None = None,
        update_settings: Callable[[Session, dict, int], None] | None = None,
    ):
        self.db = db
        self.repository = repository or QueueLimitsRepository(db)
        self._get_settings = get_settings or get_queue_settings
        self._update_settings = update_settings or update_queue_settings

    def get_queue_limits(self, *, specialty: str | None) -> list[dict]:
        queue_settings = self._get_settings(self.db)
        max_per_day_settings = queue_settings.get("max_per_day", {})
        start_numbers_settings = queue_settings.get("start_numbers", {})

        doctors = self.repository.list_active_doctors(specialty=specialty)

        specialties: dict[str, dict] = {}
        for doctor in doctors:
            if doctor.specialty not in specialties:
                specialties[doctor.specialty] = {"doctors": [], "current_usage": 0}
            specialties[doctor.specialty]["doctors"].append(doctor)

        today = date.today()
        for spec_data in specialties.values():
            total_usage = 0
            for doctor in spec_data["doctors"]:
                daily_queue = self.repository.get_daily_queue(
                    day=today,
                    specialist_id=doctor.user_id,
                )
                if daily_queue:
                    total_usage += self.repository.count_entries(queue_id=daily_queue.id)
            spec_data["current_usage"] = total_usage

        result: list[dict] = []
        for spec_name, spec_data in specialties.items():
            result.append(
                {
                    "specialty": spec_name,
                    "max_per_day": max_per_day_settings.get(spec_name, 15),
                    "start_number": start_numbers_settings.get(spec_name, 1),
                    "enabled": True,
                    "current_usage": spec_data["current_usage"],
                    "doctors_count": len(spec_data["doctors"]),
                    "last_updated": datetime.utcnow(),
                }
            )
        return result

    def update_queue_limits(self, *, limits: list, current_user_id: int) -> dict:  # type: ignore[no-untyped-def]
        queue_settings = self._get_settings(self.db)
        max_per_day = queue_settings.get("max_per_day", {})
        start_numbers = queue_settings.get("start_numbers", {})

        updated_specialties: list[str] = []
        for limit_update in limits:
            if limit_update.max_per_day is not None:
                max_per_day[limit_update.specialty] = limit_update.max_per_day
            if limit_update.start_number is not None:
                start_numbers[limit_update.specialty] = limit_update.start_number
            updated_specialties.append(limit_update.specialty)

        new_settings = {
            **queue_settings,
            "max_per_day": max_per_day,
            "start_numbers": start_numbers,
        }
        self._update_settings(self.db, new_settings, current_user_id)

        return {
            "success": True,
            "message": f"Лимиты обновлены для специальностей: {', '.join(updated_specialties)}",
            "updated_specialties": updated_specialties,
            "updated_at": datetime.utcnow(),
        }

    def get_queue_status_with_limits(self, *, day: date, specialty: str | None) -> list[dict]:
        queue_settings = self._get_settings(self.db)
        max_per_day_settings = queue_settings.get("max_per_day", {})
        doctors = self.repository.list_active_doctors(specialty=specialty)

        result: list[dict] = []
        for doctor in doctors:
            daily_queue = self.repository.get_daily_queue(
                day=day,
                specialist_id=doctor.user_id,
            )

            current_entries = 0
            queue_opened = False
            if daily_queue:
                current_entries = self.repository.count_entries(queue_id=daily_queue.id)
                queue_opened = daily_queue.opened_at is not None

            max_entries = max_per_day_settings.get(doctor.specialty, 15)
            online_available = not queue_opened and current_entries < max_entries

            result.append(
                {
                    "doctor_id": doctor.id,
                    "doctor_name": (
                        doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                    ),
                    "specialty": doctor.specialty,
                    "cabinet": doctor.cabinet,
                    "day": day,
                    "current_entries": current_entries,
                    "max_entries": max_entries,
                    "limit_reached": current_entries >= max_entries,
                    "queue_opened": queue_opened,
                    "online_available": online_available,
                }
            )
        return result

    def set_doctor_queue_limit(self, *, limit_data) -> dict:  # type: ignore[no-untyped-def]
        doctor = self.repository.get_doctor(limit_data.doctor_id)
        if not doctor:
            raise ValueError("DOCTOR_NOT_FOUND")

        daily_queue = self.repository.get_or_create_daily_queue(
            day=limit_data.day,
            specialist_id=limit_data.doctor_id,
            max_online_entries=limit_data.max_online_entries,
        )
        daily_queue.max_online_entries = limit_data.max_online_entries
        self.repository.save()

        doctor_name = doctor.user.full_name if doctor.user else f"#{doctor.id}"
        return {
            "success": True,
            "message": f"Лимит установлен для врача {doctor_name} на {limit_data.day}",
            "doctor_id": limit_data.doctor_id,
            "day": limit_data.day,
            "max_online_entries": limit_data.max_online_entries,
            "updated_at": datetime.utcnow(),
        }

    def reset_queue_limits(self, *, specialty: str | None, current_user_id: int) -> dict:
        queue_settings = self._get_settings(self.db)
        if specialty:
            max_per_day = queue_settings.get("max_per_day", {})
            start_numbers = queue_settings.get("start_numbers", {})
            max_per_day[specialty] = 15
            start_numbers[specialty] = 1
            new_settings = {
                **queue_settings,
                "max_per_day": max_per_day,
                "start_numbers": start_numbers,
            }
            message = f"Лимиты сброшены для специальности: {specialty}"
        else:
            new_settings = {**queue_settings, "max_per_day": {}, "start_numbers": {}}
            message = "Все лимиты сброшены к значениям по умолчанию"

        self._update_settings(self.db, new_settings, current_user_id)
        return {"success": True, "message": message, "reset_at": datetime.utcnow()}

    def rollback(self) -> None:
        self.repository.rollback()

