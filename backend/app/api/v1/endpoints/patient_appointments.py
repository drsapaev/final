# app/api/v1/endpoints/patient_appointments.py
"""
API endpoints для пациентов - управление своими записями.
Включает отмену и перенос записей с ограничением 24 часа.
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.models.appointment import Appointment
from app.models.user import User
from app.services.patient_appointments_api_service import PatientAppointmentsApiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patient", tags=["patient"])


# ============================================================================
# Schemas
# ============================================================================

class PatientAppointmentResponse(BaseModel):
    """Ответ с информацией о записи для пациента"""
    id: int
    appointment_date: str
    appointment_time: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_id: Optional[int] = None
    department: Optional[str] = None
    department_name: Optional[str] = None
    cabinet: Optional[str] = None
    status: str
    services: List[str] = []
    can_cancel: bool = False
    can_reschedule: bool = False
    hours_until_appointment: Optional[float] = None
    
    class Config:
        from_attributes = True


class PatientResultResponse(BaseModel):
    """Результаты анализов для пациента"""
    id: int
    title: str
    date: str
    status: str
    file_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class RescheduleRequest(BaseModel):
    """Запрос на перенос записи"""
    new_date: str = Field(..., description="Новая дата в формате YYYY-MM-DD")
    new_time: str = Field(..., description="Новое время в формате HH:MM")


class AvailableSlotResponse(BaseModel):
    """Доступный слот для записи"""
    date: str
    time: str
    doctor_id: int
    doctor_name: str


# ============================================================================
# Helper functions
# ============================================================================


def can_modify_appointment(appointment: Appointment, min_hours: int = 24) -> tuple[bool, float]:
    """
    Проверить, можно ли изменить запись.
    Возвращает (можно_ли, часов_до_записи)
    """
    if appointment.status in ['cancelled', 'completed']:
        return False, 0
    
    # Собираем datetime записи
    try:
        apt_date = appointment.appointment_date
        apt_time = appointment.appointment_time or "09:00"
        
        if isinstance(apt_date, str):
            apt_date = datetime.strptime(apt_date, "%Y-%m-%d").date()
        
        apt_datetime = datetime.combine(apt_date, datetime.strptime(apt_time, "%H:%M").time())
        
        now = datetime.now()
        hours_until = (apt_datetime - now).total_seconds() / 3600
        
        return hours_until >= min_hours, hours_until
    except Exception as e:
        logger.error(f"Error calculating appointment time: {e}")
        return False, 0


def get_department_display_name(department: Optional[str]) -> str:
    """Получить читаемое название отделения."""
    names = {
        'cardiology': 'Кардиология',
        'dermatology': 'Дерматология',
        'dentistry': 'Стоматология',
        'ent': 'ЛОР',
        'therapy': 'Терапия',
        'laboratory': 'Лаборатория',
    }
    return names.get(department.lower(), department) if department else 'Не указано'


def extract_department_value(appointment: Appointment) -> Optional[str]:
    """Достать строковое представление отделения из записи."""
    department = getattr(appointment, "department", None)
    if isinstance(department, str):
        return department
    if department is None:
        return None
    return getattr(department, "key", None) or getattr(department, "name_ru", None)


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/appointments", response_model=List[PatientAppointmentResponse])
async def get_my_appointments(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
    include_past: bool = Query(False, description="Включить прошедшие записи"),
):
    """
    Получить список записей текущего пациента.
    """
    service = PatientAppointmentsApiService(db)
    patient = service.get_patient_for_user(current_user)
    
    if not patient:
        # Если пациент не найден, вернём пустой список (не ошибку)
        logger.warning(f"No patient found for user {current_user.id}")
        return []
    
    appointments = service.list_appointments(
        patient_id=patient.id,
        status_filter=status_filter,
        include_past=include_past,
    )
    
    result = []
    for apt in appointments:
        can_mod, hours_until = can_modify_appointment(apt)
        
        # Получаем имя врача
        doctor_name = service.get_doctor_name(apt.doctor_id)
        department = extract_department_value(apt)
        
        result.append(PatientAppointmentResponse(
            id=apt.id,
            appointment_date=str(apt.appointment_date),
            appointment_time=apt.appointment_time,
            doctor_name=doctor_name,
            doctor_id=apt.doctor_id,
            department=department,
            department_name=get_department_display_name(department),
            cabinet=getattr(apt, 'cabinet', None),
            status=apt.status,
            services=apt.services or [],
            can_cancel=can_mod,
            can_reschedule=can_mod,
            hours_until_appointment=round(hours_until, 1) if hours_until > 0 else None,
        ))
    
    return result


@router.get("/appointments/{appointment_id}", response_model=PatientAppointmentResponse)
async def get_my_appointment(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить детали конкретной записи.
    """
    service = PatientAppointmentsApiService(db)
    patient = service.get_patient_for_user(current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = service.get_appointment_for_patient(
        appointment_id=appointment_id,
        patient_id=patient.id,
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    can_mod, hours_until = can_modify_appointment(appointment)
    
    # Получаем имя врача
    doctor_name = service.get_doctor_name(appointment.doctor_id)
    department = extract_department_value(appointment)
    
    return PatientAppointmentResponse(
        id=appointment.id,
        appointment_date=str(appointment.appointment_date),
        appointment_time=appointment.appointment_time,
        doctor_name=doctor_name,
        doctor_id=appointment.doctor_id,
        department=department,
        department_name=get_department_display_name(department),
        cabinet=getattr(appointment, 'cabinet', None),
        status=appointment.status,
        services=appointment.services or [],
        can_cancel=can_mod,
        can_reschedule=can_mod,
        hours_until_appointment=round(hours_until, 1) if hours_until > 0 else None,
    )


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_my_appointment(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Отменить запись на приём.
    Требуется минимум 24 часа до приёма.
    """
    service = PatientAppointmentsApiService(db)
    patient = service.get_patient_for_user(current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = service.get_appointment_for_patient(
        appointment_id=appointment_id,
        patient_id=patient.id,
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    if appointment.status == 'cancelled':
        raise HTTPException(status_code=400, detail="Запись уже отменена")
    
    if appointment.status == 'completed':
        raise HTTPException(status_code=400, detail="Нельзя отменить завершённую запись")
    
    can_cancel, hours_until = can_modify_appointment(appointment)
    
    if not can_cancel:
        raise HTTPException(
            status_code=400, 
            detail=f"Отмена возможна минимум за 24 часа до приёма. До записи осталось {round(hours_until, 1)} часов."
        )
    
    # Отменяем запись
    service.cancel_appointment(appointment)
    
    logger.info(f"Patient {patient.id} cancelled appointment {appointment_id}")
    
    # TODO: Отправить уведомление клинике
    
    return {
        "success": True,
        "message": "Запись успешно отменена",
        "appointment_id": appointment_id
    }


@router.post("/appointments/{appointment_id}/reschedule")
async def reschedule_my_appointment(
    appointment_id: int,
    request: RescheduleRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Перенести запись на другую дату/время.
    Требуется минимум 24 часа до текущей записи.
    """
    service = PatientAppointmentsApiService(db)
    patient = service.get_patient_for_user(current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = service.get_appointment_for_patient(
        appointment_id=appointment_id,
        patient_id=patient.id,
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    if appointment.status in ['cancelled', 'completed']:
        raise HTTPException(status_code=400, detail=f"Нельзя перенести запись со статусом '{appointment.status}'")
    
    can_reschedule, hours_until = can_modify_appointment(appointment)
    
    if not can_reschedule:
        raise HTTPException(
            status_code=400,
            detail=f"Перенос возможен минимум за 24 часа до приёма. До записи осталось {round(hours_until, 1)} часов."
        )
    
    # Валидация новой даты
    try:
        new_date = datetime.strptime(request.new_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    
    # Проверяем что новая дата в будущем
    if new_date < datetime.now().date():
        raise HTTPException(status_code=400, detail="Нельзя перенести на прошедшую дату")
    
    # Валидация времени
    try:
        datetime.strptime(request.new_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат времени. Используйте HH:MM")
    
    # TODO: Проверить доступность слота
    
    # Обновляем запись
    old_date = appointment.appointment_date
    old_time = appointment.appointment_time
    
    service.reschedule_appointment(
        appointment=appointment,
        new_date=new_date,
        new_time=request.new_time,
    )
    
    logger.info(
        f"Patient {patient.id} rescheduled appointment {appointment_id} "
        f"from {old_date} {old_time} to {new_date} {request.new_time}"
    )
    
    # TODO: Отправить уведомление клинике
    
    return {
        "success": True,
        "message": "Запись успешно перенесена",
        "appointment_id": appointment_id,
        "new_date": str(new_date),
        "new_time": request.new_time
    }


@router.get("/appointments/{appointment_id}/available-slots", response_model=List[AvailableSlotResponse])
async def get_available_slots(
    appointment_id: int,
    date_from: str = Query(..., description="Начальная дата YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Конечная дата YYYY-MM-DD"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить доступные слоты для переноса записи.
    """
    service = PatientAppointmentsApiService(db)
    patient = service.get_patient_for_user(current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = service.get_appointment_for_patient(
        appointment_id=appointment_id,
        patient_id=patient.id,
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    # Парсим даты
    try:
        start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты date_from")
    
    end_date = service.default_end_date(start_date=start_date)
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты date_to")

    slots = service.list_available_slots(
        appointment=appointment,
        start_date=start_date,
        end_date=end_date,
    )
    return [AvailableSlotResponse(**slot) for slot in slots[:20]]


@router.get("/results", response_model=List[PatientResultResponse])
async def get_my_results(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Получить результаты анализов пациента.
    """
    service = PatientAppointmentsApiService(db)
    patient = service.get_patient_for_user(current_user)
    
    if not patient:
        return []
    
    # Получаем лабораторные результаты
    lab_results = service.list_done_lab_results(
        patient_id=patient.id,
        limit=limit,
    )
    
    results = []
    for lab in lab_results:
        results.append(PatientResultResponse(
            id=lab.id,
            title=lab.notes or "Анализ",
            date=str(lab.created_at.date()) if lab.created_at else "",
            status=lab.status,
            file_url=None
        ))
    
    return results
