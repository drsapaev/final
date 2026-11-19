"""Authorize patient lab-result notifications from canonical DB associations."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.roles import is_doctor_role_spelling
from app.models.clinic import Doctor
from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabOrder,
    LabReportInstance,
    LabResult,
)
from app.models.user import User
from app.models.visit import Visit


def resolve_lab_notification(
    db: Session, *, lab_result_id: int, patient_id: int, current_user: User
) -> tuple[LabResult, LabOrder, Visit | None]:
    """Require consistent ownership, clinician assignment and finalized data.

    Finalized report projections may carry patient/visit where older order rows
    do not. Any conflicting populated association is denied. Legacy results
    without source provenance use the completed order as their readiness signal.
    """
    result = db.query(LabResult).filter(LabResult.id == lab_result_id).populate_existing().first()
    if not result:
        raise HTTPException(status_code=404, detail="Результат не найден")
    order = db.query(LabOrder).filter(LabOrder.id == result.order_id).populate_existing().first()
    if not order:
        raise HTTPException(status_code=403, detail="Access denied")
    if order.patient_id is not None and order.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    source = None
    if result.source_instance_id:
        source = (
            db.query(LabReportInstance)
            .filter(LabReportInstance.id == result.source_instance_id)
            .populate_existing()
            .first()
        )
        if not source or source.order_id != order.id or source.patient_id != patient_id:
            raise HTTPException(status_code=403, detail="Access denied")
        if order.visit_id and source.visit_id and order.visit_id != source.visit_id:
            raise HTTPException(status_code=403, detail="Access denied")
        ready = source.status in FINAL_INSTANCE_STATUSES
    else:
        if order.patient_id != patient_id:
            raise HTTPException(status_code=403, detail="Access denied")
        ready = (order.status or "").lower() in {"done", "completed"}

    visit_id = order.visit_id or (source.visit_id if source else None)
    visit = (
        db.query(Visit).filter(Visit.id == visit_id).populate_existing().first()
        if visit_id else None
    )
    if visit_id and (not visit or visit.patient_id != patient_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if is_doctor_role_spelling(current_user.role) and not getattr(current_user, "is_superuser", False):
        doctor = db.query(Doctor).filter(
            Doctor.user_id == current_user.id, Doctor.active.is_(True)
        ).populate_existing().first()
        if not doctor or not visit or visit.doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Access denied")
    if not ready:
        raise HTTPException(status_code=409, detail="Результат ещё не готов")
    return result, order, visit
