"""
API endpoints для жесткого потока: запись → платеж → прием → медкарта → рецепт
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.appointment import appointment as crud_appointment
from app.crud import emr as crud_emr
from app.models.enums import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import Appointment
from app.schemas.emr import (
    EMR,
    EMRCreate,
    EMRUpdate,
    Prescription,
    PrescriptionCreate,
    PrescriptionUpdate,
)

router = APIRouter()


@router.post("/{appointment_id}/start-visit", response_model=Appointment)
def start_visit(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Any:
    """
    Начать прием (переход paid -> in_visit)
    """
    appointment = crud_appointment.appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем, что запись оплачена
    if appointment.status != AppointmentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя начать прием. Текущий статус: {appointment.status}",
        )

    # Переводим в статус "на приеме"
    updated_appointment = crud_appointment.appointment.start_visit(
        db, appointment_id=appointment_id
    )
    return updated_appointment


@router.post("/{appointment_id}/emr", response_model=EMR)
def create_or_update_emr(
    appointment_id: int,
    emr_data: EMRCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Создать или обновить EMR
    """
    appointment = crud_appointment.appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем статус записи
    if appointment.status not in [
        AppointmentStatus.IN_VISIT,
        AppointmentStatus.COMPLETED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"EMR доступно только во время приема. Текущий статус: {appointment.status}",
        )

    # Проверяем, есть ли уже EMR для этой записи
    existing_emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)

    if existing_emr:
        # Создаем версию перед обновлением
        from app.crud.emr_template import emr_version
        emr_version.create_version(
            db,
            emr_id=existing_emr.id,
            version_data=existing_emr.__dict__,
            change_type="updated",
            change_description="Обновление EMR",
            changed_by=current_user.id
        )
        
        # Обновляем существующий EMR
        emr_update = EMRUpdate(**emr_data.dict(exclude={"appointment_id"}))
        updated_emr = crud_emr.emr.update(db, db_obj=existing_emr, obj_in=emr_update)
        return updated_emr
    else:
        # Создаем новый EMR
        emr_data.appointment_id = appointment_id
        new_emr = crud_emr.emr.create(db, obj_in=emr_data)
        
        # Создаем первую версию
        from app.crud.emr_template import emr_version
        emr_version.create_version(
            db,
            emr_id=new_emr.id,
            version_data=new_emr.__dict__,
            change_type="created",
            change_description="Создание EMR",
            changed_by=current_user.id
        )
        
        return new_emr


@router.post("/{appointment_id}/emr/save", response_model=EMR)
def save_emr(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Сохранить EMR (перевести из черновика)
    """
    emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)
    if not emr:
        raise HTTPException(status_code=404, detail="EMR не найдена")

    if not emr.is_draft:
        raise HTTPException(status_code=400, detail="EMR уже сохранена")

    saved_emr = crud_emr.emr.save_emr(db, emr_id=emr.id)
    return saved_emr


@router.get("/{appointment_id}/emr", response_model=Optional[EMR])
def get_emr(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Any:
    """
    Получить EMR по записи
    """
    emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)
    return emr


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
    appointment = crud_appointment.appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем, что есть сохраненная EMR
    emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)
    if not emr or emr.is_draft:
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
    existing_prescription = crud_emr.prescription.get_by_appointment(
        db, appointment_id=appointment_id
    )

    if existing_prescription:
        # Обновляем существующий рецепт
        prescription_update = PrescriptionUpdate(
            **prescription_data.dict(exclude={"appointment_id", "emr_id"})
        )
        updated_prescription = crud_emr.prescription.update(
            db, db_obj=existing_prescription, obj_in=prescription_update
        )
        return updated_prescription
    else:
        # Создаем новый рецепт
        prescription_data.appointment_id = appointment_id
        prescription_data.emr_id = emr.id
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
    prescription = crud_emr.prescription.get_by_appointment(
        db, appointment_id=appointment_id
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    if not prescription.is_draft:
        raise HTTPException(status_code=400, detail="Рецепт уже сохранен")

    saved_prescription = crud_emr.prescription.save_prescription(
        db, prescription_id=prescription.id
    )
    return saved_prescription


@router.get("/{appointment_id}/prescription", response_model=Optional[Prescription])
def get_prescription(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Any:
    """
    Получить рецепт по записи
    """
    prescription = crud_emr.prescription.get_by_appointment(
        db, appointment_id=appointment_id
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
    appointment = crud_appointment.appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем, что прием активен
    if appointment.status != AppointmentStatus.IN_VISIT:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя завершить прием. Текущий статус: {appointment.status}",
        )

    # Проверяем, что есть сохраненная EMR
    emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)
    if not emr or emr.is_draft:
        raise HTTPException(
            status_code=400, detail="Нельзя завершить прием без сохраненной EMR"
        )

    # Завершаем прием
    completed_appointment = crud_appointment.appointment.complete_visit(
        db, appointment_id=appointment_id
    )
    return completed_appointment


@router.post("/{appointment_id}/mark-paid", response_model=Appointment)
def mark_appointment_paid(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    # current_user: User = Depends(deps.require_roles("Admin", "Cashier", "Registrar")),
) -> Any:
    """
    Отметить запись как оплаченную (переход pending -> paid)
    """
    appointment = crud_appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Отмечаем как оплаченное
    paid_appointment = crud_appointment.mark_paid(
        db, appointment_id=appointment_id
    )
    return paid_appointment


@router.get("/{appointment_id}/status")
def get_appointment_status(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(
        deps.require_roles("Admin", "Doctor", "Registrar", "Cashier")
    ),
) -> Dict[str, Any]:
    """
    Получить полную информацию о статусе записи и связанных данных
    """
    appointment = crud_appointment.appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Получаем связанные данные
    emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)
    prescription = crud_emr.prescription.get_by_appointment(
        db, appointment_id=appointment_id
    )

    return {
        "appointment": appointment,
        "emr": emr,
        "prescription": prescription,
        "can_start_visit": appointment.status == AppointmentStatus.PAID,
        "can_create_emr": appointment.status
        in [AppointmentStatus.IN_VISIT, AppointmentStatus.COMPLETED],
        "can_create_prescription": emr and not emr.is_draft,
        "can_complete": appointment.status == AppointmentStatus.IN_VISIT
        and emr
        and not emr.is_draft,
    }
