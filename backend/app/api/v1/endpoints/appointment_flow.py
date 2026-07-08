"""
API endpoints для жесткого потока: запись → платеж → прием → медкарта → рецепт
"""

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.core.audit import extract_model_changes
from app.core.config import settings
from app.crud import emr as crud_emr
from app.crud.appointment import appointment as crud_appointment
from app.models.clinic import Doctor
from app.models.enums import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import Appointment
from app.schemas.emr import (
    EMR,
    EMRCreate,
    Prescription,
    PrescriptionCreate,
    PrescriptionUpdate,
)
from app.services.appointment_flow_api_service import (
    AppointmentFlowApiDomainError,
    AppointmentFlowApiService,
)
from app.services.canonical_visit_service import CanonicalVisitResolutionError
from app.services.emr_contract import (
    canonical_emr_to_legacy_payload,
    legacy_emr_to_v2_data,
)
from app.services.emr_v2_service import emr_v2_service

logger = logging.getLogger(__name__)


def convert_datetimes_to_iso(obj):
    """Рекурсивно преобразует все datetime объекты в ISO строки для JSON сериализации"""
    if isinstance(obj, dict):
        return {k: convert_datetimes_to_iso(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetimes_to_iso(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


router = APIRouter()

APPOINTMENT_FLOW_READ_ROLES = (
    "Admin",
    "Doctor",
    "Registrar",
    "Cashier",
    "cardio",
    "cardiology",
    "Cardiologist",
    "Cardio",
    "derma",
    "Dermatologist",
    "dentist",
    "Dentist",
    "Lab",
    "Laboratory",
)

APPOINTMENT_FLOW_DOCTOR_ROLES = {
    "Doctor",
    "cardio",
    "cardiology",
    "Cardiologist",
    "Cardio",
    "derma",
    "Dermatologist",
    "dentist",
    "Dentist",
}


class CanonicalVisitResponse(BaseModel):
    appointment_id: int
    visit_id: int


def _maybe_raise_legacy_write_freeze() -> None:
    if settings.EMR_LEGACY_WRITE_FREEZE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Legacy appointment-based EMR writes are temporarily frozen during "
                "EMR v2 hard cutover. Use canonical /api/v1/v2/emr endpoints."
            ),
        )


def _ensure_appointment_doctor_access(
    db: Session,
    appointment: Any,
    current_user: User,
) -> None:
    if current_user.role == "Admin" or current_user.is_superuser:
        return
    if current_user.role not in APPOINTMENT_FLOW_DOCTOR_ROLES:
        return

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")
    if appointment.doctor_id == doctor.id:
        return

    assigned_doctor = (
        db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    )
    # Legacy visit-derived appointments can carry User.id in doctor_id; allow it
    # only when it cannot resolve to another real Doctor row.
    if not assigned_doctor and appointment.doctor_id == current_user.id:
        return

    if assigned_doctor and assigned_doctor.user_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _resolve_appointment_and_visit(
    db: Session,
    appointment_id: int,
    *,
    allow_visit_fallback: bool = True,
    current_user: User | None = None,
) -> tuple[Any, int, AppointmentFlowApiService]:
    appointment_flow_api_service = AppointmentFlowApiService(db)
    appointment = crud_appointment.get(db, id=appointment_id)

    if not appointment and allow_visit_fallback:
        try:
            appointment, _visit = appointment_flow_api_service.resolve_appointment_from_visit(
                appointment_id=appointment_id,
                emr_data=SimpleNamespace(appointment_id=appointment_id),
            )
        except AppointmentFlowApiDomainError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    if current_user is not None:
        _ensure_appointment_doctor_access(db, appointment, current_user)

    try:
        visit_id = appointment_flow_api_service.resolve_canonical_visit(
            appointment_id=appointment.id
        )
    except CanonicalVisitResolutionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return appointment, visit_id, appointment_flow_api_service


def _legacy_emr_response(canonical_emr: Any, *, appointment_id: int) -> EMR:
    return EMR.model_validate(
        canonical_emr_to_legacy_payload(canonical_emr, appointment_id=appointment_id)
    )


def _canonical_emr_ready(canonical_emr: Any | None) -> bool:
    return bool(canonical_emr and getattr(canonical_emr, "status", "draft") != "draft")


@router.post("/{appointment_id}/start-visit", response_model=Appointment)
def start_visit(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Any:
    """
    Начать прием (переход paid -> in_visit)
    """
    appointment = crud_appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем, что запись оплачена или вызвана (called/calling)
    # Разрешаем начать прием если статус: paid, called, calling, waiting, queued
    _ensure_appointment_doctor_access(db, appointment, current_user)

    status_str = str(appointment.status).lower()
    allowed_start_statuses = [
        AppointmentStatus.PAID,
    ]
    if appointment.status not in allowed_start_statuses and status_str not in [
        'paid',
        'called',
        'calling',
        'waiting',
        'queued',
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя начать прием. Текущий статус: {appointment.status}",
        )

    # Переводим в статус "на приеме"
    updated_appointment = crud_appointment.start_visit(
        db, appointment_id=appointment_id
    )
    return updated_appointment


@router.post("/{appointment_id}/emr", response_model=EMR)
def create_or_update_emr(
    request: Request,
    appointment_id: int,
    emr_data: EMRCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(
        deps.require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "cardio",
            "cardiology",
            "Cardiologist",
            "Cardio",
            "derma",
            "Dermatologist",
            "dentist",
            "Dentist",
            "Lab",
            "Laboratory",
        )
    ),
) -> Any:
    """
    Создать или обновить EMR
    Может работать как с Appointment ID, так и с Visit ID (создает Appointment из Visit если нужно)

    ✅ SECURITY: Validates medical data including ICD-10 codes, date ranges, and medical values
    """
    _maybe_raise_legacy_write_freeze()

    logger.info(
        "[appointment-flow shim] create_or_update_emr appointment_id=%d user=%s role=%s",
        appointment_id,
        current_user.username,
        getattr(current_user, "role", "N/A"),
    )

    # ✅ SECURITY: Validate medical record data
    from fastapi import HTTPException, status

    from app.services.medical_validation import MedicalValidationService

    validation_service = MedicalValidationService()

    # Get patient birth date for date validation
    appointment = crud_appointment.get(db, id=appointment_id)
    if appointment:
        _ensure_appointment_doctor_access(db, appointment, current_user)
    patient_birth_date = None
    if appointment and appointment.patient_id:
        from app.crud import patient as crud_patient
        patient = crud_patient.get(db, id=appointment.patient_id)
        if patient:
            patient_birth_date = patient.birth_date

    # Convert Pydantic model to dict for validation
    emr_dict = emr_data.model_dump(exclude_unset=True)

    # Validate medical record
    is_valid, errors = validation_service.validate_medical_record(emr_dict, patient_birth_date)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Medical record validation errors: {'; '.join(errors)}",
        )

    appointment, visit_id, appointment_flow_api_service = _resolve_appointment_and_visit(
        db,
        appointment_id,
        allow_visit_fallback=False,
        current_user=current_user,
    )

    # Проверяем статус записи
    # Разрешаем сохранение EMR если статус: in_visit, in_progress, completed, или called (вызван врачом)
    allowed_statuses = [
        AppointmentStatus.IN_VISIT,
        AppointmentStatus.COMPLETED,
    ]
    # Также проверяем строковые значения для совместимости
    status_str = str(appointment.status).lower()

    if appointment.status not in allowed_statuses and status_str not in [
        'in_visit',
        'in_progress',
        'completed',
        'called',
        'calling',
        'paid',
        'waiting',
        'queued',
    ]:
        # Если статус не подходит, но это called/calling/paid/waiting/queued, обновляем статус на in_visit
        # Это позволяет начать сохранение EMR для вызванных или оплаченных пациентов
        if status_str in ['called', 'calling', 'paid', 'waiting', 'queued']:
            appointment_flow_api_service.promote_appointment_to_in_visit(
                appointment=appointment
            )
            logger.info(
                "[create_or_update_emr] Статус appointment %d обновлен с '%s' на 'in_visit'",
                appointment_id,
                status_str,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"EMR доступно только во время приема. Текущий статус: {appointment.status}",
            )

    try:
        canonical_emr = emr_v2_service.get_by_visit(db, visit_id)
        old_data = None
        if canonical_emr is not None:
            old_data, _ = extract_model_changes(canonical_emr, None)
        canonical_payload = legacy_emr_to_v2_data(
            emr_dict,
            fallback_specialty=getattr(current_user, "specialty", None)
            or getattr(current_user, "role", None),
        )
        row_version = canonical_emr.row_version if canonical_emr else 0
        saved_emr = emr_v2_service.save(
            db,
            visit_id=visit_id,
            data=canonical_payload,
            user_id=current_user.id,
            row_version=row_version,
            client_session_id=f"legacy-appointment-flow:{current_user.id}",
            is_draft=emr_data.is_draft,
        )
        if canonical_emr is None:
            logger.info(
                "[FIX:EMR_AUDIT] Logging CREATE user audit for EMR %d on appointment %d",
                saved_emr.id,
                appointment.id,
            )
            appointment_flow_api_service.finalize_emr_create_audit(
                request=request,
                user_id=current_user.id,
                appointment_id=appointment.id,
                new_emr=saved_emr,
            )
        else:
            logger.info(
                "[FIX:EMR_AUDIT] Logging UPDATE user audit for EMR %d on appointment %d",
                saved_emr.id,
                appointment.id,
            )
            appointment_flow_api_service.finalize_emr_update_audit(
                request=request,
                user_id=current_user.id,
                appointment_id=appointment.id,
                updated_emr=saved_emr,
                old_data=old_data,
            )
        return _legacy_emr_response(saved_emr, appointment_id=appointment.id)
    except HTTPException:
        raise
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.post("/{appointment_id}/emr/save", response_model=EMR)
def save_emr(
    appointment_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Сохранить EMR (перевести из черновика)

    Также индексирует фразы для Doctor History Autocomplete.
    """
    _maybe_raise_legacy_write_freeze()
    appointment, visit_id, appointment_flow_api_service = _resolve_appointment_and_visit(
        db,
        appointment_id,
        allow_visit_fallback=False,
        current_user=current_user,
    )
    canonical_emr = emr_v2_service.get_by_visit(db, visit_id)
    if not canonical_emr:
        raise HTTPException(status_code=404, detail="EMR не найдена")

    old_data, _ = extract_model_changes(canonical_emr, None)

    if canonical_emr.status != "draft":
        return _legacy_emr_response(canonical_emr, appointment_id=appointment.id)

    saved_emr = emr_v2_service.save(
        db,
        visit_id=visit_id,
        data=canonical_emr.data,
        user_id=current_user.id,
        row_version=canonical_emr.row_version,
        client_session_id=f"legacy-appointment-flow:{current_user.id}",
        is_draft=False,
    )
    logger.info(
        "[FIX:EMR_AUDIT] Logging UPDATE user audit for saved EMR %d on appointment %d",
        saved_emr.id,
        appointment.id,
    )
    appointment_flow_api_service.finalize_emr_update_audit(
        request=request,
        user_id=current_user.id,
        appointment_id=appointment.id,
        updated_emr=saved_emr,
        old_data=old_data,
    )
    return _legacy_emr_response(saved_emr, appointment_id=appointment.id)


@router.get("/{appointment_id}/emr", response_model=Optional[EMR])  # noqa: UP045  # manual-review: complex type expression — manual conversion needed
def get_emr(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Any:
    """
    Получить EMR по записи
    """
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        current_user=current_user,
    )
    canonical_emr = emr_v2_service.get_by_visit(db, visit_id)
    if not canonical_emr:
        return None
    return _legacy_emr_response(canonical_emr, appointment_id=appointment.id)


@router.post("/{appointment_id}/prescription", response_model=Prescription)
def create_or_update_prescription(
    appointment_id: int,
    prescription_data: PrescriptionCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Создать или обновить рецепт
    """
    _maybe_raise_legacy_write_freeze()
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        allow_visit_fallback=False,
        current_user=current_user,
    )

    # Проверяем, что есть сохраненная EMR
    canonical_emr = emr_v2_service.get_by_visit(db, visit_id)
    if not _canonical_emr_ready(canonical_emr):
        raise HTTPException(
            status_code=400, detail="Рецепт можно создать только после сохранения EMR"
        )

    # Проверяем статус записи
    if appointment.status not in [
        AppointmentStatus.IN_VISIT,
        AppointmentStatus.COMPLETED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Рецепт доступен только во время приема. Текущий статус: {appointment.status}",
        )

    # Проверяем, есть ли уже рецепт
    existing_prescription = crud_emr.prescription.get_by_visit(
        db, visit_id=visit_id
    )
    if not existing_prescription:
        existing_prescription = crud_emr.prescription.get_by_appointment(
            db, appointment_id=appointment.id
        )

    if existing_prescription:
        # Обновляем существующий рецепт
        prescription_update = PrescriptionUpdate(
            **prescription_data.dict(
                exclude={"appointment_id", "visit_id", "emr_id", "emr_record_id"}
            )
        )
        updated_prescription = crud_emr.prescription.update(
            db, db_obj=existing_prescription, obj_in=prescription_update
        )
        updated_prescription.appointment_id = appointment.id
        updated_prescription.visit_id = visit_id
        updated_prescription.emr_record_id = canonical_emr.id
        db.add(updated_prescription)
        db.commit()
        db.refresh(updated_prescription)
        return updated_prescription
    else:
        # Создаем новый рецепт
        prescription_data.appointment_id = appointment.id
        prescription_data.visit_id = visit_id
        prescription_data.emr_id = None
        prescription_data.emr_record_id = canonical_emr.id
        new_prescription = crud_emr.prescription.create(db, obj_in=prescription_data)
        return new_prescription


