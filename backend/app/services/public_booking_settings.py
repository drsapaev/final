"""Versioned Admin configuration for the first public booking release."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings
from app.repositories.public_booking_settings_repository import (
    PublicBookingSettingsRepository,
)
from app.schemas.public_booking_settings import (
    PublicBookingMode,
    PublicBookingOptionOut,
    PublicBookingSettingsOut,
    PublicBookingSettingsUpdate,
)

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
