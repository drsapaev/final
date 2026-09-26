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
    """Selection rule; never rewrite queue-ownership ``requires_doctor``.

    Raw catalog flags only: a service is clinician-performed when the
    catalog says ``requires_doctor`` or ``is_consultation``. Queue
    OWNERSHIP (does the tag route to a resource axis instead of a doctor)
    is a separate question — see :func:`service_routes_to_resource_queue`
    and :func:`doctor_selection_required_for_surface`.
    """
    return bool(service.requires_doctor or service.is_consultation)


def service_routes_to_resource_queue(
    db: Session,
    service: Service,
    target_date: date | None = None,
    *,
    resource_routed_tags: Set[str] | None = None,
) -> bool:
    """Does the service's queue_tag route to the resource-owned axis?

    PR #3438 review P1-1: ``requires_doctor``/``is_consultation`` alone say
    NOTHING about queue ownership. The canonical seed carries K10 «ЭКГ»
    with ``requires_doctor=True`` while its ``ecg`` tag is a registry
    QueueResource — the queue entry ALWAYS lands in the resource-owned
    queue (the assignment pass nulls the specialist for registry tags),
    so a doctor picked for such a service would be decorative.

    Routing truth mirrors the write-side surface exactly:

    - with ``target_date``: an existing resource-owned (day, tag) surface
      (``tag_routes_to_resource``, deactivation-proof — the day's open
      resource queue stays the surface after a mid-day registry
      deactivation) OR an ACTIVE registry row for the exact tag (the
      first booking of the day will create the resource queue — the
      stage-C switch);
    - without a date: an ACTIVE registry row for the exact tag
      (``resolve_tag_resource``);
    - ``resource_routed_tags``: precomputed batch (see
      :func:`resource_routed_tags_for_day`) with the SAME semantics —
      the catalog passes it to avoid per-service queries.
    """
    tag = (service.queue_tag or "").strip()
    if not tag:
        return False
    if resource_routed_tags is not None:
        return tag in resource_routed_tags
    if (
        target_date is not None
        and tag_routes_to_resource(db, tag, target_date) is not None
    ):
        return True
    return resolve_tag_resource(db, tag) is not None


def resource_routed_tags_for_day(db: Session, target_date: date) -> set[str]:
    """Batched ``tag_routes_to_resource`` truth for every tag at once.

    The registrar catalog classifies every service in one request; calling
    the per-tag resolver per service is an N+1 read model. This builds the
    SAME answer with two queries: the active registry rows (stage-C switch)
    plus the day's existing resource-owned surfaces, with the per-tag
    FIRST-active-queue-wins rule of ``find_active_tag_queue`` preserved
    (a tag whose first active (day, tag) queue is doctor-owned does not
    become resource-routed by a LATER resource queue unless the registry
    row is active).
    """
    from app.models.online_queue import DailyQueue, QueueResource

    registry_tags = {
        tag
        for (tag,) in (
            db.query(QueueResource.queue_tag)
            .filter(QueueResource.active.is_(True))
            .all()
        )
        if tag
    }
    first_queue_is_resource: dict[str, bool] = {}
    rows = (
        db.query(DailyQueue.queue_tag, DailyQueue.queue_resource_id)
        .filter(
            DailyQueue.day == target_date,
            DailyQueue.active.is_(True),
        )
        .order_by(DailyQueue.id.asc())
        .all()
    )
    for tag, queue_resource_id in rows:
        if tag and tag not in first_queue_is_resource:
            first_queue_is_resource[tag] = queue_resource_id is not None
    surface_tags = {
        tag for tag, is_resource in first_queue_is_resource.items() if is_resource
    }
    return registry_tags | surface_tags


def doctor_selection_required_for_surface(
    db: Session,
    service: Service,
    target_date: date | None = None,
    *,
    resource_routed_tags: Set[str] | None = None,
) -> bool:
    """Server decision: must the registrar pick a doctor for this service?

    PR #3438 review P1-1 — the three ownership classes:

    - **doctor-owned**: clinician-performed and the tag routes to a
      doctor's queue → selection required (doctor cards in the wizard);
    - **resource-owned**: clinician-performed flag set, NOT a consultation,
      and the tag routes to the resource axis (canonical K10 «ЭКГ»/ecg,
      lab) → NO doctor selection: the service stays on the resource/
      general surface and books into the resource queue without a doctor;
    - **ambiguous**: a CONSULTATION whose tag routes to the resource axis
      (mixed semantics — the 0059 seed gate aborts on exactly this) →
      selection stays required and doctor booking is unavailable: the
      misconfiguration fails closed instead of silently booking a
      clinician consult into a staff-served resource queue.
    """
    if not service_requires_doctor_selection(service):
        return False
    if service.is_consultation:
        return True
    routed = service_routes_to_resource_queue(
        db, service, target_date, resource_routed_tags=resource_routed_tags
    )
    return not routed


def doctor_booking_unavailable_reason(
    service: Service, resource_routed_tags: Set[str]
) -> str | None:
    """Why a clinician-performed service cannot be booked to a doctor.

    PR #3438 review P1-1/P2: applies to EVERY doctor-selection service, not
    only consultations — a ``requires_doctor`` service whose tag routes to
    the resource axis is not doctor-bookable either (the runtime owner is
    the resource, a doctor_id would be decorative). The tag set is the
    date-aware routing truth (``resource_routed_tags_for_day``).
    """
    if not service_requires_doctor_selection(service):
        return None
    if not service.queue_tag:
        return "missing_queue_tag" if service.is_consultation else None
    if service.queue_tag in resource_routed_tags:
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
    # PR #3438 review P1-1: queue ownership decides the doctor surface.
    # A non-consultation doctor-selection service whose queue_tag routes
    # to the resource axis (canonical K10 «ЭКГ»/ecg) is RESOURCE-OWNED:
    # the assignment pass nulls the specialist for registry tags, so a
    # doctor on the visit would be decorative and the per-doctor worklist
    # would never count the entry. Fail closed with 409 when a doctor was
    # supplied, and require NO doctor otherwise — the resource surface
    # books without one. (Consultations keep the dedicated checks below.)
    if not service.is_consultation and service_routes_to_resource_queue(
        db, service, target_date
    ):
        if doctor_id is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Услугу «{service.name}» нельзя записать к врачу: "
                    "её очередь настроена как ресурсная"
                ),
            )
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
    accepted = accepted_specialty_variants_for_department_key(service.department_key)
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
