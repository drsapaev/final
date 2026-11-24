"""Project canonical laboratory states and keep physician review on the exact report."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabOrder,
    LabReportInstance,
    LabResultReview,
)
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service_execution import ServiceExecution
from app.models.visit import Visit, VisitService
from app.schemas.emr_workspace import (
    LabReviewOut,
    WorkspaceExecution,
    WorkspaceInvoiceStatus,
    WorkspaceLabOrder,
    WorkspaceLabReport,
    WorkspaceLabs,
)
from app.services.emr_workspace_service import WorkspaceError


def read_visit_labs(db: Session, visit: Visit) -> WorkspaceLabs:
    orders = (
        db.query(LabOrder)
        .filter_by(visit_id=visit.id, patient_id=visit.patient_id)
        .order_by(LabOrder.created_at.desc(), LabOrder.id.desc())
        .all()
    )
    instances = (
        db.query(LabReportInstance)
        .filter_by(visit_id=visit.id, patient_id=visit.patient_id)
        .options(selectinload(LabReportInstance.template))
        .order_by(LabReportInstance.id.desc())
        .all()
    )
    reviews = (
        db.query(LabResultReview)
        .join(LabReportInstance, LabResultReview.instance_id == LabReportInstance.id)
        .filter(
            LabReportInstance.visit_id == visit.id,
            LabReportInstance.patient_id == visit.patient_id,
        )
        .order_by(LabResultReview.reviewed_at.desc())
        .all()
    )
    reviews_by_instance: dict[int, list[LabReviewOut]] = {}
    for review in reviews:
        reviews_by_instance.setdefault(review.instance_id, []).append(
            LabReviewOut.model_validate(review)
        )
    superseded = {
        report.supersedes_instance_id
        for report in instances
        if report.status in FINAL_INSTANCE_STATUSES
        and report.supersedes_instance_id is not None
    }
    by_order: dict[int, list[WorkspaceLabReport]] = {order.id: [] for order in orders}
    unlinked: list[WorkspaceLabReport] = []
    for instance in instances:
        row = WorkspaceLabReport(
            id=instance.id,
            status=instance.status,
            template_name=instance.template.name or instance.template.code,
            supersedes_instance_id=instance.supersedes_instance_id,
            finalized_at=instance.finalized_at,
            is_current_final=instance.status in FINAL_INSTANCE_STATUSES
            and instance.id not in superseded,
            reviews=reviews_by_instance.get(instance.id, []),
        )
        by_order.get(instance.order_id, unlinked).append(row)

    execution_rows = (
        db.query(ServiceExecution, VisitService.name)
        .join(VisitService, VisitService.id == ServiceExecution.visit_service_id)
        .filter(VisitService.visit_id == visit.id)
        .order_by(ServiceExecution.started_at.desc())
        .all()
    )
    invoices = (
        db.query(PaymentInvoice.id, PaymentInvoice.status)
        .join(PaymentInvoiceVisit, PaymentInvoiceVisit.invoice_id == PaymentInvoice.id)
        .filter(PaymentInvoiceVisit.visit_id == visit.id)
        .order_by(PaymentInvoice.id.desc())
        .all()
    )
    return WorkspaceLabs(
        orders=[
            WorkspaceLabOrder(
                id=order.id,
                status=order.status,
                created_at=order.created_at,
                reports=by_order[order.id],
            )
            for order in orders
        ],
        unlinked_reports=unlinked,
        executions=[
            WorkspaceExecution(
                id=attempt.id,
                service_name=name,
                attempt=attempt.attempt_no,
                status=attempt.status,
            )
            for attempt, name in execution_rows
        ],
        invoices=[
            WorkspaceInvoiceStatus(id=invoice_id, status=status)
            for invoice_id, status in invoices
        ],
    )


def record_lab_review(
    db: Session,
    visit: Visit,
    instance_id: int,
    reviewer_id: int,
    next_action: str | None,
) -> LabReviewOut:
    instance = (
        db.query(LabReportInstance)
        .filter_by(id=instance_id, patient_id=visit.patient_id, visit_id=visit.id)
        .with_for_update()
        .one_or_none()
    )
    if instance is None:
        raise WorkspaceError(404, "LAB_VERSION_NOT_FOUND")
    if instance.status not in FINAL_INSTANCE_STATUSES:
        raise WorkspaceError(409, "LAB_VERSION_NOT_FINAL")
    existing = db.get(LabResultReview, (instance_id, reviewer_id))
    if existing is None:
        existing = LabResultReview(
            instance_id=instance_id,
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(UTC),
            next_action=(next_action or "").strip() or None,
        )
        db.add(existing)
        db.flush()
    return LabReviewOut.model_validate(existing)
