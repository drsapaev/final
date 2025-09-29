"""
API endpoints для получения информации о врачах и отделениях
"""
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.doctor_info_service import get_doctor_info_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== PYDANTIC СХЕМЫ =====================

class DoctorInfoResponse(BaseModel):
    """Схема ответа с информацией о враче"""
    id: int
    full_name: str
    specialization: str
    department: str
    department_id: Optional[int] = None
    cabinet: Optional[Dict[str, Any]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    schedule: Optional[str] = None
    experience_years: Optional[int] = None

class DepartmentInfoResponse(BaseModel):
    """Схема ответа с информацией об отделении"""
    id: int
    name: str
    description: Optional[str] = None
    head_doctor: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    is_active: bool

class DoctorListResponse(BaseModel):
    """Схема списка врачей"""
    doctors: List[DoctorInfoResponse]
    total_count: int

class DepartmentListResponse(BaseModel):
    """Схема списка отделений"""
    departments: List[DepartmentInfoResponse]
    total_count: int

class AppointmentDoctorInfoResponse(BaseModel):
    """Схема информации о враче для записи"""
    doctor: DoctorInfoResponse
    department: DepartmentInfoResponse

# ===================== ENDPOINTS =====================

@router.get("/doctors/{doctor_id}", response_model=DoctorInfoResponse)
async def get_doctor_info(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить информацию о враче"""
    try:
        service = get_doctor_info_service(db)
        doctor_info = service.get_doctor_full_info(doctor_id)
        
        return DoctorInfoResponse(**doctor_info)
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о враче {doctor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о враче: {str(e)}"
        )

@router.get("/doctors", response_model=DoctorListResponse)
async def get_doctors_list(
    specialization: Optional[str] = Query(None, description="Фильтр по специализации"),
    department_name: Optional[str] = Query(None, description="Фильтр по отделению"),
    active_only: bool = Query(True, description="Только активные врачи"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить список врачей"""
    try:
        service = get_doctor_info_service(db)
        
        if specialization:
            doctors = service.get_doctors_by_specialization(specialization)
        elif department_name:
            doctors = service.get_doctors_by_department(department_name)
        else:
            # Получаем всех врачей (можно добавить метод get_all_doctors)
            doctors = []
        
        # Фильтруем по активности
        if active_only:
            doctors = [doc for doc in doctors if doc.get("is_active", False)]
        
        doctors_response = [DoctorInfoResponse(**doc) for doc in doctors]
        
        return DoctorListResponse(
            doctors=doctors_response,
            total_count=len(doctors_response)
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения списка врачей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка врачей: {str(e)}"
        )

@router.get("/doctors/by-user/{user_id}", response_model=DoctorInfoResponse)
async def get_doctor_by_user_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить информацию о враче по ID пользователя"""
    try:
        service = get_doctor_info_service(db)
        doctor_info = service.get_doctor_by_user_id(user_id)
        
        if not doctor_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден"
            )
        
        return DoctorInfoResponse(**doctor_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения врача по user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о враче: {str(e)}"
        )

@router.get("/departments/{department_id}", response_model=DepartmentInfoResponse)
async def get_department_info(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить информацию об отделении"""
    try:
        service = get_doctor_info_service(db)
        department_info = service.get_department_info(department_id)
        
        if not department_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Отделение не найдено"
            )
        
        return DepartmentInfoResponse(**department_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации об отделении {department_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации об отделении: {str(e)}"
        )

@router.get("/departments", response_model=DepartmentListResponse)
async def get_departments_list(
    active_only: bool = Query(True, description="Только активные отделения"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить список отделений"""
    try:
        service = get_doctor_info_service(db)
        departments = service.get_all_departments()
        
        # Фильтруем по активности
        if active_only:
            departments = [dept for dept in departments if dept.get("is_active", True)]
        
        departments_response = [DepartmentInfoResponse(**dept) for dept in departments]
        
        return DepartmentListResponse(
            departments=departments_response,
            total_count=len(departments_response)
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения списка отделений: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка отделений: {str(e)}"
        )

@router.get("/appointments/{appointment_id}/doctor-info", response_model=AppointmentDoctorInfoResponse)
async def get_appointment_doctor_info(
    appointment_id: int,
    appointment_type: str = Query("appointment", description="Тип записи: appointment или visit"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить информацию о враче для записи"""
    try:
        service = get_doctor_info_service(db)
        info = service.get_appointment_doctor_info(appointment_id, appointment_type)
        
        doctor_response = DoctorInfoResponse(**info["doctor"])
        department_response = DepartmentInfoResponse(**info["department"])
        
        return AppointmentDoctorInfoResponse(
            doctor=doctor_response,
            department=department_response
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о враче для записи {appointment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации: {str(e)}"
        )

@router.get("/doctors/{doctor_id}/formatted-info")
async def get_formatted_doctor_info(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить отформатированную информацию о враче для уведомлений"""
    try:
        service = get_doctor_info_service(db)
        doctor_info = service.get_doctor_full_info(doctor_id)
        formatted_info = service.format_doctor_info_for_notification(doctor_info)
        
        return {
            "doctor_id": doctor_id,
            "formatted_info": formatted_info,
            "raw_info": doctor_info
        }
        
    except Exception as e:
        logger.error(f"Ошибка форматирования информации о враче {doctor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка форматирования информации: {str(e)}"
        )

@router.get("/departments/{department_id}/formatted-info")
async def get_formatted_department_info(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """Получить отформатированную информацию об отделении для уведомлений"""
    try:
        service = get_doctor_info_service(db)
        department_info = service.get_department_info(department_id)
        
        if not department_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Отделение не найдено"
            )
        
        formatted_info = service.format_department_info_for_notification(department_info)
        
        return {
            "department_id": department_id,
            "formatted_info": formatted_info,
            "raw_info": department_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка форматирования информации об отделении {department_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка форматирования информации: {str(e)}"
        )

