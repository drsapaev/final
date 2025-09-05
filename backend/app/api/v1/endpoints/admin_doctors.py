"""
API endpoints для управления врачами в админ панели
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.crud import clinic as crud_clinic
from app.schemas.clinic import (
    DoctorOut, DoctorCreate, DoctorUpdate,
    ScheduleOut, ScheduleCreate, ScheduleUpdate, WeeklyScheduleUpdate
)

router = APIRouter()

# ===================== УПРАВЛЕНИЕ ВРАЧАМИ =====================

@router.get("/doctors", response_model=List[DoctorOut])
def get_doctors(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    specialty: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить список врачей"""
    try:
        doctors = crud_clinic.get_doctors(db, skip=skip, limit=limit, active_only=active_only)
        
        # Фильтрация по специальности
        if specialty:
            doctors = [d for d in doctors if d.specialty == specialty]
        
        # Добавляем связанные данные
        for doctor in doctors:
            # Загружаем пользователя
            if doctor.user_id:
                doctor.user = {
                    "id": doctor.user.id,
                    "username": doctor.user.username,
                    "full_name": doctor.user.full_name,
                    "email": doctor.user.email
                } if doctor.user else None
            
            # Загружаем расписания
            doctor.schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
        
        return doctors
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка врачей: {str(e)}"
        )


@router.get("/doctors/{doctor_id}", response_model=DoctorOut)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить врача по ID"""
    doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Врач с ID {doctor_id} не найден"
        )
    
    # Добавляем связанные данные
    if doctor.user_id:
        doctor.user = {
            "id": doctor.user.id,
            "username": doctor.user.username,
            "full_name": doctor.user.full_name,
            "email": doctor.user.email
        } if doctor.user else None
    
    doctor.schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
    
    return doctor


@router.post("/doctors", response_model=DoctorOut)
def create_doctor(
    doctor: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Создать врача"""
    try:
        # Проверяем, не привязан ли уже пользователь к другому врачу
        if doctor.user_id:
            existing_doctor = crud_clinic.get_doctor_by_user_id(db, doctor.user_id)
            if existing_doctor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь уже привязан к другому врачу"
                )
        
        new_doctor = crud_clinic.create_doctor(db, doctor)
        return new_doctor
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания врача: {str(e)}"
        )


@router.put("/doctors/{doctor_id}", response_model=DoctorOut)
def update_doctor(
    doctor_id: int,
    doctor: DoctorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить врача"""
    try:
        # Проверяем существование врача
        existing_doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        if not existing_doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден"
            )
        
        # Проверяем уникальность user_id если он изменяется
        if doctor.user_id and doctor.user_id != existing_doctor.user_id:
            other_doctor = crud_clinic.get_doctor_by_user_id(db, doctor.user_id)
            if other_doctor and other_doctor.id != doctor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь уже привязан к другому врачу"
                )
        
        updated_doctor = crud_clinic.update_doctor(db, doctor_id, doctor)
        return updated_doctor
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления врача: {str(e)}"
        )


@router.delete("/doctors/{doctor_id}")
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Удалить врача (мягкое удаление)"""
    try:
        success = crud_clinic.delete_doctor(db, doctor_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден"
            )
        
        return {"success": True, "message": "Врач успешно деактивирован"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления врача: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ РАСПИСАНИЯМИ =====================

@router.get("/doctors/{doctor_id}/schedule", response_model=List[ScheduleOut])
def get_doctor_schedule(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить расписание врача"""
    # Проверяем существование врача
    doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Врач с ID {doctor_id} не найден"
        )
    
    schedules = crud_clinic.get_doctor_schedules(db, doctor_id)
    return schedules


@router.put("/doctors/{doctor_id}/schedule", response_model=List[ScheduleOut])
def update_doctor_schedule(
    doctor_id: int,
    schedule_data: WeeklyScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить недельное расписание врача"""
    try:
        # Проверяем существование врача
        doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден"
            )
        
        # Конвертируем данные для CRUD
        schedules_dict = []
        for schedule in schedule_data.schedules:
            schedules_dict.append(schedule.model_dump())
        
        updated_schedules = crud_clinic.update_weekly_schedule(db, doctor_id, schedules_dict)
        return updated_schedules
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления расписания: {str(e)}"
        )


@router.post("/doctors/{doctor_id}/schedule", response_model=ScheduleOut)
def create_schedule(
    doctor_id: int,
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Создать расписание для врача"""
    try:
        # Проверяем существование врача
        doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден"
            )
        
        # Устанавливаем doctor_id
        schedule.doctor_id = doctor_id
        
        new_schedule = crud_clinic.create_schedule(db, schedule)
        return new_schedule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания расписания: {str(e)}"
        )


# ===================== СПЕЦИАЛЬНОСТИ И СТАТИСТИКА =====================

@router.get("/specialties")
def get_specialties(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить список специальностей"""
    try:
        # Получаем уникальные специальности из врачей
        from sqlalchemy import distinct
        from app.models.clinic import Doctor
        
        specialties_query = db.query(distinct(Doctor.specialty)).filter(Doctor.active == True).all()
        specialties = [s[0] for s in specialties_query if s[0]]
        
        # Добавляем информацию о каждой специальности
        specialty_info = {
            'cardiology': {
                'name_ru': 'Кардиология',
                'name_uz': 'Kardiologiya',
                'name_en': 'Cardiology',
                'description': 'Консультации кардиолога, ЭКГ, ЭхоКГ',
                'color': '#dc3545'
            },
            'dermatology': {
                'name_ru': 'Дерматология',
                'name_uz': 'Dermatologiya',
                'name_en': 'Dermatology', 
                'description': 'Дерматология и косметология',
                'color': '#fd7e14'
            },
            'stomatology': {
                'name_ru': 'Стоматология',
                'name_uz': 'Stomatologiya',
                'name_en': 'Stomatology',
                'description': 'Стоматологические услуги',
                'color': '#007bff'
            }
        }
        
        result = []
        for specialty in specialties:
            info = specialty_info.get(specialty, {
                'name_ru': specialty,
                'name_uz': specialty,
                'name_en': specialty,
                'description': '',
                'color': '#6c757d'
            })
            
            # Подсчитываем количество врачей
            doctor_count = db.query(Doctor).filter(
                Doctor.specialty == specialty,
                Doctor.active == True
            ).count()
            
            result.append({
                'code': specialty,
                'doctor_count': doctor_count,
                **info
            })
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения специальностей: {str(e)}"
        )


@router.get("/doctors/stats")
def get_doctors_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить статистику по врачам"""
    try:
        from app.models.clinic import Doctor
        
        total_doctors = db.query(Doctor).filter(Doctor.active == True).count()
        
        # Статистика по специальностям
        specialty_stats = {}
        specialties = db.query(Doctor.specialty).filter(Doctor.active == True).distinct().all()
        
        for (specialty,) in specialties:
            if specialty:
                count = db.query(Doctor).filter(
                    Doctor.specialty == specialty,
                    Doctor.active == True
                ).count()
                specialty_stats[specialty] = count
        
        return {
            'total_doctors': total_doctors,
            'by_specialty': specialty_stats,
            'active_doctors': total_doctors  # Все врачи активные в этом запросе
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики врачей: {str(e)}"
        )