@router.post("/{appointment_id}/prescription/save", response_model=Prescription)
def save_prescription(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Сохранить рецепт (перевести из черновика)
    """
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        allow_visit_fallback=False,
        current_user=current_user,
    )
    prescription = crud_emr.prescription.get_by_visit(db, visit_id=visit_id)
    if not prescription:
        prescription = crud_emr.prescription.get_by_appointment(
            db, appointment_id=appointment.id
        )
    if not prescription:
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    if not prescription.is_draft:
        raise HTTPException(status_code=400, detail="Рецепт уже сохранен")

    saved_prescription = crud_emr.prescription.save_prescription(
        db, prescription_id=prescription.id
    )
    return saved_prescription


@router.get("/{appointment_id}/prescription", response_model=Optional[Prescription])  # noqa: UP045  # manual-review: complex type expression — manual conversion needed
def get_prescription(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Any:
    """
    Получить рецепт по записи
    """
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        current_user=current_user,
    )
    prescription = crud_emr.prescription.get_by_visit(db, visit_id=visit_id)
    if not prescription:
        prescription = crud_emr.prescription.get_by_appointment(
            db, appointment_id=appointment.id
        )
    return prescription


@router.post("/{appointment_id}/complete", response_model=Appointment)
def complete_visit(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Завершить прием (переход in_visit -> completed)
    """
    _maybe_raise_legacy_write_freeze()
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        allow_visit_fallback=False,
        current_user=current_user,
    )

    # Проверяем, что прием активен
    if appointment.status != AppointmentStatus.IN_VISIT:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя завершить прием. Текущий статус: {appointment.status}",
        )

    # Проверяем, что есть сохраненная EMR
    canonical_emr = emr_v2_service.get_by_visit(db, visit_id)
    if not _canonical_emr_ready(canonical_emr):
        raise HTTPException(
            status_code=400, detail="Нельзя завершить прием без сохраненной EMR"
        )

    # Завершаем прием
    completed_appointment = crud_appointment.complete_visit(
        db, appointment_id=appointment.id
    )
    return completed_appointment


