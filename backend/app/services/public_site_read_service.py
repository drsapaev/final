"""Public website read model and publication filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.schemas.public_site import (
    PublicSiteCategoryOut,
    PublicSiteClinicOut,
    PublicSiteDoctorOut,
    PublicSiteLocale,
    PublicSiteServiceOut,
)

if TYPE_CHECKING:
    from app.models.clinic import Doctor
    from app.models.service import Service


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _localized(
    russian: str | None, uzbek: str | None, locale: PublicSiteLocale
) -> str | None:
    # Deliberately do not substitute one language for the requested locale.
    return _clean_text(russian if locale == "ru" else uzbek)


class PublicSiteReadService:
    """Build stable public DTOs from the existing Clinic OS source of truth."""

    def __init__(self, repository: PublicSiteReadRepository) -> None:
        self.repository = repository

    def get_clinic(self) -> PublicSiteClinicOut:
        settings = self.repository.get_public_clinic_settings()

        def value(key: str) -> str | None:
            return _clean_text(settings.get(key))

        return PublicSiteClinicOut(
            name=value("clinic_name"),
            address=value("clinic_address"),
            phone=value("clinic_phone"),
            email=value("clinic_email"),
        )

    @staticmethod
    def _category_name(category, locale: PublicSiteLocale) -> str | None:
        if category is None or not category.active:
            return None
        name_ru = _clean_text(category.name_ru)
        name_uz = _clean_text(category.name_uz)
        if not name_ru or not name_uz:
            return None
        return name_ru if locale == "ru" else name_uz

    @staticmethod
    def _service_content_is_complete(service: Service) -> bool:
        """Use one Python whitespace rule for selecting and shaping a card."""
        return all(
            _clean_text(value) is not None
            for value in (
                service.slug,
                service.name,
                service.name_uz,
                service.description_ru,
                service.description_uz,
            )
        )

    @staticmethod
    def _doctor_content_is_complete(doctor: Doctor) -> bool:
        """A public doctor card requires a name and both localized bios."""
        return all(
            _clean_text(value) is not None
            for value in (
                doctor.slug,
                doctor.user.full_name if doctor.user else None,
                doctor.bio_ru,
                doctor.bio_uz,
            )
        )

    def _eligible_services(self) -> list[Service]:
        return [
            row
            for row in self.repository.list_public_services()
            if self._service_content_is_complete(row)
        ]

    def _eligible_doctors(self) -> list[Doctor]:
        return [
            row
            for row in self.repository.list_public_doctors()
            if self._doctor_content_is_complete(row)
        ]

    @classmethod
    def _service_out(
        cls, service: Service, locale: PublicSiteLocale
    ) -> PublicSiteServiceOut | None:
        if not cls._service_content_is_complete(service):
            return None

        name = _localized(service.name, service.name_uz, locale)
        description = _localized(service.description_ru, service.description_uz, locale)
        # Completeness was checked for both locales before serialization.
        if name is None or description is None or service.slug is None:
            return None

        price = service.price
        currency = _clean_text(service.currency)
        # Do not publish an amount without its unit.
        if price is not None and currency is None:
            price = None

        return PublicSiteServiceOut(
            slug=service.slug,
            name=name,
            description=description,
            price=price,
            currency=currency,
            category=cls._category_name(service.category, locale),
        )

    def list_services(self, locale: PublicSiteLocale) -> list[PublicSiteServiceOut]:
        result = []
        for row in self._eligible_services():
            card = self._service_out(row, locale)
            if card is not None:
                result.append(card)
        return result

    def get_service(
        self, slug: str, locale: PublicSiteLocale
    ) -> PublicSiteServiceOut | None:
        row = self.repository.get_public_service_by_slug(slug)
        return self._service_out(row, locale) if row is not None else None

    @classmethod
    def _category_rows(
        cls, services: list[Service], locale: PublicSiteLocale
    ) -> list[PublicSiteCategoryOut]:
        names: dict[int, str] = {}
        for service in services:
            category = service.category
            name = cls._category_name(category, locale)
            if category is not None and name is not None:
                names[category.id] = name
        # The public DTO exposes labels only, so repeated localized labels
        # intentionally represent one category in the selected locale.
        unique_names = sorted(set(names.values()), key=str.casefold)
        return [PublicSiteCategoryOut(name=name) for name in unique_names]

    def list_categories(self, locale: PublicSiteLocale) -> list[PublicSiteCategoryOut]:
        return self._category_rows(self._eligible_services(), locale)

    @staticmethod
    def _doctor_out(
        doctor: Doctor,
        locale: PublicSiteLocale,
        specialties: dict[str, object],
    ) -> PublicSiteDoctorOut | None:
        if not PublicSiteReadService._doctor_content_is_complete(doctor):
            return None

        name = _clean_text(doctor.user.full_name if doctor.user else None)
        bio = _localized(doctor.bio_ru, doctor.bio_uz, locale)
        if name is None or bio is None or doctor.slug is None:
            return None

        specialty_title = None
        specialty = specialties.get(doctor.specialty)
        if specialty is not None:
            specialty_title = _localized(specialty.title_ru, specialty.title_uz, locale)

        return PublicSiteDoctorOut(
            slug=doctor.slug,
            name=name,
            bio=bio,
            specialty=specialty_title,
        )

    def list_doctors(self, locale: PublicSiteLocale) -> list[PublicSiteDoctorOut]:
        doctors = self._eligible_doctors()
        specialties = self.repository.list_specialties_by_code(
            {doctor.specialty for doctor in doctors if doctor.specialty}
        )
        result = []
        for doctor in doctors:
            card = self._doctor_out(doctor, locale, specialties)
            if card is not None:
                result.append(card)
        return result

    def get_doctor(
        self, slug: str, locale: PublicSiteLocale
    ) -> PublicSiteDoctorOut | None:
        doctor = self.repository.get_public_doctor_by_slug(slug)
        if doctor is None or not self._doctor_content_is_complete(doctor):
            return None
        specialties = self.repository.list_specialties_by_code(
            {doctor.specialty} if doctor.specialty else set()
        )
        return self._doctor_out(doctor, locale, specialties)
