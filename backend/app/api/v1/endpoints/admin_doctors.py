"""
API endpoints для управления врачами в админ панели
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import require_roles
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
        
        # Преобразуем в Pydantic модели с дополнительными данными
        result = []
        for doctor in doctors:
            # Создаем базовый DoctorOut из объекта
            doctor_dict = {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": doctor.price_default,
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
                "auto_close_time": doctor.auto_close_time,
                "active": doctor.active,
                "created_at": doctor.created_at,
                "updated_at": doctor.updated_at,
            }
            
            # Добавляем данные пользователя
            if doctor.user_id and doctor.user:
                doctor_dict["user"] = {
                    "id": doctor.user.id,
                    "username": doctor.user.username,
                    "full_name": doctor.user.full_name,
                    "email": doctor.user.email
                }
            else:
                doctor_dict["user"] = None
            
            # Загружаем расписания
            schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
            doctor_dict["schedules"] = [ScheduleOut.model_validate(s) for s in schedules]
            
            result.append(DoctorOut(**doctor_dict))
        
        return result
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
    
    # Создаем словарь для Pydantic модели
    doctor_dict = {
        "id": doctor.id,
        "user_id": doctor.user_id,
        "specialty": doctor.specialty,
        "cabinet": doctor.cabinet,
        "price_default": doctor.price_default,
        "start_number_online": doctor.start_number_online,
        "max_online_per_day": doctor.max_online_per_day,
        "auto_close_time": doctor.auto_close_time,
        "active": doctor.active,
        "created_at": doctor.created_at,
        "updated_at": doctor.updated_at,
    }
    
    # Добавляем данные пользователя
    if doctor.user_id and doctor.user:
        doctor_dict["user"] = {
            "id": doctor.user.id,
            "username": doctor.user.username,
            "full_name": doctor.user.full_name,
            "email": doctor.user.email
        }
    else:
        doctor_dict["user"] = None
    
    # Загружаем расписания
    schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
    doctor_dict["schedules"] = [ScheduleOut.model_validate(s) for s in schedules]
    
    return DoctorOut(**doctor_dict)


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
        
        # Преобразуем в DoctorOut с дополнительными данными
        doctor_dict = {
            "id": new_doctor.id,
            "user_id": new_doctor.user_id,
            "specialty": new_doctor.specialty,
            "cabinet": new_doctor.cabinet,
            "price_default": new_doctor.price_default,
            "start_number_online": new_doctor.start_number_online,
            "max_online_per_day": new_doctor.max_online_per_day,
            "auto_close_time": new_doctor.auto_close_time,
            "active": new_doctor.active,
            "created_at": new_doctor.created_at,
            "updated_at": new_doctor.updated_at,
        }
        
        # Добавляем данные пользователя
        if new_doctor.user_id and new_doctor.user:
            doctor_dict["user"] = {
                "id": new_doctor.user.id,
                "username": new_doctor.user.username,
                "full_name": new_doctor.user.full_name,
                "email": new_doctor.user.email
            }
        else:
            doctor_dict["user"] = None
        
        # Загружаем расписания
        schedules = crud_clinic.get_doctor_schedules(db, new_doctor.id)
        doctor_dict["schedules"] = [ScheduleOut.model_validate(s) for s in schedules]
        
        return DoctorOut(**doctor_dict)
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
        
        if not updated_doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден"
            )
        
        # Преобразуем в DoctorOut с дополнительными данными
        doctor_dict = {
            "id": updated_doctor.id,
            "user_id": updated_doctor.user_id,
            "specialty": updated_doctor.specialty,
            "cabinet": updated_doctor.cabinet,
            "price_default": updated_doctor.price_default,
            "start_number_online": updated_doctor.start_number_online,
            "max_online_per_day": updated_doctor.max_online_per_day,
            "auto_close_time": updated_doctor.auto_close_time,
            "active": updated_doctor.active,
            "created_at": updated_doctor.created_at,
            "updated_at": updated_doctor.updated_at,
        }
        
        # Добавляем данные пользователя
        if updated_doctor.user_id and updated_doctor.user:
            doctor_dict["user"] = {
                "id": updated_doctor.user.id,
                "username": updated_doctor.user.username,
                "full_name": updated_doctor.user.full_name,
                "email": updated_doctor.user.email
            }
        else:
            doctor_dict["user"] = None
        
        # Загружаем расписания
        schedules = crud_clinic.get_doctor_schedules(db, updated_doctor.id)
        doctor_dict["schedules"] = [ScheduleOut.model_validate(s) for s in schedules]
        
        return DoctorOut(**doctor_dict)
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
