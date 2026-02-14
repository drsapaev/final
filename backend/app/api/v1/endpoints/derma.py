from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.derma_api_service import DermaApiDomainError, DermaApiService

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


@router.post(
    "/price-override",
    summary="Изменить цену процедуры",
    response_model=PriceOverrideResponse,
)
async def create_price_override(
    override_data: PriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
) -> PriceOverrideResponse:
    """
    Дерматолог изменяет цену процедуры с указанием причины
    """
    try:
        service = DermaApiService(db)
        price_override = service.create_price_override(
            override_data=override_data,
            user_id=user.id,
        )

        return PriceOverrideResponse(
            id=price_override.id,
            visit_id=price_override.visit_id,
            service_id=price_override.service_id,
            original_price=price_override.original_price,
            new_price=price_override.new_price,
            reason=price_override.reason,
            details=price_override.details,
            status=price_override.status,
            created_at=price_override.created_at,
        )

    except DermaApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания изменения цены: {str(e)}"
        )


@router.get("/price-overrides", summary="Получить изменения цен")
async def get_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor", "derma")),
    visit_id: Optional[int] = Query(None, description="ID визита"),
    status: Optional[str] = Query(
        None, description="Статус (pending, approved, rejected)"
    ),
    limit: int = Query(50, ge=1, le=100),
) -> List[PriceOverrideResponse]:
    """
    Получить список изменений цен дерматолога
    """
    try:
        overrides = DermaApiService(db).get_price_overrides(
            user_id=user.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

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
                created_at=override.created_at,
            )
            for override in overrides
        ]

    except DermaApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
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
