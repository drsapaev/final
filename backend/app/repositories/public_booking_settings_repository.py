"""Database access for Admin-managed public booking settings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings, Doctor
from app.models.service import Service
from app.models.user import User


@dataclass(frozen=True, slots=True)
class BookingCatalogOption:
    id: int
    label: str | None
    eligible: bool


class PublicBookingSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_settings_row(self, *, lock: bool = False) -> ClinicSettings | None:
        statement = select(ClinicSettings).where(
            ClinicSettings.key == "public_booking_settings"
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalars(statement).one_or_none()

    def list_service_options(
        self, selected_ids: list[int]
    ) -> list[BookingCatalogOption]:
        public_candidate = and_(
            Service.active.is_(True), Service.show_on_website.is_(True)
        )
        filters = [public_candidate]
        if selected_ids:
            filters.append(Service.id.in_(selected_ids))
        rows = self.db.execute(
            select(
                Service.id,
                Service.name,
                Service.name_uz,
                Service.description_ru,
                Service.description_uz,
                Service.slug,
                Service.duration_minutes,
                Service.requires_doctor,
                Service.active,
                Service.show_on_website,
            )
            .where(or_(*filters))
            .order_by(Service.name, Service.id)
        ).all()
        options = [
            BookingCatalogOption(
                id=row.id,
                label=_clean(row.name),
                eligible=(
                    row.active
                    and row.show_on_website
                    and all(
                        _clean(value) is not None
                        for value in (
                            row.name,
                            row.name_uz,
                            row.description_ru,
                            row.description_uz,
                            row.slug,
                        )
                    )
                    and isinstance(row.duration_minutes, int)
                    and 1 <= row.duration_minutes <= 480
                    and row.requires_doctor
                ),
            )
            for row in rows
        ]
        return _append_missing(options, selected_ids)

    def list_doctor_options(
        self, selected_ids: list[int]
    ) -> list[BookingCatalogOption]:
        public_candidate = and_(
            Doctor.active.is_(True),
            Doctor.show_on_website.is_(True),
            User.is_active.is_(True),
        )
        filters = [public_candidate]
        if selected_ids:
            filters.append(Doctor.id.in_(selected_ids))
        rows = self.db.execute(
            select(
                Doctor.id,
                User.full_name,
                User.role,
                Doctor.bio_ru,
                Doctor.bio_uz,
                Doctor.slug,
                Doctor.active,
                Doctor.show_on_website,
                User.is_active.label("user_active"),
            )
            .outerjoin(User, Doctor.user_id == User.id)
            .where(or_(*filters))
            .order_by(User.full_name, Doctor.id)
        ).all()
        options = [
            BookingCatalogOption(
                id=row.id,
                label=_clean(row.full_name),
                eligible=(
                    row.active
                    and row.show_on_website
                    and row.user_active is True
                    and row.role != "Resource"
                    and all(
                        _clean(value) is not None
                        for value in (row.full_name, row.bio_ru, row.bio_uz, row.slug)
                    )
                ),
            )
            for row in rows
        ]
        return _append_missing(options, selected_ids)


def _clean(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _append_missing(
    options: list[BookingCatalogOption], selected_ids: list[int]
) -> list[BookingCatalogOption]:
    present = {option.id for option in options}
    options.extend(
        BookingCatalogOption(id=item, label=None, eligible=False)
        for item in selected_ids
        if item not in present
    )
    return sorted(
        options,
        key=lambda option: (
            option.label is None,
            (option.label or "").casefold(),
            option.id,
        ),
    )
