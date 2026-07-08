import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.dental_api_service import DentalApiDomainError, DentalApiService
from app.schemas.dental import (
    DentalExaminationRequest,
    DentalProstheticRequest,
    DentalTreatmentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dental", tags=["dental"])

DENTAL_CLINICIAN_ROLES = ("Admin", "Doctor", "dentist")
DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL = (
    "Dental examination/treatment persistence is not implemented on this endpoint. "
    "Use the canonical visit protocol or odontogram workflow until a durable dental "
    "record contract is added."
)


class DentalPriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    # SPEC-AUDIT-28 P0-3: validate price is positive and reasonable
    new_price: Decimal = Field(..., gt=0, le=Decimal("1000000000"))
    reason: str
    details: str | None = None
    treatment_completed: bool = True


class DentalPriceOverrideResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    original_price: Decimal
    # SPEC-AUDIT-28 P0-3: validate price is positive and reasonable
    new_price: Decimal = Field(..., gt=0, le=Decimal("1000000000"))
    reason: str
    details: str | None
    status: str
    treatment_completed: bool
    created_at: datetime


@router.get("/examinations", summary="Стоматологические осмотры", response_model=list[dict[str, Any]])
async def get_dental_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список стоматологических осмотров
    """
    try:
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/examinations", summary="Создать стоматологический осмотр", response_model=dict[str, Any])
async def create_dental_examination(
    examination_data: DentalExaminationRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, Any]:
    """
    Создать новый стоматологический осмотр
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL,
    )


@router.get("/treatments", summary="Планы лечения", response_model=list[dict[str, Any]])
async def get_treatment_plans(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список планов лечения
    """
    try:
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/treatments", summary="Создать план лечения", response_model=dict[str, Any])
async def create_treatment_plan(
    treatment_data: DentalTreatmentRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, Any]:
    """
    Создать новый план лечения
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL,
    )


@router.get("/prosthetics", summary="Протезирование", response_model=list[dict[str, Any]])
async def get_prosthetics(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список протезов
    """
    try:
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/prosthetics", summary="Создать протез", response_model=dict[str, Any])
async def create_prosthetic(
    prosthetic_data: DentalProstheticRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, Any]:
    """
    Создать новый протез
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL,
    )


@router.get("/xray", summary="Рентгеновские снимки", response_model=dict[str, Any])
async def get_xray_images(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    patient_id: int | None = None,
) -> dict[str, Any]:
    """
    Получить рентгеновские снимки пациента
    """
    try:
        return {
            "message": "Модуль рентгеновских снимков будет доступен в следующей версии"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post(
    "/price-override",
    summary="Указать цену после лечения",
    response_model=DentalPriceOverrideResponse,
)
async def create_dental_price_override(
    override_data: DentalPriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
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
            status_code=500, detail="Internal server error"
        )


@router.get("/price-overrides", summary="Получить изменения цен стоматолога", response_model=list[DentalPriceOverrideResponse])
async def get_dental_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    visit_id: int | None = Query(None, description="ID визита"),
    status: str | None = Query(
        None, description="Статус (pending, approved, rejected)"
    ),
    limit: int = Query(50, ge=1, le=100),
) -> list[DentalPriceOverrideResponse]:
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
            status_code=500, detail="Internal server error"
        )


class PriceOverrideApprovalRequest(BaseModel):
    action: str
    rejection_reason: str | None = None


@router.put(
    "/price-override/{override_id}/approve", summary="Одобрить/отклонить изменение цены",
    response_model=dict[str, Any],
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
            status_code=500, detail="Internal server error"
        )


@router.get(
    "/price-overrides/pending", summary="Получить ожидающие одобрения изменения цен",
    response_model=dict[str, Any],
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
            detail="Internal server error",
        )
