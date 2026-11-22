"""Database access for Admin-managed public booking settings."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings, Doctor
from app.models.online_queue import QueueResource
from app.models.service import Service
from app.models.user import User
from app.services.registrar_doctor_eligibility import (
    accepted_specialty_variants_for_department_key,
    doctor_booking_unavailable_reason,
    is_named_eligible_real_doctor,
    service_has_explicit_doctor_assignment,
    service_requires_doctor_selection,
)


@dataclass(frozen=True, slots=True)
class BookingCatalogOption:
    id: int
    label: str | None
    eligible: bool
    slug: str | None = None


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
                Service.is_consultation,
                Service.doctor_id,
                Service.queue_tag,
                Service.department_key,
                Service.active,
                Service.show_on_website,
            )
            .where(or_(*filters))
            .order_by(Service.name, Service.id)
        ).all()
        resource_routed_tags = set(
            self.db.scalars(
                select(QueueResource.queue_tag).where(QueueResource.active.is_(True))
            ).all()
        )
        pinned_doctor_ids = sorted(
            {row.doctor_id for row in rows if row.doctor_id is not None}
        )
        eligible_pinned_doctor_ids: set[int] = set()
        if pinned_doctor_ids:
            pinned_doctor_options = self.list_doctor_options(pinned_doctor_ids)
            eligible_pinned_doctor_ids = {
                option.id for option in pinned_doctor_options if option.eligible
            }
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
                    and (
                        service_requires_doctor_selection(row)
                        or service_has_explicit_doctor_assignment(row)
                    )
                    and doctor_booking_unavailable_reason(row, resource_routed_tags)
                    is None
                    and (
                        row.doctor_id is None
                        or row.doctor_id in eligible_pinned_doctor_ids
                    )
                ),
                slug=_clean(row.slug),
            )
            for row in rows
        ]
        return _append_missing(options, selected_ids)

    def selected_services_match_doctors(
        self, service_ids: list[int], doctor_ids: list[int]
    ) -> bool:
        """Return whether each selected service can use an allowed doctor.

        Appointment writes enforce both an exact ``Service.doctor_id`` pin
        and the service department's accepted doctor-specialty variants.
        Settings must not report ready when the independent allowlists have
        no compatible service/doctor pair.
        """
        if not service_ids or not doctor_ids:
            return False
        pairs = self.compatible_service_doctor_pairs(service_ids, doctor_ids)
        compatible_service_ids = {service_id for service_id, _ in pairs}
        return all(
            service_id in compatible_service_ids for service_id in set(service_ids)
        )

    def compatible_service_doctor_pairs(
        self, service_ids: list[int], doctor_ids: list[int]
    ) -> list[tuple[int, int]]:
        """Return exact eligible service/doctor pairs used by booking writes."""
        if not service_ids or not doctor_ids:
            return []

        unique_service_ids = set(service_ids)
        unique_doctor_ids = set(doctor_ids)
        service_rows = self.db.execute(
            select(Service.id, Service.doctor_id, Service.department_key).where(
                Service.id.in_(unique_service_ids)
            )
        ).all()
        if len(service_rows) != len(unique_service_ids):
            return []

        doctor_rows = self.db.execute(
            select(Doctor.id, Doctor.specialty).where(Doctor.id.in_(unique_doctor_ids))
        ).all()
        specialties = {row.id: row.specialty for row in doctor_rows}
        if len(specialties) != len(unique_doctor_ids):
            return []

        pairs: list[tuple[int, int]] = []
        for service in service_rows:
            accepted_specialties = accepted_specialty_variants_for_department_key(
                service.department_key
            )
            for doctor_id in unique_doctor_ids:
                if service.doctor_id is not None and service.doctor_id != doctor_id:
                    continue
                if (
                    accepted_specialties is not None
                    and (specialties[doctor_id] or "").strip().lower()
                    not in accepted_specialties
                ):
                    continue
                pairs.append((service.id, doctor_id))
        return pairs

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
                User.id.label("owner_id"),
                Doctor.specialty,
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
                    and is_named_eligible_real_doctor(
                        SimpleNamespace(active=row.active, specialty=row.specialty),
                        (
                            SimpleNamespace(
                                is_active=row.user_active,
                                role=row.role,
                                full_name=row.full_name,
                            )
                            if row.owner_id is not None
                            else None
                        ),
                    )
                    and all(
                        _clean(value) is not None
                        for value in (row.full_name, row.bio_ru, row.bio_uz, row.slug)
                    )
                ),
                slug=_clean(row.slug),
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
        BookingCatalogOption(id=item, label=None, eligible=False, slug=None)
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
