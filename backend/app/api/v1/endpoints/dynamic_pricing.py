"""
API endpoints для динамического ценообразования и пакетных услуг
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.models.dynamic_pricing import DiscountType, PricingRuleType
from app.models.user import User
from app.services.dynamic_pricing_api_service import (
    DynamicPricingApiDomainError,
    DynamicPricingApiService,
)

router = APIRouter()


# === Pydantic схемы ===


class PricingRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    rule_type: PricingRuleType
    discount_type: DiscountType
    discount_value: float = Field(..., gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    start_time: Optional[str] = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    end_time: Optional[str] = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    days_of_week: Optional[str] = Field(None, pattern=r"^[1-7](,[1-7])*$")
    min_quantity: int = Field(1, ge=1)
    max_quantity: Optional[int] = Field(None, ge=1)
    min_amount: Optional[float] = Field(None, ge=0)
    priority: int = Field(0, ge=0)
    max_uses: Optional[int] = Field(None, ge=1)
    service_ids: List[int] = Field(..., min_items=1)


class PricingRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    discount_value: Optional[float] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    start_time: Optional[str] = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    end_time: Optional[str] = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
    )
    days_of_week: Optional[str] = Field(None, pattern=r"^[1-7](,[1-7])*$")
    min_quantity: Optional[int] = Field(None, ge=1)
    max_quantity: Optional[int] = Field(None, ge=1)
    min_amount: Optional[float] = Field(None, ge=0)
    priority: Optional[int] = Field(None, ge=0)
    max_uses: Optional[int] = Field(None, ge=1)


class ServicePackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    service_ids: List[int] = Field(..., min_items=2)
    package_price: float = Field(..., gt=0)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    max_purchases: Optional[int] = Field(None, ge=1)
    per_patient_limit: Optional[int] = Field(None, ge=1)


class ServicePackageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    package_price: Optional[float] = Field(None, gt=0)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    max_purchases: Optional[int] = Field(None, ge=1)
    per_patient_limit: Optional[int] = Field(None, ge=1)


class PriceCalculationRequest(BaseModel):
    services: List[Dict[str, Any]] = Field(..., min_items=1)
    patient_id: Optional[int] = None
    appointment_time: Optional[datetime] = None


class PackagePurchaseRequest(BaseModel):
    package_id: int
    patient_id: int
    visit_id: Optional[int] = None
    appointment_id: Optional[int] = None


class PricingRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    rule_type: str
    discount_type: str
    discount_value: float
    is_active: bool
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    start_time: Optional[str]
    end_time: Optional[str]
    days_of_week: Optional[str]
    min_quantity: int
    max_quantity: Optional[int]
    min_amount: Optional[float]
    priority: int
    max_uses: Optional[int]
    current_uses: int
    created_at: datetime

    class Config:
        from_attributes = True


class ServicePackageResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    package_price: float
    original_price: Optional[float]
    savings_amount: Optional[float]
    savings_percentage: Optional[float]
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    max_purchases: Optional[int]
    current_purchases: int
    per_patient_limit: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


# === API endpoints ===


@router.post("/pricing-rules", response_model=PricingRuleResponse)
def create_pricing_rule(
    rule_data: PricingRuleCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
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
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pricing-rules", response_model=List[PricingRuleResponse])
def get_pricing_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    rule_type: Optional[PricingRuleType] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
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
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pricing-rules/{rule_id}")
def delete_pricing_rule(
    rule_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Удалить правило ценообразования"""
    service = DynamicPricingApiService(db)
    try:
        return service.delete_pricing_rule(rule_id=rule_id)
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-price")
def calculate_price(
    request: PriceCalculationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
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
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/service-packages", response_model=ServicePackageResponse)
def create_service_package(
    package_data: ServicePackageCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
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
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/service-packages", response_model=List[ServicePackageResponse])
def get_service_packages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = None,
    patient_id: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
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
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/service-packages/{package_id}")
def delete_service_package(
    package_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Удалить пакет услуг"""
    service = DynamicPricingApiService(db)
    try:
        return service.delete_service_package(package_id=package_id)
    except DynamicPricingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase-package")
def purchase_package(
    request: PackagePurchaseRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-dynamic-prices")
def update_dynamic_prices(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Обновить динамические цены"""
    service = DynamicPricingApiService(db)
    try:
        return service.update_dynamic_prices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pricing-analytics")
def get_pricing_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Получить аналитику по ценообразованию"""
    service = DynamicPricingApiService(db)
    try:
        return service.get_pricing_analytics(start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-history/{service_id}")
def get_price_history(
    service_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Получить историю изменения цен для услуги"""
    return DynamicPricingApiService(db).get_price_history(
        service_id=service_id,
        skip=skip,
        limit=limit,
    )
