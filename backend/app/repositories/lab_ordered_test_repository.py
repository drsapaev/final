"""Canonical visit service lines eligible for explicit laboratory allocation."""

from sqlalchemy import and_, case, func, or_, select

from app.models.department import Department
from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabOrder,
    LabOrderTest,
    LabReportInstance,
)
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.service_mapping import (
    QUEUE_GROUPS,
    SPECIALTY_ALIASES,
    SPECIALTY_TO_QUEUE_GROUP,
    resolve_queue_group_key,
)

_LAB_GROUP = "laboratory"
_ROUTING_HINTS = {
    hint: resolve_queue_group_key(queue_tag=hint)
    for hint in (
        QUEUE_GROUPS.keys()
        | SPECIALTY_ALIASES.keys()
        | SPECIALTY_TO_QUEUE_GROUP.keys()
        | {group["tab_key"] for group in QUEUE_GROUPS.values()}
    )
}
LAB_DEPARTMENT_HINTS = tuple(
    sorted(hint for hint, group in _ROUTING_HINTS.items() if group == _LAB_GROUP)
)
INACTIVE_LAB_VISIT_STATUSES = (
    "canceled",
    "cancelled",
    "no_show",
    "no-show",
    "archived",
)


def unallocated_lab_report_visits():
    return (
        select(LabReportInstance.visit_id)
        .join(
            Visit,
            and_(
                Visit.id == LabReportInstance.visit_id,
                Visit.patient_id == LabReportInstance.patient_id,
            ),
        )
        .where(
            LabReportInstance.supersedes_instance_id.is_(None),
            ~select(LabOrderTest.id)
            .where(LabOrderTest.report_instance_id == LabReportInstance.id)
            .exists(),
        )
    )


def unallocated_lab_release_history():
    return (
        unallocated_lab_report_visits()
        .with_only_columns(
            LabReportInstance.visit_id,
            func.max(LabReportInstance.finalized_at).label("latest_release"),
            func.count()
            .filter(LabReportInstance.finalized_at.is_(None))
            .label("missing_release_dates"),
        )
        .where(LabReportInstance.status.in_(FINAL_INSTANCE_STATUSES))
        .group_by(LabReportInstance.visit_id)
    )


def active_lab_orders():
    return (
        select(LabOrder)
        .join(
            Visit,
            and_(
                Visit.id == LabOrder.visit_id, Visit.patient_id == LabOrder.patient_id
            ),
        )
        .where(LabOrder.status.in_(("ordered", "in_progress")))
    )


def specimen_visit_service_orders():
    """Explicit specimen custody links within the same order/visit/patient."""
    return (
        select(LabSpecimenAssignment.visit_service_id, LabSpecimen.order_id)
        .join(LabSpecimen, LabSpecimen.id == LabSpecimenAssignment.specimen_id)
        .join(LabOrder, LabOrder.id == LabSpecimen.order_id)
        .join(
            VisitService,
            and_(
                VisitService.id == LabSpecimenAssignment.visit_service_id,
                VisitService.visit_id == LabOrder.visit_id,
            ),
        )
        .join(
            Visit,
            and_(
                Visit.id == LabOrder.visit_id, Visit.patient_id == LabOrder.patient_id
            ),
        )
        .where(~func.lower(LabOrder.status).in_(INACTIVE_LAB_VISIT_STATUSES))
        .distinct()
    )


def lab_visit_services(
    *, include_previously_allocated: bool = False, specimen_orders=None
):
    """SQL projection of laboratory VisitService rows, independent of payment.

    Match configured routing before falling back to the lab catalog code
    group. Visit labels and patient names never determine ownership.
    """
    route_group = func.coalesce(
        case(_ROUTING_HINTS, value=func.lower(func.trim(Service.queue_tag))),
        case(_ROUTING_HINTS, value=func.lower(func.trim(Service.department_key))),
        case(_ROUTING_HINTS, value=func.lower(func.trim(Department.key))),
    )
    code = func.coalesce(
        func.nullif(func.trim(Service.service_code), ""),
        func.nullif(func.trim(VisitService.code), ""),
        func.nullif(func.trim(Service.code), ""),
    )
    upper_code = func.upper(code)
    lab_config = QUEUE_GROUPS[_LAB_GROUP]
    catalog_lab = or_(
        upper_code.in_(lab_config["service_codes"]),
        *(upper_code.startswith(prefix) for prefix in lab_config["service_prefixes"]),
        and_(code.is_(None), Service.category_code == "L"),
    )
    source = (
        select(
            VisitService.id.label("visit_service_id"),
            VisitService.visit_id,
            VisitService.service_id,
            code.label("code"),
            VisitService.name,
            VisitService.qty.label("quantity"),
            VisitService.created_at,
        )
        .select_from(VisitService)
        .outerjoin(Service, Service.id == VisitService.service_id)
        .outerjoin(Department, Department.id == Service.department_id)
    )
    if include_previously_allocated:
        prior_report_allocation = (
            select(LabOrderTest.id)
            .where(
                LabOrderTest.visit_service_id == VisitService.id,
            )
            .exists()
        )
        custody = (
            specimen_orders
            if specimen_orders is not None
            else specimen_visit_service_orders().subquery()
        )
        prior_specimen_allocation = (
            select(custody.c.visit_service_id)
            .where(
                custody.c.visit_service_id == VisitService.id,
            )
            .exists()
        )
        prior_allocation = or_(prior_report_allocation, prior_specimen_allocation)
    else:
        prior_allocation = False
    return source.where(
        or_(
            prior_allocation,
            route_group == _LAB_GROUP,
            and_(route_group.is_(None), catalog_lab),
        )
    )
