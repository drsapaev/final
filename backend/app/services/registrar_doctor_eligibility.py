"""Shared doctor-selection policy for registrar reads and write commands."""

from __future__ import annotations

from collections.abc import Set
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import is_doctor_role_spelling
from app.crud.queue_resource_routing import resolve_tag_resource, tag_routes_to_resource
from app.models.clinic import Doctor
from app.models.service import Service
from app.models.user import User
from app.services.user_mgmt._base import is_doctor_profile_incomplete

# Existing queue specialty vocabulary, shared with doctor integration. Keep
# these aliases together so registrar catalog and command gates cannot drift.
DOCTOR_QUEUE_SPECIALTY_VARIANTS: dict[str, list[str]] = {
    "cardiology": ["cardiology", "cardio", "Cardiologist", "Cardio", "cardiology_common", "Кардиология"],
    "cardio": ["cardiology", "cardio", "Cardiologist", "Cardio", "cardiology_common", "Кардиология"],
    "cardiology_common": ["cardiology", "cardio", "Cardiologist", "Cardio", "cardiology_common", "Кардиология"],
    "derma": ["derma", "dermatology", "Dermatologist"],
    "dermatology": ["derma", "dermatology", "Dermatologist"],
    "dentist": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "dentistry": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "stomatology": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "lab": ["lab", "laboratory", "Laboratory"],
    "laboratory": ["lab", "laboratory", "Laboratory"],
    "general": ["general", "therapy", "therapist", "general_practice"],
}


def accepted_specialty_variants_for_department_key(
    department_key: str | None,
) -> set[str] | None:
    """Allowed clinician specialties for a service department.

    Reverse alias matching admits e.g. dental/dentistry. An unknown key
    matches exactly; a missing key does not impose a specialty restriction.
    """
    key = (department_key or "").strip().lower()
    if not key:
        return None
    for variants in DOCTOR_QUEUE_SPECIALTY_VARIANTS.values():
        lowered = {variant.strip().lower() for variant in variants}
        if key in lowered:
            return lowered
    return {key}


def service_requires_doctor_selection(service: Service) -> bool:
    """Selection rule; never rewrite queue-ownership ``requires_doctor``."""
    return bool(service.requires_doctor or service.is_consultation)


def doctor_booking_unavailable_reason(
    service: Service, active_resource_tags: Set[str]
) -> str | None:
    """Why a consultation cannot be booked to a doctor-owned queue."""
    if not service.is_consultation:
        return None
    if not service.queue_tag:
        return "missing_queue_tag"
    if service.queue_tag in active_resource_tags:
        return "resource_queue"
    return None


def is_named_eligible_real_doctor(doctor: Doctor, owner: User | None) -> bool:
    """Registrar roster and command eligibility for a selectable doctor.

    Mirrors the canonical real-doctor rules used by queue owners, with the
    additional registrar requirement that the clinician has a usable name.
    """
    return bool(
        doctor.active
        and not is_doctor_profile_incomplete(doctor.specialty)
        and owner is not None
        and owner.is_active
        and is_doctor_role_spelling(owner.role)
        and (owner.full_name or "").strip()
    )


def assert_doctor_eligible_for_service(
    db: Session,
    service: Service,
    doctor_id: int | None,
    *,
    doctor_map: dict[int, Doctor] | None = None,
    target_date: date | None = None,
) -> None:
    """Validate a doctor-required service before any registrar write."""
    if not service_requires_doctor_selection(service):
        return
    if not doctor_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Услуга «{service.name}» требует выбора врача: "
                "сохранение визита без врача недоступно"
            ),
        )
    doctor = (
        doctor_map.get(doctor_id)
        if doctor_map is not None
        else db.query(Doctor).filter(Doctor.id == doctor_id).first()
    )
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Врач с ID {doctor_id} не найден",
        )
    if not doctor.active:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Выбранный врач (ID {doctor.id}) неактивен: "
                "выберите действующего врача"
            ),
        )
    if not is_named_eligible_real_doctor(doctor, doctor.user):
        raise HTTPException(
            status_code=409,
            detail=(
                "Профиль врача не готов к записи: нужна активная врачебная "
                "учётная запись, специализация и фамилия с именем"
            ),
        )
    if service.is_consultation and target_date is None:
        raise HTTPException(
            status_code=409,
            detail="Для консультации не определён день очереди врача",
        )
    resource_tags = (
        {service.queue_tag}
        if service.is_consultation
        and service.queue_tag
        and resolve_tag_resource(db, service.queue_tag) is not None
        else set()
    )
    if service.is_consultation and service.queue_tag and target_date is not None:
        surface = tag_routes_to_resource(db, service.queue_tag, target_date)
        if surface is not None and surface.queue_resource_id is not None:
            resource_tags.add(service.queue_tag)
    route_block = doctor_booking_unavailable_reason(service, resource_tags)
    if route_block == "missing_queue_tag":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Консультацию «{service.name}» нельзя записать: "
                "для неё не настроен тег очереди врача"
            ),
        )
    if route_block == "resource_queue":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Консультацию «{service.name}» нельзя записать к врачу: "
                "её очередь настроена как ресурсная"
            ),
        )
    accepted = accepted_specialty_variants_for_department_key(
        service.department_key
    )
    doctor_specialty = (doctor.specialty or "").strip().lower()
    if accepted is None or doctor_specialty in accepted:
        return
    raise HTTPException(
        status_code=400,
        detail=(
            f"Врач (ID {doctor.id}, специальность "
            f"«{doctor.specialty}») не подходит для услуги "
            f"«{service.name}» (отделение «{service.department_key}»)"
        ),
    )
