"""Repository helpers for admin_doctors stats endpoints."""

from __future__ import annotations

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.clinic import Doctor


class AdminDoctorsStatsRepository:
    """Encapsulates doctor statistics ORM queries for admin API."""

    def __init__(self, db: Session):
        self.db = db

    def list_active_specialties(self) -> list[str]:
        rows = self.db.query(distinct(Doctor.specialty)).filter(Doctor.active.is_(True)).all()
        return [row[0] for row in rows if row[0]]

    def count_active_doctors(self) -> int:
        return self.db.query(Doctor).filter(Doctor.active.is_(True)).count()

    def count_active_by_specialty(self, specialty: str) -> int:
        return (
            self.db.query(Doctor)
            .filter(
                Doctor.specialty == specialty,
                Doctor.active.is_(True),
            )
            .count()
        )

