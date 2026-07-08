"""
API endpoints для динамического ценообразования и пакетных услуг
"""

import logging
from datetime import datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.models.dynamic_pricing import DiscountType, PricingRuleType
from app.models.user import User
from app.services.dynamic_pricing_api_service import (
    DynamicPricingApiDomainError,
    DynamicPricingApiService,
)

router = APIRouter()

logger = logging.getLogger(__name__)


def _raise_dynamic_pricing_internal_error(action: str, exc: Exception) -> NoReturn:
    if isinstance(exc, HTTPException):
        raise exc
    logger.error(
        "Dynamic pricing endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


def _raise_dynamic_pricing_bad_request(action: str, exc: Exception) -> NoReturn:
    logger.warning(
        "Dynamic pricing request rejected action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid dynamic pricing request",
    ) from exc


# === Pydantic схемы ===


class PricingRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    rule_type: PricingRuleType
    discount_type: DiscountType
    discount_value: float = Field(..., gt=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    start_time: str | None = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    end_time: str | None = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    days_of_week: str | None = Field(None, pattern=r"^[1-7](,[1-7])*$")
    min_quantity: int = Field(1, ge=1)
    max_quantity: int | None = Field(None, ge=1)
    min_amount: float | None = Field(None, ge=0)
    priority: int = Field(0, ge=0)
    max_uses: int | None = Field(None, ge=1)
    service_ids: list[int] = Field(..., min_length=1)


class PricingRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    discount_value: float | None = Field(None, gt=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    start_time: str | None = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    end_time: str | None = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    days_of_week: str | None = Field(None, pattern=r"^[1-7](,[1-7])*$")
    min_quantity: int | None = Field(None, ge=1)
    max_quantity: int | None = Field(None, ge=1)
    min_amount: float | None = Field(None, ge=0)
    priority: int | None = Field(None, ge=0)
    max_uses: int | None = Field(None, ge=1)


class ServicePackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    service_ids: list[int] = Field(..., min_length=2)
    package_price: float = Field(..., gt=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_purchases: int | None = Field(None, ge=1)
    per_patient_limit: int | None = Field(None, ge=1)


class ServicePackageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    package_price: float | None = Field(None, gt=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_purchases: int | None = Field(None, ge=1)
    per_patient_limit: int | None = Field(None, ge=1)


class PriceCalculationRequest(BaseModel):
    services: list[dict[str, Any]] = Field(..., min_length=1)
    patient_id: int | None = None
    appointment_time: datetime | None = None


class PackagePurchaseRequest(BaseModel):
    package_id: int
    patient_id: int
    visit_id: int | None = None
    appointment_id: int | None = None


class PricingRuleResponse(BaseModel):
    id: int
    name: str
    description: str | None
    rule_type: str
    discount_type: str
    discount_value: float
    is_active: bool
    start_date: datetime | None
    end_date: datetime | None
    start_time: str | None
    end_time: str | None
    days_of_week: str | None
    min_quantity: int
    max_quantity: int | None
    min_amount: float | None
    priority: int
    max_uses: int | None
    current_uses: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServicePackageResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    package_price: float
    original_price: float | None
    savings_amount: float | None
    savings_percentage: float | None
    valid_from: datetime | None
    valid_to: datetime | None
    max_purchases: int | None
    current_purchases: int
    per_patient_limit: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


# === API endpoints ===


@router.post("/pricing-rules", response_model=PricingRuleResponse)
def create_pricing_rule(
    rule_data: PricingRuleCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Создать правило ценообразования"""
    service = DynamicPricingApiService(db)
    try:
        return service.create_pricing_rule(
            payload=_model_to_dict(rule_data),
            current_user_id=current_user.id,
        )
    except Exception as e:
        service.rollback()
        _raise_dynamic_pricing_bad_request("create_pricing_rule", e)


@router.get("/pricing-rules", response_model=list[PricingRuleResponse])
def get_pricing_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    rule_type: PricingRuleType | None = None,
    is_active: bool | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Получить список правил ценообразования"""
    return DynamicPricingApiService(db).list_pricing_rules(
        skip=skip,
        limit=limit,
        rule_type=rule_type,
        is_active=is_active,
    )


@router.get("/pricing-rules/{rule_id}", response_model=PricingRuleResponse)
def get_pricing_rule(
    rule_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Получить правило ценообразования по ID"""
    try:
        return DynamicPricingApiService(db).get_pricing_rule(rule_id=rule_id)
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.put("/pricing-rules/{rule_id}", response_model=PricingRuleResponse)
def update_pricing_rule(
    rule_id: int,
    rule_data: PricingRuleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Обновить правило ценообразования"""
    service = DynamicPricingApiService(db)
    try:
        return service.update_pricing_rule(
            rule_id=rule_id,
            payload=_model_to_dict(rule_data),
        )
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        _raise_dynamic_pricing_internal_error("update_pricing_rule", e)


@router.delete("/pricing-rules/{rule_id}", response_model=dict[str, Any])
def delete_pricing_rule(
    rule_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Удалить правило ценообразования"""
    service = DynamicPricingApiService(db)
    try:
        return service.delete_pricing_rule(rule_id=rule_id)
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        _raise_dynamic_pricing_internal_error("delete_pricing_rule", e)


@router.post("/calculate-price", response_model=dict[str, Any])
def calculate_price(
    request: PriceCalculationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Рассчитать цену с учетом правил ценообразования"""
    service = DynamicPricingApiService(db)
    try:
        return service.calculate_price(
            services=request.services,
            patient_id=request.patient_id,
            appointment_time=request.appointment_time,
        )
    except Exception as e:
        _raise_dynamic_pricing_bad_request("calculate_price", e)


@router.post("/service-packages", response_model=ServicePackageResponse)
def create_service_package(
    package_data: ServicePackageCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Создать пакет услуг"""
    service = DynamicPricingApiService(db)
    try:
        return service.create_service_package(
            payload=_model_to_dict(package_data),
            current_user_id=current_user.id,
        )
    except Exception as e:
        service.rollback()
        _raise_dynamic_pricing_bad_request("create_service_package", e)


@router.get("/service-packages", response_model=list[ServicePackageResponse])
def get_service_packages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: bool | None = None,
    patient_id: int | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Получить список пакетов услуг"""
    return DynamicPricingApiService(db).list_service_packages(
        skip=skip,
        limit=limit,
        is_active=is_active,
        patient_id=patient_id,
    )


@router.get("/service-packages/{package_id}", response_model=ServicePackageResponse)
def get_service_package(
    package_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Получить пакет услуг по ID"""
    try:
        return DynamicPricingApiService(db).get_service_package(package_id=package_id)
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.put("/service-packages/{package_id}", response_model=ServicePackageResponse)
def update_service_package(
    package_id: int,
    package_data: ServicePackageUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Обновить пакет услуг"""
    service = DynamicPricingApiService(db)
    try:
        return service.update_service_package(
            package_id=package_id,
            payload=_model_to_dict(package_data),
        )
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        _raise_dynamic_pricing_internal_error("update_service_package", e)


@router.delete("/service-packages/{package_id}", response_model=dict[str, Any])
def delete_service_package(
    package_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Удалить пакет услуг"""
    service = DynamicPricingApiService(db)
    try:
        return service.delete_service_package(package_id=package_id)
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        _raise_dynamic_pricing_internal_error("delete_service_package", e)


@router.post("/purchase-package", response_model=dict[str, Any])
def purchase_package(
    request: PackagePurchaseRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Купить пакет услуг"""
    service = DynamicPricingApiService(db)
    try:
        purchase = service.purchase_package(
            package_id=request.package_id,
            patient_id=request.patient_id,
            visit_id=request.visit_id,
            appointment_id=request.appointment_id,
        )
        return {
            "purchase_id": purchase.id,
            "package_id": purchase.package_id,
            "patient_id": purchase.patient_id,
            "purchase_price": purchase.purchase_price,
            "savings_amount": purchase.savings_amount,
            "status": purchase.status,
            "purchased_at": purchase.purchased_at,
            "expires_at": purchase.expires_at,
        }
    except ValueError as e:
        _raise_dynamic_pricing_bad_request("purchase_package_validation", e)
    except Exception as e:
        _raise_dynamic_pricing_internal_error("purchase_package", e)


@router.post("/update-dynamic-prices", response_model=dict[str, Any])
def update_dynamic_prices(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Обновить динамические цены"""
    service = DynamicPricingApiService(db)
    try:
        return service.update_dynamic_prices()
    except Exception as e:
        _raise_dynamic_pricing_internal_error("update_dynamic_prices", e)


@router.get("/pricing-analytics", response_model=dict[str, Any])
def get_pricing_analytics(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Получить аналитику по ценообразованию"""
    service = DynamicPricingApiService(db)
    try:
        return service.get_pricing_analytics(start_date=start_date, end_date=end_date)
    except Exception as e:
        _raise_dynamic_pricing_internal_error("get_pricing_analytics", e)


@router.get("/price-history/{service_id}", response_model=dict[str, Any])
def get_price_history(
    service_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """Получить историю изменения цен для услуги"""
    return DynamicPricingApiService(db).get_price_history(
        service_id=service_id,
        skip=skip,
        limit=limit,
    )
