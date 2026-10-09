"""Read-only repository for the public website catalog."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.clinic import ClinicSettings, Doctor
from app.models.medical_specialty import MedicalSpecialty
from app.models.service import Service
from app.models.user import User


class PublicSiteReadRepository:
    """Queries only rows eligible to be shaped as public website content."""

    CLINIC_SETTING_KEYS = (
        "clinic_name",
        "clinic_address",
        "clinic_phone",
        "clinic_email",
    )

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _public_service_filters():
        return (
            Service.active.is_(True),
            Service.show_on_website.is_(True),
            Service.slug.is_not(None),
            func.trim(Service.slug) != "",
            func.trim(Service.name) != "",
            Service.name_uz.is_not(None),
            func.trim(Service.name_uz) != "",
            Service.description_ru.is_not(None),
            func.trim(Service.description_ru) != "",
            Service.description_uz.is_not(None),
            func.trim(Service.description_uz) != "",
        )

    @staticmethod
    def _public_doctor_filters():
        return (
            Doctor.active.is_(True),
            Doctor.show_on_website.is_(True),
            Doctor.slug.is_not(None),
            func.trim(Doctor.slug) != "",
            Doctor.bio_ru.is_not(None),
            func.trim(Doctor.bio_ru) != "",
            Doctor.bio_uz.is_not(None),
            func.trim(Doctor.bio_uz) != "",
            User.is_active.is_(True),
            User.full_name.is_not(None),
            func.trim(User.full_name) != "",
        )

    def list_public_services(self) -> list[Service]:
        statement = (
            select(Service)
            .options(selectinload(Service.category))
            .where(*self._public_service_filters())
            .order_by(Service.slug.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_public_service_by_slug(self, slug: str) -> Service | None:
        statement = (
            select(Service)
            .options(selectinload(Service.category))
            .where(*self._public_service_filters(), Service.slug == slug)
        )
        return self.db.scalars(statement).first()

    def list_public_doctors(self) -> list[Doctor]:
        statement = (
            select(Doctor)
            .join(User, Doctor.user_id == User.id)
            .options(joinedload(Doctor.user))
            .where(*self._public_doctor_filters())
            .order_by(Doctor.slug.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_public_doctor_by_slug(self, slug: str) -> Doctor | None:
        statement = (
            select(Doctor)
            .join(User, Doctor.user_id == User.id)
            .options(joinedload(Doctor.user))
            .where(*self._public_doctor_filters(), Doctor.slug == slug)
        )
        return self.db.scalars(statement).first()

    def list_specialties_by_code(self, codes: set[str]) -> dict[str, MedicalSpecialty]:
        if not codes:
            return {}
        statement = select(MedicalSpecialty).where(MedicalSpecialty.code.in_(codes))
        return {
            specialty.code: specialty for specialty in self.db.scalars(statement).all()
        }

    def get_public_clinic_settings(self) -> dict[str, object]:
        statement = select(ClinicSettings).where(
            ClinicSettings.key.in_(self.CLINIC_SETTING_KEYS)
        )
        return {
            setting.key: setting.value for setting in self.db.scalars(statement).all()
        }
