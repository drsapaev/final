# app/api/v1/endpoints/patient_appointments.py
"""
API endpoints для пациентов - управление своими записями.
Включает отмену и перенос записей с ограничением 24 часа.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.models.appointment import Appointment
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.lab import LabOrder
from app.models.clinic import Doctor, Schedule

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

def get_patient_for_user(db: Session, user: User) -> Optional[Patient]:
    """Получить пациента, связанного с пользователем"""
    # Пациент может быть связан по user_id или по телефону
    if hasattr(user, 'patient_id') and user.patient_id:
        return db.query(Patient).filter(Patient.id == user.patient_id).first()
    
    # Попробуем найти по телефону или email
    if user.phone:
        patient = db.query(Patient).filter(Patient.phone == user.phone).first()
        if patient:
            return patient
    
    if user.email:
        patient = db.query(Patient).filter(Patient.email == user.email).first()
        if patient:
            return patient
    
    return None


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
    """Получить читаемое название отделения"""
    names = {
        'cardiology': 'Кардиология',
        'dermatology': 'Дерматология',
        'dentistry': 'Стоматология',
        'ent': 'ЛОР',
        'therapy': 'Терапия',
        'laboratory': 'Лаборатория',
    }
    return names.get(department.lower(), department) if department else 'Не указано'


def get_doctor_name(db: Session, doctor_id: Optional[int]) -> Optional[str]:
    """Получить имя врача по doctor_id (ссылается на doctors.id, не users.id)"""
    if not doctor_id:
        return None
    
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        return None
    
    if doctor.user_id:
        user = db.query(User).filter(User.id == doctor.user_id).first()
        if user:
            return user.full_name or user.username
    
    return f"Врач #{doctor_id}"


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
    patient = get_patient_for_user(db, current_user)
    
    if not patient:
        # Если пациент не найден, вернём пустой список (не ошибку)
        logger.warning(f"No patient found for user {current_user.id}")
        return []
    
    # Базовый запрос
    query = db.query(Appointment).filter(Appointment.patient_id == patient.id)
    
    # Фильтр по статусу
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    
    # Фильтр прошедших записей
    if not include_past:
        today = datetime.now().date()
        query = query.filter(Appointment.appointment_date >= today)
    
    # Сортировка по дате
    query = query.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc())
    
    appointments = query.all()
    
    result = []
    for apt in appointments:
        can_mod, hours_until = can_modify_appointment(apt)
        
        # Получаем имя врача
        doctor_name = get_doctor_name(db, apt.doctor_id)
        
        result.append(PatientAppointmentResponse(
            id=apt.id,
            appointment_date=str(apt.appointment_date),
            appointment_time=apt.appointment_time,
            doctor_name=doctor_name,
            doctor_id=apt.doctor_id,
            department=apt.department,
            department_name=get_department_display_name(apt.department),
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
    patient = get_patient_for_user(db, current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == patient.id
    ).first()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    can_mod, hours_until = can_modify_appointment(appointment)
    
    # Получаем имя врача
    doctor_name = get_doctor_name(db, appointment.doctor_id)
    
    return PatientAppointmentResponse(
        id=appointment.id,
        appointment_date=str(appointment.appointment_date),
        appointment_time=appointment.appointment_time,
        doctor_name=doctor_name,
        doctor_id=appointment.doctor_id,
        department=appointment.department,
        department_name=get_department_display_name(appointment.department),
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
    patient = get_patient_for_user(db, current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == patient.id
    ).first()
    
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
    appointment.status = 'cancelled'
    appointment.updated_at = datetime.now()
    
    db.commit()
    
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
    patient = get_patient_for_user(db, current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == patient.id
    ).first()
    
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
    
    appointment.appointment_date = new_date
    appointment.appointment_time = request.new_time
    appointment.updated_at = datetime.now()
    
    db.commit()
    
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
    patient = get_patient_for_user(db, current_user)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == patient.id
    ).first()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    # Парсим даты
    try:
        start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты date_from")
    
    end_date = start_date + timedelta(days=7)  # По умолчанию неделя
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты date_to")
    
    # Получаем врача и его расписание
    doctor = None
    doctor_name = "Врач"
    schedules = []
    
    if appointment.doctor_id:
        doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
        if doctor:
            # Получаем имя через связанного пользователя
            if doctor.user_id:
                user = db.query(User).filter(User.id == doctor.user_id).first()
                if user:
                    doctor_name = f"{user.full_name or user.username}"
            
            # Получаем расписание врача
            schedules = db.query(Schedule).filter(
                Schedule.doctor_id == doctor.id,
                Schedule.active == True
            ).all()
    
    # Получаем все существующие записи врача в диапазоне дат
    existing_appointments = []
    if appointment.doctor_id:
        existing_appointments = db.query(Appointment).filter(
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.appointment_date >= start_date,
            Appointment.appointment_date <= end_date,
            Appointment.status.notin_(['cancelled'])
        ).all()
    
    # Создаём set занятых слотов
    booked_slots = set()
    for apt in existing_appointments:
        slot_key = f"{apt.appointment_date}_{apt.appointment_time}"
        booked_slots.add(slot_key)
    
    slots = []
    current_date = start_date
    
    while current_date <= end_date:
        weekday = current_date.weekday()  # 0=Monday
        
        # Ищем расписание на этот день недели
        day_schedule = None
        for sched in schedules:
            if sched.weekday == weekday and sched.active:
                day_schedule = sched
                break
        
        if day_schedule and day_schedule.start_time and day_schedule.end_time:
            # Генерируем слоты на основе реального расписания
            start_hour = day_schedule.start_time.hour if hasattr(day_schedule.start_time, 'hour') else 9
            end_hour = day_schedule.end_time.hour if hasattr(day_schedule.end_time, 'hour') else 18
            
            for hour in range(start_hour, end_hour):
                time_str = f"{hour:02d}:00"
                slot_key = f"{current_date}_{time_str}"
                
                # Пропускаем занятые слоты
                if slot_key in booked_slots:
                    continue
                
                slots.append(AvailableSlotResponse(
                    date=str(current_date),
                    time=time_str,
                    doctor_id=appointment.doctor_id or 0,
                    doctor_name=doctor_name
                ))
        elif not schedules:
            # Если расписания нет, используем дефолтные часы (Пн-Сб 9-17)
            if weekday < 6:
                for hour in [9, 10, 11, 14, 15, 16]:
                    time_str = f"{hour:02d}:00"
                    slot_key = f"{current_date}_{time_str}"
                    
                    if slot_key in booked_slots:
                        continue
                    
                    slots.append(AvailableSlotResponse(
                        date=str(current_date),
                        time=time_str,
                        doctor_id=appointment.doctor_id or 0,
                        doctor_name=doctor_name
                    ))
        
        current_date += timedelta(days=1)
    
    return slots[:20]  # Ограничиваем количество


@router.get("/results", response_model=List[PatientResultResponse])
async def get_my_results(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Получить результаты анализов пациента.
    """
    patient = get_patient_for_user(db, current_user)
    
    if not patient:
        return []
    
    # Получаем лабораторные результаты
    lab_results = db.query(LabOrder).filter(
        LabOrder.patient_id == patient.id,
        LabOrder.status == 'done'
    ).order_by(LabOrder.created_at.desc()).limit(limit).all()
    
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
