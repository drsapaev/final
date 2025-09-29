"""
API для управления лимитами онлайн-очередей
"""
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.crud.clinic import get_queue_settings, update_queue_settings
from sqlalchemy import and_

router = APIRouter()


# ===================== PYDANTIC МОДЕЛИ =====================

class QueueLimitSettings(BaseModel):
    """Настройки лимитов для специальности"""
    specialty: str = Field(..., description="Специальность врача")
    max_per_day: int = Field(15, ge=1, le=100, description="Максимум записей в день")
    start_number: int = Field(1, ge=1, le=999, description="Начальный номер очереди")
    enabled: bool = Field(True, description="Включены ли лимиты для этой специальности")


class QueueLimitUpdate(BaseModel):
    """Обновление лимитов"""
    specialty: str = Field(..., description="Специальность")
    max_per_day: Optional[int] = Field(None, ge=1, le=100)
    start_number: Optional[int] = Field(None, ge=1, le=999)
    enabled: Optional[bool] = Field(None)


class DoctorQueueLimit(BaseModel):
    """Индивидуальный лимит для врача"""
    doctor_id: int = Field(..., description="ID врача")
    day: date = Field(..., description="Дата")
    max_online_entries: int = Field(15, ge=0, le=100, description="Максимум онлайн записей")


class QueueLimitResponse(BaseModel):
    """Ответ с информацией о лимитах"""
    specialty: str
    max_per_day: int
    start_number: int
    enabled: bool
    current_usage: int
    doctors_count: int
    last_updated: Optional[datetime]


class QueueStatusResponse(BaseModel):
    """Статус очереди с лимитами"""
    doctor_id: int
    doctor_name: str
    specialty: str
    cabinet: Optional[str]
    day: date
    current_entries: int
    max_entries: int
    limit_reached: bool
    queue_opened: bool
    online_available: bool


# ===================== ПОЛУЧЕНИЕ НАСТРОЕК ЛИМИТОВ =====================

