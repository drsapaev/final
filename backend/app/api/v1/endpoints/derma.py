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

router = APIRouter(prefix="/derma", tags=["derma"])


class PriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    new_price: Decimal
    reason: str
    details: Optional[str] = None


class PriceOverrideResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    original_price: Decimal
    new_price: Decimal
    reason: str
    details: Optional[str]
    status: str
    created_at: datetime


@router.get("/examinations", summary="Осмотры кожи")
async def get_skin_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить список осмотров кожи
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения осмотров: {str(e)}"
        )


@router.post("/examinations", summary="Создать осмотр кожи")
async def create_skin_examination(
    examination_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
) -> Dict[str, Any]:
    """
    Создать новый осмотр кожи
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Осмотр кожи создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания осмотра: {str(e)}"
        )


@router.get("/procedures", summary="Косметические процедуры")
async def get_cosmetic_procedures(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить список косметических процедур
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения процедур: {str(e)}"
        )


@router.post("/procedures", summary="Создать косметическую процедуру")
async def create_cosmetic_procedure(
    procedure_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
) -> Dict[str, Any]:
    """
    Создать новую косметическую процедуру
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Косметическая процедура создана", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания процедуры: {str(e)}"
        )


@router.post("/price-override", summary="Изменить цену процедуры", response_model=PriceOverrideResponse)
async def create_price_override(
    override_data: PriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
) -> PriceOverrideResponse:
    """
    Дерматолог изменяет цену процедуры с указанием причины
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
        
        # Проверяем, что врач - дерматолог
        if doctor.specialty not in ["dermatology", "cosmetology"]:
            raise HTTPException(
                status_code=403, 
                detail="Только дерматолог-косметолог может изменять цены процедур"
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
            status="pending"
        )
        
        db.add(price_override)
        db.commit()
        db.refresh(price_override)
        
        return PriceOverrideResponse(
            id=price_override.id,
            visit_id=price_override.visit_id,
            service_id=price_override.service_id,
            original_price=price_override.original_price,
            new_price=price_override.new_price,
            reason=price_override.reason,
            details=price_override.details,
            status=price_override.status,
            created_at=price_override.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания изменения цены: {str(e)}"
        )


@router.get("/price-overrides", summary="Получить изменения цен")
async def get_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
    visit_id: Optional[int] = Query(None, description="ID визита"),
    status: Optional[str] = Query(None, description="Статус (pending, approved, rejected)"),
    limit: int = Query(50, ge=1, le=100),
) -> List[PriceOverrideResponse]:
    """
    Получить список изменений цен дерматолога
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
            PriceOverrideResponse(
                id=override.id,
                visit_id=override.visit_id,
                service_id=override.service_id,
                original_price=override.original_price,
                new_price=override.new_price,
                reason=override.reason,
                details=override.details,
                status=override.status,
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


@router.get("/photo-gallery", summary="Фотогалерея")
async def get_photo_gallery(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
    patient_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить фотогалерею пациента
    """
    try:
        return {"message": "Фотогалерея будет доступна в следующей версии"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения фотогалереи: {str(e)}"
        )
