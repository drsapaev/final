"""
API endpoints для жесткого потока: запись → платеж → прием → медкарта → рецепт
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import emr as crud_emr
from app.crud.appointment import appointment as crud_appointment
from app.models.appointment import Appointment as AppointmentModel
from app.models.enums import AppointmentStatus
from app.models.user import User
from app.core.audit import log_critical_change, extract_model_changes
from app.schemas.appointment import Appointment
from app.schemas.emr import (
    EMR,
    EMRCreate,
    EMRUpdate,
    Prescription,
    PrescriptionCreate,
    PrescriptionUpdate,
)

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
    logger.info(
        "[create_or_update_emr] Начало обработки appointment_id=%d, user=%s, role=%s",
        appointment_id,
        current_user.username,
        getattr(current_user, 'role', 'N/A'),
    )
    
    # ✅ SECURITY: Validate medical record data
    from app.services.medical_validation import MedicalValidationService
    from fastapi import HTTPException, status
    
    validation_service = MedicalValidationService()
    
    # Get patient birth date for date validation
    appointment = crud_appointment.get(db, id=appointment_id)
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
    
    appointment = crud_appointment.get(db, id=appointment_id)

    # Если Appointment не найден, проверяем, может это Visit ID
    if not appointment:
        logger.info(
            "[create_or_update_emr] Appointment %d не найден, проверяем Visit...",
            appointment_id,
        )
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == appointment_id).first()
        if visit:
            logger.info(
                "[create_or_update_emr] Найден Visit %d, проверяем существующий Appointment...",
                appointment_id,
            )
            # Проверяем, нет ли уже Appointment для этого Visit (по patient_id, дате, doctor_id)
            existing_appointment = (
                db.query(AppointmentModel)
                .filter(
                    and_(
                        AppointmentModel.patient_id == visit.patient_id,
                        AppointmentModel.appointment_date
                        == (visit.visit_date or date.today()),
                        AppointmentModel.doctor_id == visit.doctor_id,
                    )
                )
                .first()
            )

            if existing_appointment:
                logger.info(
                    "[create_or_update_emr] Найден существующий Appointment %d для Visit %d, используем его",
                    existing_appointment.id,
                    visit.id,
                )
                appointment = existing_appointment
                # Обновляем appointment_id в emr_data для корректной привязки
                emr_data.appointment_id = existing_appointment.id
            else:
                logger.info(
                    "[create_or_update_emr] Создаем новый Appointment из Visit %d...",
                    visit.id,
                )
                # Создаем Appointment из Visit для работы с EMR
                appointment = AppointmentModel(
                    patient_id=visit.patient_id,
                    appointment_date=visit.visit_date or date.today(),
                    appointment_time=visit.visit_time or "09:00",
                    status=(
                        AppointmentStatus.IN_VISIT
                        if visit.status in ["in_progress", "confirmed"]
                        else AppointmentStatus.PAID
                    ),
                    doctor_id=visit.doctor_id,
                    department=visit.department,
                    notes=visit.notes,
                    created_at=visit.created_at,
                )
                db.add(appointment)
                db.commit()
                db.refresh(appointment)
            logger.info(
                "[create_or_update_emr] Создан Appointment %d из Visit %d",
                appointment.id,
                visit.id,
            )
        else:
            logger.warning(
                "[create_or_update_emr] Запись %d не найдена ни в Appointment, ни в Visit",
                appointment_id,
            )
            raise HTTPException(status_code=404, detail="Запись не найдена")
    else:
        logger.info(
            "[create_or_update_emr] Appointment найден: status=%s",
            appointment.status,
        )
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)

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
            appointment.status = AppointmentStatus.IN_VISIT
            db.commit()
            db.refresh(appointment)
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
        # Проверяем, есть ли уже EMR для этой записи
        logger.info(
            "[create_or_update_emr] Проверка существующего EMR для appointment_id=%d",
            appointment_id,
        )
        existing_emr = crud_emr.emr.get_by_appointment(
            db, appointment_id=appointment_id
        )

        if existing_emr:
            logger.info("[create_or_update_emr] EMR найден, обновление...")
            # Создаем версию перед обновлением
            try:
                from app.crud.emr_template import emr_version

                # Очищаем объект от SQLAlchemy внутренних полей перед сериализацией
                # Используем Pydantic схему для безопасной сериализации
                from app.schemas.emr import EMR as EMRSchema

                emr_dict = EMRSchema.from_orm(existing_emr).dict()

                # Преобразуем все datetime объекты в ISO строки для JSON сериализации
                emr_dict_clean = convert_datetimes_to_iso(emr_dict)

                emr_version.create_version(
                    db,
                    emr_id=existing_emr.id,
                    version_data=emr_dict_clean,
                    change_type="updated",
                    change_description="Обновление EMR",
                    changed_by=current_user.id,
                )
            except Exception as version_error:
                logger.warning(
                    "[create_or_update_emr] Предупреждение: не удалось создать версию: %s",
                    version_error,
                    exc_info=True,
                )

            # Обновляем существующий EMR
            # ✅ AUDIT LOG: Сохраняем старые данные перед обновлением
            old_data, _ = extract_model_changes(existing_emr, None)
            
            emr_update_dict = emr_data.dict(exclude={"appointment_id"})
            logger.info(
                "[create_or_update_emr] Данные для обновления: %s",
                list(emr_update_dict.keys()),
            )
            emr_update = EMRUpdate(**emr_update_dict)
            updated_emr = crud_emr.emr.update(
                db, db_obj=existing_emr, obj_in=emr_update
            )
            
            # ✅ AUDIT LOG: Логируем обновление EMR
            db.refresh(updated_emr)
            _, new_data = extract_model_changes(None, updated_emr)
            log_critical_change(
                db=db,
                user_id=current_user.id,
                action="UPDATE",
                table_name="emr",
                row_id=updated_emr.id,
                old_data=old_data,
                new_data=new_data,
                request=request,
                description=f"Обновлен EMR ID={updated_emr.id} для записи {appointment_id}",
            )
            db.commit()
            
            logger.info("[create_or_update_emr] EMR обновлен успешно")
            return updated_emr
        else:
            logger.info("[create_or_update_emr] EMR не найден, создание нового...")
            # Создаем новый EMR
            # Убеждаемся, что appointment_id установлен из URL параметра
            if emr_data.appointment_id != appointment_id:
                logger.warning(
                    "[create_or_update_emr] Предупреждение: appointment_id в данных (%d) != URL (%d), используем URL",
                    emr_data.appointment_id,
                    appointment_id,
                )
            emr_data.appointment_id = appointment_id
            logger.info(
                "[create_or_update_emr] Создание EMR с appointment_id=%d, is_draft=%s",
                appointment_id,
                emr_data.is_draft,
            )
            try:
                new_emr = crud_emr.emr.create(db, obj_in=emr_data)
                logger.info("[create_or_update_emr] EMR создан, id=%d", new_emr.id)
                
                # ✅ AUDIT LOG: Логируем создание EMR
                db.refresh(new_emr)
                _, new_data = extract_model_changes(None, new_emr)
                log_critical_change(
                    db=db,
                    user_id=current_user.id,
                    action="CREATE",
                    table_name="emr",
                    row_id=new_emr.id,
                    old_data=None,
                    new_data=new_data,
                    request=request,
                    description=f"Создан EMR ID={new_emr.id} для записи {appointment_id}",
                )
                db.commit()
            except Exception as create_error:
                logger.error(
                    "[create_or_update_emr] Ошибка при создании EMR: %s: %s",
                    type(create_error).__name__,
                    create_error,
                    exc_info=True,
                )
                raise

            # Создаем первую версию
            try:
                from app.crud.emr_template import emr_version

                # Очищаем объект от SQLAlchemy внутренних полей перед сериализацией
                # Используем Pydantic схему для безопасной сериализации
                from app.schemas.emr import EMR as EMRSchema

                emr_dict = EMRSchema.from_orm(new_emr).dict()

                # Преобразуем все datetime объекты в ISO строки для JSON сериализации
                emr_dict_clean = convert_datetimes_to_iso(emr_dict)

                emr_version.create_version(
                    db,
                    emr_id=new_emr.id,
                    version_data=emr_dict_clean,
                    change_type="created",
                    change_description="Создание EMR",
                    changed_by=current_user.id,
                )
            except Exception as version_error:
                logger.warning(
                    "[create_or_update_emr] Предупреждение: не удалось создать версию: %s",
                    version_error,
                    exc_info=True,
                )

            logger.info(
                "[create_or_update_emr] EMR создан успешно, id=%d",
                new_emr.id,
            )
            return new_emr
    except HTTPException:
        raise
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.post("/{appointment_id}/emr/save", response_model=EMR)
def save_emr(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Сохранить EMR (перевести из черновика)
    
    Также индексирует фразы для Doctor History Autocomplete.
    """
    emr = crud_emr.emr.get_by_appointment(db, appointment_id=appointment_id)
    if not emr:
        raise HTTPException(status_code=404, detail="EMR не найдена")

    if not emr.is_draft:
        raise HTTPException(status_code=400, detail="EMR уже сохранена")

    saved_emr = crud_emr.emr.save_emr(db, emr_id=emr.id)
    
    # 🔥 INDEX PHRASES for Doctor History Autocomplete
    # Это НЕ генерация - это извлечение фраз для будущих подсказок
    try:
        from app.services.emr_phrase_indexer import get_emr_phrase_indexer
        
        indexer = get_emr_phrase_indexer(db)
        specialty = getattr(current_user, 'specialty', None)
        
        indexed_count = indexer.index_single_emr(
            emr_id=saved_emr.id,
            doctor_id=current_user.id,
            specialty=specialty
        )
        
        logger.info(
            "[save_emr] Indexed %d phrases for doctor %d from EMR %d",
            indexed_count, current_user.id, saved_emr.id
        )
    except Exception as index_error:
        # Не блокируем сохранение если индексация не удалась
        logger.warning(
            "[save_emr] Failed to index phrases: %s",
            index_error
        )
    
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
    appointment = crud_appointment.get(db, id=appointment_id)
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
    appointment = crud_appointment.get(db, id=appointment_id)
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
    completed_appointment = crud_appointment.complete_visit(
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
    paid_appointment = crud_appointment.mark_paid(db, appointment_id=appointment_id)
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
    appointment = crud_appointment.get(db, id=appointment_id)
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
