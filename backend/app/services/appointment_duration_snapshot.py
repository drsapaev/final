"""Resolve exact service selections and capture their duration at write time."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.department import Department, DepartmentService
from app.models.service import Service

MAX_SNAPSHOT_DURATION_MINUTES = 480


class InvalidServiceSelection(ValueError):
    """Raised when submitted service IDs are unknown or no longer active."""


@dataclass(frozen=True)
class ResolvedServiceSelection:
    service_ids: tuple[int, ...]
    names: tuple[str, ...]
    duration_minutes_snapshot: int | None


def resolve_exact_service_selection(
    db: Session,
    service_ids: list[int] | tuple[int, ...],
    *,
    doctor_id: int | None,
    department_id: int | None = None,
) -> ResolvedServiceSelection:
    """Resolve active catalog rows; only one compatible service has a duration.

    Exact service IDs are also checked against the selected doctor and
    canonical department before an appointment can be written. A snapshot is
    deliberately omitted for multi-service selections or an invalid duration;
    callers must not infer a duration from display names or a later catalog
    read.
    """
    ids = tuple(service_ids)
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in ids
    ):
        raise InvalidServiceSelection("service_ids_invalid")
    if len(set(ids)) != len(ids):
        raise InvalidServiceSelection("service_ids_duplicate")
    if not ids:
        return ResolvedServiceSelection((), (), None)

    rows = db.query(Service).filter(Service.id.in_(ids), Service.active.is_(True)).all()
    rows_by_id = {row.id: row for row in rows}
    if len(rows_by_id) != len(ids):
        raise InvalidServiceSelection("service_not_found_or_inactive")

    ordered = [rows_by_id[service_id] for service_id in ids]
    _validate_service_eligibility(
        db,
        ordered,
        service_ids=list(ids),
        doctor_id=doctor_id,
        department_id=department_id,
    )
    duration: int | None = None
    if len(ordered) == 1 and doctor_id is not None:
        service = ordered[0]
        candidate = service.duration_minutes
        if (
            service.doctor_id in (None, doctor_id)
            and isinstance(candidate, int)
            and not isinstance(candidate, bool)
            and 1 <= candidate <= MAX_SNAPSHOT_DURATION_MINUTES
        ):
            duration = candidate

    return ResolvedServiceSelection(
        service_ids=ids,
        names=tuple(service.name for service in ordered),
        duration_minutes_snapshot=duration,
    )


def _validate_service_eligibility(
    db: Session,
    services: list[Service],
    *,
    service_ids: list[int],
    doctor_id: int | None,
    department_id: int | None,
) -> None:
    """Reject exact service selections incompatible with explicit routing.

    Reuse the clinic's existing service/doctor compatibility policy, which
    checks both a service's exact doctor pin and its department-specialty
    aliases. Department IDs come from the protected portal resolver or an
    existing appointment; direct service bindings and explicit
    ``DepartmentService`` assignments are checked against that canonical row.
    """
    # These policy modules depend on CRUD/user-management modules that also
    # import this resolver. Load them only when a writer resolves an exact
    # selection, after application module initialization has completed.
    from app.repositories.public_booking_settings_repository import (
        PublicBookingSettingsRepository,
    )
    from app.services.registrar_doctor_eligibility import (
        accepted_specialty_variants_for_department_key,
    )

    if doctor_id is not None and not PublicBookingSettingsRepository(
        db
    ).selected_services_match_doctors(service_ids, [doctor_id]):
        raise InvalidServiceSelection("service_incompatible_with_doctor")

    doctor = db.get(Doctor, doctor_id) if doctor_id is not None else None
    target_department_id = department_id or (
        doctor.department_id if doctor is not None else None
    )
    department = (
        db.get(Department, target_department_id)
        if target_department_id is not None
        else None
    )
    if target_department_id is not None and department is None:
        raise InvalidServiceSelection("department_not_found")

    department_links: dict[int, set[int]] = {
        service_id: set() for service_id in service_ids
    }
    for service_id, linked_department_id in (
        db.query(DepartmentService.service_id, DepartmentService.department_id)
        .filter(DepartmentService.service_id.in_(service_ids))
        .all()
    ):
        department_links.setdefault(service_id, set()).add(linked_department_id)

    for service in services:
        if (
            target_department_id is not None
            and service.department_id is not None
            and service.department_id != target_department_id
        ):
            raise InvalidServiceSelection("service_incompatible_with_department")

        linked_departments = department_links.get(service.id, set())
        if (
            target_department_id is not None
            and linked_departments
            and target_department_id not in linked_departments
        ):
            raise InvalidServiceSelection("service_incompatible_with_department")

        if service.department_key and department is not None:
            service_keys = accepted_specialty_variants_for_department_key(
                service.department_key
            )
            selected_keys = accepted_specialty_variants_for_department_key(
                department.key
            )
            if (
                not service_keys
                or not selected_keys
                or not service_keys.intersection(selected_keys)
            ):
                raise InvalidServiceSelection("service_incompatible_with_department")


def duration_snapshot_for_service_id(
    db: Session, service_id: int | None, *, doctor_id: int | None
) -> int | None:
    """Capture one VisitService duration from its active catalog row.

    ``doctor_id`` remains accepted for existing writer call sites, but a
    VisitService snapshot records the catalog service's own duration. Doctor
    and department compatibility is validated by appointment writers, where
    a selected service determines whether an appointment may be created.
    """
    if (
        not isinstance(service_id, int)
        or isinstance(service_id, bool)
        or service_id <= 0
    ):
        return None
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.active.is_(True))
        .one_or_none()
    )
    if service is None:
        return None
    candidate = service.duration_minutes
    if (
        isinstance(candidate, int)
        and not isinstance(candidate, bool)
        and 1 <= candidate <= MAX_SNAPSHOT_DURATION_MINUTES
    ):
        return candidate
    return None
