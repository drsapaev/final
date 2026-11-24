"""Cancellation of explicit laboratory requisition lines before reporting."""

from datetime import UTC, datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models.lab import LabOrder, LabOrderTest
from app.models.patient import Patient
from app.models.visit import Visit, VisitService
from app.repositories.lab_ordered_test_repository import (
    INACTIVE_LAB_VISIT_STATUSES,
    active_lab_orders,
    lab_visit_services,
    unallocated_lab_report_visits,
)
from app.schemas.lab_worklist import LabCanceledOrderedTest
from app.services.lab_reporting_service import LabReportingDomainError


def cancel_unreported_lab_test(
    db: Session,
    *,
    visit_id: int,
    visit_service_id: int,
    order_id: int | None,
    actor_id: int,
    reason: str,
) -> LabCanceledOrderedTest:
    # Match report/specimen provisioning's visit-first lock order, then
    # serialize allocation and cancellation using the exact visit service.
    visit = db.execute(
        select(Visit)
        .join(Patient)
        .where(
            Visit.id == visit_id,
            ~Patient.is_deleted,
            ~func.lower(Visit.status).in_(INACTIVE_LAB_VISIT_STATUSES),
        )
        .with_for_update(of=Visit, key_share=True)
    ).scalar_one_or_none()
    if visit is None:
        raise LabReportingDomainError(404, "Lab visit not found")
    line = db.execute(
        select(VisitService)
        .where(
            VisitService.id == visit_service_id,
            VisitService.visit_id == visit.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if line is None:
        raise LabReportingDomainError(404, "Ordered laboratory test not found")
    if not db.execute(
        select(exists(lab_visit_services().where(VisitService.id == line.id)))
    ).scalar_one():
        raise LabReportingDomainError(404, "Ordered laboratory test not found")

    test = db.execute(
        select(LabOrderTest).where(
            LabOrderTest.visit_service_id == line.id,
        )
    ).scalar_one_or_none()
    if test is not None:
        if order_id is not None and test.order_id != order_id:
            raise LabReportingDomainError(
                409, "Ordered test belongs to a different order"
            )
        if test.canceled_at is not None:
            if test.cancel_reason != reason:
                raise LabReportingDomainError(
                    409, "Ordered test has already been canceled"
                )
            return _canceled_test(test)
        if test.report_instance_id is not None:
            raise LabReportingDomainError(
                409, "Reported tests must be reviewed within their report history"
            )

    # Older reports do not prove which exact visit-service IDs they cover.
    # Leave those lines available for manual reconciliation before canceling.
    unknown_report = (
        unallocated_lab_report_visits().where(Visit.id == visit.id).exists()
    )
    if db.execute(select(unknown_report)).scalar_one():
        raise LabReportingDomainError(
            409, "An existing report has no verified ordered-test allocation"
        )

    if test is None:
        orders = active_lab_orders().where(Visit.id == visit.id)
        if order_id is not None:
            order = db.execute(
                orders.where(LabOrder.id == order_id)
            ).scalar_one_or_none()
            if order is None:
                raise LabReportingDomainError(
                    404, "Lab order not found in the selected visit"
                )
        else:
            candidates = db.execute(orders.limit(2)).scalars().all()
            if len(candidates) > 1:
                raise LabReportingDomainError(
                    409, "Select the exact lab order before canceling its test"
                )
            order = (
                candidates[0]
                if candidates
                else LabOrder(patient_id=visit.patient_id, visit_id=visit.id)
            )
            if not candidates:
                db.add(order)
                db.flush()
        test = LabOrderTest(order_id=order.id, visit_service_id=line.id)
        db.add(test)
    test.canceled_at = datetime.now(UTC)
    test.canceled_by_user_id = actor_id
    test.cancel_reason = reason
    response = _canceled_test(test)
    db.commit()
    return response


def _canceled_test(test: LabOrderTest) -> LabCanceledOrderedTest:
    canceled_at = test.canceled_at
    if canceled_at.tzinfo is None:
        canceled_at = canceled_at.replace(tzinfo=UTC)
    return LabCanceledOrderedTest(
        order_id=test.order_id,
        visit_service_id=test.visit_service_id,
        canceled_at=canceled_at,
        canceled_by_user_id=test.canceled_by_user_id,
    )
