"""Service layer for admin_doctors statistics endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.admin_doctors_stats_repository import AdminDoctorsStatsRepository


class AdminDoctorsStatsService:
    """Builds specialty and stats payloads for admin doctor endpoints."""

    _SPECIALTY_INFO = {
        "cardiology": {
            "name_ru": "Кардиология",
            "name_uz": "Kardiologiya",
            "name_en": "Cardiology",
            "description": "Консультации кардиолога, ЭКГ, ЭхоКГ",
            "color": "#dc3545",
        },
        "dermatology": {
            "name_ru": "Дерматология",
            "name_uz": "Dermatologiya",
            "name_en": "Dermatology",
            "description": "Дерматология и косметология",
            "color": "#fd7e14",
        },
        "stomatology": {
            "name_ru": "Стоматология",
            "name_uz": "Stomatologiya",
            "name_en": "Stomatology",
            "description": "Стоматологические услуги",
            "color": "#007bff",
        },
    }

    def __init__(
        self,
        db: Session,
        repository: AdminDoctorsStatsRepository | None = None,
    ):
        self.repository = repository or AdminDoctorsStatsRepository(db)

    def get_specialties(self) -> list[dict]:
        result: list[dict] = []
        for specialty in self.repository.list_active_specialties():
            info = self._SPECIALTY_INFO.get(
                specialty,
                {
                    "name_ru": specialty,
                    "name_uz": specialty,
                    "name_en": specialty,
                    "description": "",
                    "color": "#6c757d",
                },
            )
            result.append(
                {
                    "code": specialty,
                    "doctor_count": self.repository.count_active_by_specialty(specialty),
                    **info,
                }
            )
        return result

    def get_doctors_stats(self) -> dict:
        specialties = self.repository.list_active_specialties()
        total_doctors = self.repository.count_active_doctors()
        return {
            "total_doctors": total_doctors,
            "by_specialty": {
                specialty: self.repository.count_active_by_specialty(specialty)
                for specialty in specialties
            },
            "active_doctors": total_doctors,
        }

