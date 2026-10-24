"""Read-only repository for the public website catalog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.clinic import ClinicSettings, Doctor
from app.models.medical_specialty import MedicalSpecialty
from app.models.public_site_media import PublicSiteMedia
from app.models.service import Service
from app.models.user import User


class PublicSiteReadRepository:
    """Queries active, published candidates for the public website read model."""

    CLINIC_SETTING_KEYS = (
        "clinic_name",
        "clinic_address",
        "clinic_phone",
        "clinic_email",
        "clinic_working_hours_start",
        "clinic_working_hours_end",
    )

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _public_service_filters():
        return (
            Service.active.is_(True),
            Service.show_on_website.is_(True),
        )

    @staticmethod
    def _public_doctor_filters():
        return (
            Doctor.active.is_(True),
            Doctor.show_on_website.is_(True),
            User.is_active.is_(True),
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

    def get_public_doctor_by_id(self, doctor_id: int) -> Doctor | None:
        statement = (
            select(Doctor)
            .join(User, Doctor.user_id == User.id)
            .options(joinedload(Doctor.user))
            .where(*self._public_doctor_filters(), Doctor.id == doctor_id)
        )
        return self.db.scalars(statement).first()

    def get_published_clinic_logo(self) -> PublicSiteMedia | None:
        statement = select(PublicSiteMedia).where(
            PublicSiteMedia.asset_kind == "clinic_logo",
            PublicSiteMedia.is_published.is_(True),
        )
        return self.db.scalars(statement).first()

    def list_published_doctor_media_keys(self, doctor_ids: set[int]) -> dict[int, str]:
        if not doctor_ids:
            return {}
        statement = select(PublicSiteMedia).where(
            PublicSiteMedia.asset_kind == "doctor_portrait",
            PublicSiteMedia.doctor_id.in_(doctor_ids),
            PublicSiteMedia.is_published.is_(True),
        )
        return {
            row.doctor_id: row.storage_key
            for row in self.db.scalars(statement).all()
            if row.doctor_id is not None
        }

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
