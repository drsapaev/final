"""Versioned Admin configuration for the first public booking release."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings
from app.repositories.public_booking_settings_repository import (
    PublicBookingSettingsRepository,
)
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.schemas.public_booking_availability import (
    PublicBookingCatalogOptionOut,
    PublicBookingCompatiblePairOut,
    PublicBookingOptionsOut,
)
from app.schemas.public_booking_settings import (
    PublicBookingMode,
    PublicBookingOptionOut,
    PublicBookingSettingsOut,
    PublicBookingSettingsUpdate,
)
from app.schemas.public_site import PublicSiteLocale
from app.services.public_site_read_service import PublicSiteReadService

PUBLIC_BOOKING_SETTINGS_KEY = "public_booking_settings"
PUBLIC_BOOKING_SETTINGS_CATEGORY = "booking_settings"


class PublicBookingSettingsError(Exception):
    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class _StoredSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    is_enabled: bool = False
    mode: PublicBookingMode | None = None
    booking_horizon_days: int | None = Field(default=None, ge=1, le=365)
    service_ids: list[int] = Field(max_length=500)
    doctor_ids: list[int] = Field(max_length=500)


def is_public_booking_settings_key(key: str) -> bool:
    return key == PUBLIC_BOOKING_SETTINGS_KEY


class PublicBookingSettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PublicBookingSettingsRepository(db)

    def get_settings(self) -> PublicBookingSettingsOut:
        row = self.repository.get_settings_row()
        self._ensure_category(row)
        stored = self._load(row.value) if row is not None else None
        return self._to_output(stored=stored, row=row)

    def get_patient_booking_service_ids(self) -> list[int]:
        """Return only selected services that remain eligible for publication.

        Website publication and online-booking approval are separate facts:
        membership in the Admin allowlist is required, and current service
        eligibility removes stale entries that are now inactive or unpublished.
        """
        settings = self.get_settings()
        eligible_ids = {option.id for option in settings.services if option.eligible}
        return [
            service_id
            for service_id in settings.service_ids
            if service_id in eligible_ids
        ]

    def get_public_booking_options(
        self, locale: PublicSiteLocale
    ) -> PublicBookingOptionsOut:
        """Return only current, Admin-approved public booking choices.

        The public contract intentionally contains slugs and localized public
        labels, never database IDs or Admin-only settings metadata. Invalid or
        disabled configuration fails closed with an empty choice list.
        """
        settings = self.get_settings()
        base = {
            "settings_version": settings.version,
            "available": False,
            "mode": settings.mode,
            "booking_horizon_days": settings.booking_horizon_days,
            "services": [],
            "doctors": [],
            "compatible_pairs": [],
        }
        if not settings.is_enabled or not settings.is_ready:
            return PublicBookingOptionsOut(**base)

        approved_service_ids = set(settings.service_ids)
        approved_doctor_ids = set(settings.doctor_ids)
        selected_service_slugs = {
            option.id: option.slug
            for option in self.repository.list_service_options(settings.service_ids)
            if option.id in approved_service_ids and option.eligible and option.slug
        }
        selected_doctor_slugs = {
            option.id: option.slug
            for option in self.repository.list_doctor_options(settings.doctor_ids)
            if option.id in approved_doctor_ids and option.eligible and option.slug
        }
        candidate_pairs = self.repository.compatible_service_doctor_pairs(
            list(selected_service_slugs), list(selected_doctor_slugs)
        )

        public_read = PublicSiteReadService(PublicSiteReadRepository(self.db))
        public_services = {
            option.slug: option
            for option in public_read.list_services(locale)
            if option.slug
        }
        public_doctors = {
            option.slug: option
            for option in public_read.list_doctors(locale)
            if option.slug
        }
        pairs = {
            (
                selected_service_slugs[service_id],
                selected_doctor_slugs[doctor_id],
            )
            for service_id, doctor_id in candidate_pairs
            if service_id in selected_service_slugs
            and doctor_id in selected_doctor_slugs
            and selected_service_slugs[service_id] in public_services
            and selected_doctor_slugs[doctor_id] in public_doctors
        }
        if not pairs:
            return PublicBookingOptionsOut(**base)

        service_slugs = {service_slug for service_slug, _ in pairs}
        doctor_slugs = {doctor_slug for _, doctor_slug in pairs}
        return PublicBookingOptionsOut(
            **{
                **base,
                "available": True,
                "services": [
                    PublicBookingCatalogOptionOut(
                        slug=slug, name=public_services[slug].name
                    )
                    for slug in sorted(
                        service_slugs,
                        key=lambda value: public_services[value].name.casefold(),
                    )
                ],
                "doctors": [
                    PublicBookingCatalogOptionOut(
                        slug=slug, name=public_doctors[slug].name
                    )
                    for slug in sorted(
                        doctor_slugs,
                        key=lambda value: public_doctors[value].name.casefold(),
                    )
                ],
                "compatible_pairs": [
                    PublicBookingCompatiblePairOut(
                        service_slug=service_slug, doctor_slug=doctor_slug
                    )
                    for service_slug, doctor_slug in sorted(pairs)
                ],
            }
        )

    def validate_patient_booking_service_selection(
        self,
        *,
        service_ids: list[int] | None,
        services: list[str] | None,
    ) -> None:
        """Reject selected services without exact IDs or outside the Admin allowlist."""
        requested_ids = service_ids or []
        has_named_services = bool(services)
        if not requested_ids and not has_named_services:
            return
        if has_named_services and not requested_ids:
            raise PublicBookingSettingsError(400, "booking_service_id_required")

        allowed_ids = set(self.get_patient_booking_service_ids())
        if any(service_id not in allowed_ids for service_id in requested_ids):
            raise PublicBookingSettingsError(400, "booking_service_not_approved")

    def update_settings(
        self, *, update: PublicBookingSettingsUpdate, actor_user_id: int
    ) -> PublicBookingSettingsOut:
        row = self.repository.get_settings_row(lock=True)
        self._ensure_category(row)
        current = self._load(row.value) if row is not None else None
        current_version = current.version if current is not None else 0
        if update.expected_version != current_version:
            raise PublicBookingSettingsError(409, "booking_settings_version_conflict")

        services = self.repository.list_service_options(update.service_ids)
        doctors = self.repository.list_doctor_options(update.doctor_ids)
        service_by_id = {item.id: item for item in services}
        doctor_by_id = {item.id: item for item in doctors}
        selected_eligible = (
            bool(update.service_ids)
            and bool(update.doctor_ids)
            and all(
                service_by_id.get(item) and service_by_id[item].eligible
                for item in update.service_ids
            )
            and all(
                doctor_by_id.get(item) and doctor_by_id[item].eligible
                for item in update.doctor_ids
            )
            and self.repository.selected_services_match_doctors(
                update.service_ids, update.doctor_ids
            )
        )
        ready = bool(
            update.mode is not None
            and update.booking_horizon_days is not None
            and selected_eligible
        )
        if update.is_enabled and not ready:
            raise PublicBookingSettingsError(422, "booking_settings_incomplete")

        stored = _StoredSettings(
            version=current_version + 1,
            is_enabled=update.is_enabled,
            mode=update.mode,
            booking_horizon_days=update.booking_horizon_days,
            service_ids=update.service_ids,
            doctor_ids=update.doctor_ids,
        )
        if row is None:
            row = ClinicSettings(
                key=PUBLIC_BOOKING_SETTINGS_KEY,
                category=PUBLIC_BOOKING_SETTINGS_CATEGORY,
                value=stored.model_dump(mode="json"),
                updated_by=actor_user_id,
            )
            self.db.add(row)
        else:
            row.category = PUBLIC_BOOKING_SETTINGS_CATEGORY
            row.value = stored.model_dump(mode="json")
            row.updated_by = actor_user_id

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PublicBookingSettingsError(
                409, "booking_settings_version_conflict"
            ) from exc
        self.db.refresh(row)
        return self._to_output(stored=stored, row=row)

    @staticmethod
    def _load(value: object) -> _StoredSettings:
        try:
            stored = _StoredSettings.model_validate(value)
        except ValidationError as exc:
            raise PublicBookingSettingsError(503, "booking_settings_invalid") from exc
        if any(item <= 0 for item in (*stored.service_ids, *stored.doctor_ids)):
            raise PublicBookingSettingsError(503, "booking_settings_invalid")
        if len(stored.service_ids) != len(set(stored.service_ids)) or len(
            stored.doctor_ids
        ) != len(set(stored.doctor_ids)):
            raise PublicBookingSettingsError(503, "booking_settings_invalid")
        if stored.is_enabled and (
            stored.mode is None
            or stored.booking_horizon_days is None
            or not stored.service_ids
            or not stored.doctor_ids
        ):
            raise PublicBookingSettingsError(503, "booking_settings_invalid")
        return stored

    @staticmethod
    def _ensure_category(row: ClinicSettings | None) -> None:
        if row is not None and row.category != PUBLIC_BOOKING_SETTINGS_CATEGORY:
            raise PublicBookingSettingsError(503, "booking_settings_invalid")

    def _to_output(
        self, *, stored: _StoredSettings | None, row: ClinicSettings | None
    ) -> PublicBookingSettingsOut:
        service_ids = stored.service_ids if stored else []
        doctor_ids = stored.doctor_ids if stored else []
        services = self.repository.list_service_options(service_ids)
        doctors = self.repository.list_doctor_options(doctor_ids)
        service_by_id = {item.id: item for item in services}
        doctor_by_id = {item.id: item for item in doctors}
        ready = bool(
            stored is not None
            and stored.mode is not None
            and stored.booking_horizon_days is not None
            and service_ids
            and doctor_ids
            and all(
                service_by_id.get(item) and service_by_id[item].eligible
                for item in service_ids
            )
            and all(
                doctor_by_id.get(item) and doctor_by_id[item].eligible
                for item in doctor_ids
            )
            and self.repository.selected_services_match_doctors(service_ids, doctor_ids)
        )
        return PublicBookingSettingsOut(
            version=stored.version if stored is not None else 0,
            is_enabled=stored.is_enabled if stored is not None else False,
            is_ready=ready,
            mode=stored.mode if stored is not None else None,
            booking_horizon_days=(stored.booking_horizon_days if stored else None),
            service_ids=service_ids,
            doctor_ids=doctor_ids,
            services=[
                PublicBookingOptionOut(
                    id=option.id, label=option.label, eligible=option.eligible
                )
                for option in services
            ],
            doctors=[
                PublicBookingOptionOut(
                    id=option.id, label=option.label, eligible=option.eligible
                )
                for option in doctors
            ],
            updated_at=row.updated_at if row is not None else None,
            updated_by=row.updated_by if row is not None else None,
        )
