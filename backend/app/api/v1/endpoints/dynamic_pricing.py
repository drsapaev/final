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
from app.services.dynamic_pricing_service import DynamicPricingService

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
        None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
    )
    end_time: Optional[str] = Field(
        None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
    )
    days_of_week: Optional[str] = Field(None, pattern=r'^[1-7](,[1-7])*$')
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
        None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
    )
    end_time: Optional[str] = Field(
        None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
    )
    days_of_week: Optional[str] = Field(None, pattern=r'^[1-7](,[1-7])*$')
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


# === API endpoints ===


@router.post("/pricing-rules", response_model=PricingRuleResponse)
def create_pricing_rule(
    rule_data: PricingRuleCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Создать правило ценообразования"""
    service = DynamicPricingService(db)

    try:
        rule = service.create_pricing_rule(
            name=rule_data.name,
            description=rule_data.description,
            rule_type=rule_data.rule_type,
            discount_type=rule_data.discount_type,
            discount_value=rule_data.discount_value,
            start_date=rule_data.start_date,
            end_date=rule_data.end_date,
            start_time=rule_data.start_time,
            end_time=rule_data.end_time,
            days_of_week=rule_data.days_of_week,
            min_quantity=rule_data.min_quantity,
            max_quantity=rule_data.max_quantity,
            min_amount=rule_data.min_amount,
            priority=rule_data.priority,
            max_uses=rule_data.max_uses,
            created_by=current_user.id,
        )

        # Добавляем услуги к правилу
        from app.models.dynamic_pricing import PricingRuleService

        for service_id in rule_data.service_ids:
            rule_service = PricingRuleService(rule_id=rule.id, service_id=service_id)
            db.add(rule_service)
        db.commit()

        return rule
    except Exception as e:
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
    from app.models.dynamic_pricing import PricingRule

    query = db.query(PricingRule)

    if rule_type:
        query = query.filter(PricingRule.rule_type == rule_type)
    if is_active is not None:
        query = query.filter(PricingRule.is_active == is_active)

    rules = query.offset(skip).limit(limit).all()
    return rules


@router.get("/pricing-rules/{rule_id}", response_model=PricingRuleResponse)
def get_pricing_rule(
    rule_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Получить правило ценообразования по ID"""
    from app.models.dynamic_pricing import PricingRule

    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    return rule


@router.put("/pricing-rules/{rule_id}", response_model=PricingRuleResponse)
def update_pricing_rule(
    rule_id: int,
    rule_data: PricingRuleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Обновить правило ценообразования"""
    from app.models.dynamic_pricing import PricingRule

    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    # Обновляем поля
    for field, value in rule_data.dict(exclude_unset=True).items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/pricing-rules/{rule_id}")
def delete_pricing_rule(
    rule_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Удалить правило ценообразования"""
    from app.models.dynamic_pricing import PricingRule

    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    db.delete(rule)
    db.commit()
    return {"message": "Правило удалено"}


@router.post("/calculate-price")
def calculate_price(
    request: PriceCalculationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Рассчитать цену с учетом правил ценообразования"""
    service = DynamicPricingService(db)

    try:
        result = service.apply_pricing_rules(
            services=request.services,
            patient_id=request.patient_id,
            appointment_time=request.appointment_time,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/service-packages", response_model=ServicePackageResponse)
def create_service_package(
    package_data: ServicePackageCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Создать пакет услуг"""
    service = DynamicPricingService(db)

    try:
        package = service.create_service_package(
            name=package_data.name,
            description=package_data.description,
            service_ids=package_data.service_ids,
            package_price=package_data.package_price,
            valid_from=package_data.valid_from,
            valid_to=package_data.valid_to,
            max_purchases=package_data.max_purchases,
            per_patient_limit=package_data.per_patient_limit,
            created_by=current_user.id,
        )
        return package
    except Exception as e:
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
    service = DynamicPricingService(db)

    if patient_id:
        packages = service.get_available_packages(patient_id=patient_id)
    else:
        from app.models.dynamic_pricing import ServicePackage

        query = db.query(ServicePackage)

        if is_active is not None:
            query = query.filter(ServicePackage.is_active == is_active)

        packages = query.offset(skip).limit(limit).all()

    return packages


@router.get("/service-packages/{package_id}", response_model=ServicePackageResponse)
def get_service_package(
    package_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Получить пакет услуг по ID"""
    from app.models.dynamic_pricing import ServicePackage

    package = db.query(ServicePackage).filter(ServicePackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Пакет не найден")

    return package


@router.put("/service-packages/{package_id}", response_model=ServicePackageResponse)
def update_service_package(
    package_id: int,
    package_data: ServicePackageUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Обновить пакет услуг"""
    from app.models.dynamic_pricing import ServicePackage

    package = db.query(ServicePackage).filter(ServicePackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Пакет не найден")

    # Обновляем поля
    update_data = package_data.dict(exclude_unset=True)

    # Пересчитываем экономию если изменилась цена
    if 'package_price' in update_data and package.original_price:
        new_price = update_data['package_price']
        package.savings_amount = package.original_price - new_price
        package.savings_percentage = (
            (package.savings_amount / package.original_price * 100)
            if package.original_price > 0
            else 0
        )

    for field, value in update_data.items():
        setattr(package, field, value)

    db.commit()
    db.refresh(package)
    return package


@router.delete("/service-packages/{package_id}")
def delete_service_package(
    package_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Удалить пакет услуг"""
    from app.models.dynamic_pricing import ServicePackage

    package = db.query(ServicePackage).filter(ServicePackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Пакет не найден")

    db.delete(package)
    db.commit()
    return {"message": "Пакет удален"}


@router.post("/purchase-package")
def purchase_package(
    request: PackagePurchaseRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Купить пакет услуг"""
    service = DynamicPricingService(db)

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
    service = DynamicPricingService(db)

    try:
        result = service.update_dynamic_prices()
        return result
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
    service = DynamicPricingService(db)

    try:
        analytics = service.get_pricing_analytics(
            start_date=start_date, end_date=end_date
        )
        return analytics
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
    from app.models.dynamic_pricing import PriceHistory

    history = (
        db.query(PriceHistory)
        .filter(PriceHistory.service_id == service_id)
        .order_by(PriceHistory.changed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": h.id,
            "service_id": h.service_id,
            "old_price": h.old_price,
            "new_price": h.new_price,
            "price_type": h.price_type,
            "change_reason": h.change_reason,
            "change_type": h.change_type,
            "changed_at": h.changed_at,
            "changed_by": h.changed_by,
            "effective_from": h.effective_from,
            "effective_to": h.effective_to,
        }
        for h in history
    ]
