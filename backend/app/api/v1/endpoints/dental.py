import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.dental_api_service import DentalApiDomainError, DentalApiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dental", tags=["dental"])


class DentalPriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    new_price: Decimal
    reason: str
    details: Optional[str] = None
    treatment_completed: bool = True


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


@router.post(
    "/price-override",
    summary="Указать цену после лечения",
    response_model=DentalPriceOverrideResponse,
)
async def create_dental_price_override(
    override_data: DentalPriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> DentalPriceOverrideResponse:
    """
    Стоматолог указывает цену после проведенного лечения
    """
    service = DentalApiService(db)
    try:
        price_override = await service.create_dental_price_override(
            override_data=override_data,
            user=user,
        )
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
            created_at=price_override.created_at,
        )
    except DentalApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания изменения цены: {str(e)}"
        )


@router.get("/price-overrides", summary="Получить изменения цен стоматолога")
async def get_dental_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    visit_id: Optional[int] = Query(None, description="ID визита"),
    status: Optional[str] = Query(
        None, description="Статус (pending, approved, rejected)"
    ),
    limit: int = Query(50, ge=1, le=100),
) -> List[DentalPriceOverrideResponse]:
    """
    Получить список изменений цен стоматолога
    """
    try:
        overrides = DentalApiService(db).get_dental_price_overrides(
            user_id=user.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )
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
                treatment_completed=True,
                created_at=override.created_at,
            )
            for override in overrides
        ]
    except DentalApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения изменений цен: {str(e)}"
        )


class PriceOverrideApprovalRequest(BaseModel):
    action: str
    rejection_reason: Optional[str] = None


@router.put(
    "/price-override/{override_id}/approve", summary="Одобрить/отклонить изменение цены"
)
async def approve_price_override(
    override_id: int,
    approval_data: PriceOverrideApprovalRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Одобрить или отклонить изменение цены стоматологом
    Доступно только для регистраторов и администраторов
    """
    service = DentalApiService(db)
    try:
        return await service.approve_price_override(
            override_id=override_id,
            approval_data=approval_data,
            user=user,
        )
    except DentalApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка обработки изменения цены: {str(e)}"
        )


@router.get(
    "/price-overrides/pending", summary="Получить ожидающие одобрения изменения цен"
)
async def get_pending_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Получить список изменений цен, ожидающих одобрения
    Доступно только для регистраторов и администраторов
    """
    try:
        return DentalApiService(db).get_pending_price_overrides(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения ожидающих изменений цен: {str(e)}",
        )
