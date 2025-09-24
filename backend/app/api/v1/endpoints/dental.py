from typing import Any, Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.visit import Visit
from app.models.service import Service
from app.models.clinic import Doctor

router = APIRouter(prefix="/dental", tags=["dental"])


class DentalPriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    new_price: Decimal
    reason: str
    details: Optional[str] = None
    treatment_completed: bool = True  # Для стоматолога - указание цены после лечения


class DentalPriceOverrideResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    original_price: Decimal
    new_price: Decimal
    reason: str
    details: Optional[str]
    status: str
    treatment_completed: bool
    created_at: datetime


@router.get("/examinations", summary="Стоматологические осмотры")
async def get_dental_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить список стоматологических осмотров
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения осмотров: {str(e)}"
        )


@router.post("/examinations", summary="Создать стоматологический осмотр")
async def create_dental_examination(
    examination_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Dict[str, Any]:
    """
    Создать новый стоматологический осмотр
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Стоматологический осмотр создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания осмотра: {str(e)}"
        )


@router.get("/treatments", summary="Планы лечения")
async def get_treatment_plans(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить список планов лечения
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения планов лечения: {str(e)}"
        )


@router.post("/treatments", summary="Создать план лечения")
async def create_treatment_plan(
    treatment_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Dict[str, Any]:
    """
    Создать новый план лечения
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "План лечения создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания плана лечения: {str(e)}"
        )


@router.get("/prosthetics", summary="Протезирование")
async def get_prosthetics(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить список протезов
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения протезов: {str(e)}"
        )


@router.post("/prosthetics", summary="Создать протез")
async def create_prosthetic(
    prosthetic_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Dict[str, Any]:
    """
    Создать новый протез
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Протез создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания протеза: {str(e)}"
        )


@router.get("/xray", summary="Рентгеновские снимки")
async def get_xray_images(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    patient_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить рентгеновские снимки пациента
    """
    try:
        return {
            "message": "Модуль рентгеновских снимков будет доступен в следующей версии"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения снимков: {str(e)}"
        )


@router.post("/price-override", summary="Указать цену после лечения", response_model=DentalPriceOverrideResponse)
async def create_dental_price_override(
    override_data: DentalPriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> DentalPriceOverrideResponse:
    """
    Стоматолог указывает цену после проведенного лечения
    """
    try:
        # Проверяем существование визита
        visit = db.query(Visit).filter(Visit.id == override_data.visit_id).first()
        if not visit:
            raise HTTPException(status_code=404, detail="Визит не найден")
        
        # Проверяем существование услуги
        service = db.query(Service).filter(Service.id == override_data.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Услуга не найдена")
        
        # Проверяем, что услуга разрешает изменение цены врачом
        if not service.allow_doctor_price_override:
            raise HTTPException(
                status_code=400, 
                detail="Данная услуга не разрешает изменение цены врачом"
            )
        
        # Получаем врача по пользователю
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Врач не найден")
        
        # Проверяем, что врач - стоматолог
        if doctor.specialty not in ["stomatology", "dental"]:
            raise HTTPException(
                status_code=403, 
                detail="Только стоматолог может указывать цену после лечения"
            )
        
        # Создаём запись об изменении цены
        price_override = DoctorPriceOverride(
            visit_id=override_data.visit_id,
            doctor_id=doctor.id,
            service_id=override_data.service_id,
            original_price=service.price or Decimal("0"),
            new_price=override_data.new_price,
            reason=override_data.reason,
            details=override_data.details,
            status="pending"  # Требует одобрения регистратуры
        )
        
        db.add(price_override)
        db.commit()
        db.refresh(price_override)
        
        # TODO: Отправить уведомление в регистратуру
        # Это будет реализовано в следующем пункте 5.3
        
        return DentalPriceOverrideResponse(
            id=price_override.id,
            visit_id=price_override.visit_id,
            service_id=price_override.service_id,
            original_price=price_override.original_price,
            new_price=price_override.new_price,
            reason=price_override.reason,
            details=price_override.details,
            status=price_override.status,
            treatment_completed=override_data.treatment_completed,
            created_at=price_override.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания изменения цены: {str(e)}"
        )


@router.get("/price-overrides", summary="Получить изменения цен стоматолога")
async def get_dental_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    visit_id: Optional[int] = Query(None, description="ID визита"),
    status: Optional[str] = Query(None, description="Статус (pending, approved, rejected)"),
    limit: int = Query(50, ge=1, le=100),
) -> List[DentalPriceOverrideResponse]:
    """
    Получить список изменений цен стоматолога
    """
    try:
        # Получаем врача по пользователю
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Врач не найден")
        
        query = db.query(DoctorPriceOverride).filter(
            DoctorPriceOverride.doctor_id == doctor.id
        )
        
        if visit_id:
            query = query.filter(DoctorPriceOverride.visit_id == visit_id)
        
        if status:
            query = query.filter(DoctorPriceOverride.status == status)
        
        overrides = query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()
        
        return [
            DentalPriceOverrideResponse(
                id=override.id,
                visit_id=override.visit_id,
                service_id=override.service_id,
                original_price=override.original_price,
                new_price=override.new_price,
                reason=override.reason,
                details=override.details,
                status=override.status,
                treatment_completed=True,  # Для стоматолога всегда True
                created_at=override.created_at
            )
            for override in overrides
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения изменений цен: {str(e)}"
        )