@router.get("/queue-limits", response_model=List[QueueLimitResponse])
def get_queue_limits(
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить настройки лимитов очередей
    """
    try:
        # Получаем текущие настройки
        queue_settings = get_queue_settings(db)
        max_per_day_settings = queue_settings.get("max_per_day", {})
        start_numbers_settings = queue_settings.get("start_numbers", {})
        
        # Получаем все специальности из базы врачей
        doctors_query = db.query(Doctor).filter(Doctor.active == True)
        if specialty:
            doctors_query = doctors_query.filter(Doctor.specialty == specialty)
        
        doctors = doctors_query.all()
        
        # Группируем по специальностям
        specialties = {}
        for doctor in doctors:
            if doctor.specialty not in specialties:
                specialties[doctor.specialty] = {
                    "doctors": [],
                    "current_usage": 0
                }
            specialties[doctor.specialty]["doctors"].append(doctor)
        
        # Подсчитываем текущее использование для каждой специальности
        today = date.today()
        for spec_name, spec_data in specialties.items():
            total_usage = 0
            for doctor in spec_data["doctors"]:
                daily_queue = db.query(DailyQueue).filter(
                    and_(
                        DailyQueue.day == today,
                        DailyQueue.specialist_id == doctor.id
                    )
                ).first()
                
                if daily_queue:
                    entries_count = db.query(OnlineQueueEntry).filter(
                        OnlineQueueEntry.queue_id == daily_queue.id
                    ).count()
                    total_usage += entries_count
            
            spec_data["current_usage"] = total_usage
        
        # Формируем ответ
        result = []
        for spec_name, spec_data in specialties.items():
            result.append(QueueLimitResponse(
                specialty=spec_name,
                max_per_day=max_per_day_settings.get(spec_name, 15),
                start_number=start_numbers_settings.get(spec_name, 1),
                enabled=True,  # Пока все включены
                current_usage=spec_data["current_usage"],
                doctors_count=len(spec_data["doctors"]),
                last_updated=datetime.utcnow()
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения лимитов: {str(e)}"
        )


# ===================== ОБНОВЛЕНИЕ ЛИМИТОВ =====================

@router.put("/queue-limits")
def update_queue_limits(
    limits: List[QueueLimitUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Обновить настройки лимитов очередей
    """
    try:
        # Получаем текущие настройки
        queue_settings = get_queue_settings(db)
        max_per_day = queue_settings.get("max_per_day", {})
        start_numbers = queue_settings.get("start_numbers", {})
        
        # Обновляем настройки
        updated_specialties = []
        for limit_update in limits:
            if limit_update.max_per_day is not None:
                max_per_day[limit_update.specialty] = limit_update.max_per_day
            
            if limit_update.start_number is not None:
                start_numbers[limit_update.specialty] = limit_update.start_number
            
            updated_specialties.append(limit_update.specialty)
        
        # Сохраняем обновленные настройки
        new_settings = {
            **queue_settings,
            "max_per_day": max_per_day,
            "start_numbers": start_numbers
        }
        
        update_queue_settings(db, new_settings, current_user.id)
        
        return {
            "success": True,
            "message": f"Лимиты обновлены для специальностей: {', '.join(updated_specialties)}",
            "updated_specialties": updated_specialties,
            "updated_at": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления лимитов: {str(e)}"
        )


# ===================== СТАТУС ОЧЕРЕДЕЙ С ЛИМИТАМИ =====================

@router.get("/queue-status", response_model=List[QueueStatusResponse])
def get_queue_status_with_limits(
    day: Optional[date] = Query(None, description="Дата (по умолчанию сегодня)"),
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить статус очередей с информацией о лимитах
    """
    try:
        if day is None:
            day = date.today()
        
        # Получаем настройки лимитов
        queue_settings = get_queue_settings(db)
        max_per_day_settings = queue_settings.get("max_per_day", {})
        
        # Получаем врачей
        doctors_query = db.query(Doctor).filter(Doctor.active == True)
        if specialty:
            doctors_query = doctors_query.filter(Doctor.specialty == specialty)
        
        doctors = doctors_query.all()
        
        result = []
        for doctor in doctors:
            # Получаем очередь на день
            daily_queue = db.query(DailyQueue).filter(
                and_(
                    DailyQueue.day == day,
                    DailyQueue.specialist_id == doctor.id
                )
            ).first()
            
            current_entries = 0
            queue_opened = False
            
            if daily_queue:
                current_entries = db.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.queue_id == daily_queue.id
                ).count()
                queue_opened = daily_queue.opened_at is not None
            
            # Получаем лимит для специальности
            max_entries = max_per_day_settings.get(doctor.specialty, 15)
            
            # Проверяем доступность онлайн записи
            online_available = not queue_opened and current_entries < max_entries
            
            result.append(QueueStatusResponse(
                doctor_id=doctor.id,
                doctor_name=doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                specialty=doctor.specialty,
                cabinet=doctor.cabinet,
                day=day,
                current_entries=current_entries,
                max_entries=max_entries,
                limit_reached=current_entries >= max_entries,
                queue_opened=queue_opened,
                online_available=online_available
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса очередей: {str(e)}"
        )


# ===================== ИНДИВИДУАЛЬНЫЕ ЛИМИТЫ ДЛЯ ВРАЧЕЙ =====================

@router.put("/doctor-queue-limit")
def set_doctor_queue_limit(
    limit_data: DoctorQueueLimit,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Установить индивидуальный лимит для врача на конкретный день
    """
    try:
        # Проверяем существование врача
        doctor = db.query(Doctor).filter(Doctor.id == limit_data.doctor_id).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден"
            )
        
        # Получаем или создаем очередь на день
        daily_queue = db.query(DailyQueue).filter(
            and_(
                DailyQueue.day == limit_data.day,
                DailyQueue.specialist_id == limit_data.doctor_id
            )
        ).first()
        
        if not daily_queue:
            daily_queue = DailyQueue(
                day=limit_data.day,
                specialist_id=limit_data.doctor_id,
                active=True,
                max_online_entries=limit_data.max_online_entries
            )
            db.add(daily_queue)
        else:
            daily_queue.max_online_entries = limit_data.max_online_entries
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Лимит установлен для врача {doctor.user.full_name if doctor.user else f'#{doctor.id}'} на {limit_data.day}",
            "doctor_id": limit_data.doctor_id,
            "day": limit_data.day,
            "max_online_entries": limit_data.max_online_entries,
            "updated_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка установки лимита: {str(e)}"
        )


# ===================== СБРОС ЛИМИТОВ =====================

@router.post("/reset-queue-limits")
def reset_queue_limits(
    specialty: Optional[str] = Query(None, description="Сбросить лимиты для конкретной специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Сбросить лимиты очередей к значениям по умолчанию
    """
    try:
        queue_settings = get_queue_settings(db)
        
        if specialty:
            # Сбрасываем для конкретной специальности
            max_per_day = queue_settings.get("max_per_day", {})
            start_numbers = queue_settings.get("start_numbers", {})
            
            max_per_day[specialty] = 15  # Значение по умолчанию
            start_numbers[specialty] = 1   # Значение по умолчанию
            
            new_settings = {
                **queue_settings,
                "max_per_day": max_per_day,
                "start_numbers": start_numbers
            }
            
            message = f"Лимиты сброшены для специальности: {specialty}"
        else:
            # Сбрасываем все лимиты
            new_settings = {
                **queue_settings,
                "max_per_day": {},
                "start_numbers": {}
            }
            message = "Все лимиты сброшены к значениям по умолчанию"
        
        update_queue_settings(db, new_settings, current_user.id)
        
        return {
            "success": True,
            "message": message,
            "reset_at": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сброса лимитов: {str(e)}"
        )