@router.post("/{appointment_id}/mark-paid", response_model=Appointment)
def mark_appointment_paid(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Cashier", "Registrar")),
) -> Any:
    """
    Отметить запись как оплаченную (переход pending -> paid)
    """
    appointment = crud_appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Отмечаем как оплаченное
    paid_appointment = crud_appointment.mark_paid(db, appointment_id=appointment_id)
    return paid_appointment


@router.get("/{appointment_id}/status", response_model=dict[str, Any])
def get_appointment_status(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*APPOINTMENT_FLOW_READ_ROLES)),
) -> dict[str, Any]:
    """
    Получить полную информацию о статусе записи и связанных данных
    """
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        current_user=current_user,
    )

    # Получаем связанные данные
    canonical_emr = emr_v2_service.get_by_visit(db, visit_id)
    emr = (
        _legacy_emr_response(canonical_emr, appointment_id=appointment.id)
        if canonical_emr
        else None
    )
    prescription = crud_emr.prescription.get_by_visit(db, visit_id=visit_id)
    if not prescription:
        prescription = crud_emr.prescription.get_by_appointment(
            db, appointment_id=appointment.id
        )
    emr_ready = _canonical_emr_ready(canonical_emr)

    return {
        "appointment": appointment,
        "visit_id": visit_id,
        "emr": emr,
        "prescription": prescription,
        "can_start_visit": appointment.status == AppointmentStatus.PAID,
        "can_create_emr": appointment.status
        in [AppointmentStatus.IN_VISIT, AppointmentStatus.COMPLETED],
        "can_create_prescription": emr_ready,
        "can_complete": appointment.status == AppointmentStatus.IN_VISIT
        and emr_ready,
    }


@router.get(
    "/{appointment_id}/canonical-visit",
    response_model=CanonicalVisitResponse,
)
def resolve_canonical_visit(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*APPOINTMENT_FLOW_READ_ROLES)),
) -> CanonicalVisitResponse:
    """Resolve appointment-based flows to the single canonical visit identifier."""
    appointment, visit_id, _ = _resolve_appointment_and_visit(
        db,
        appointment_id,
        current_user=current_user,
    )
    return CanonicalVisitResponse(appointment_id=appointment.id, visit_id=visit_id)
