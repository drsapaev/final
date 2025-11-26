"""
API endpoints для системы скидок и льгот
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.discount_benefits_service import DiscountBenefitsService
from app.models.discount_benefits import DiscountType, BenefitType

router = APIRouter()


# === PYDANTIC СХЕМЫ ===

class DiscountCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    discount_type: DiscountType
    value: float = Field(..., gt=0)
    min_amount: float = Field(default=0, ge=0)
    max_discount: Optional[float] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    usage_limit: Optional[int] = Field(None, gt=0)
    applies_to_services: bool = True
    applies_to_appointments: bool = True
    applies_to_packages: bool = True
    can_combine_with_others: bool = False
    priority: int = Field(default=0, ge=0)


class DiscountUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    value: Optional[float] = Field(None, gt=0)
    min_amount: Optional[float] = Field(None, ge=0)
    max_discount: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    usage_limit: Optional[int] = Field(None, gt=0)
    applies_to_services: Optional[bool] = None
    applies_to_appointments: Optional[bool] = None
    applies_to_packages: Optional[bool] = None
    can_combine_with_others: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0)


class BenefitCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    benefit_type: BenefitType
    discount_percentage: float = Field(..., gt=0, le=100)
    max_discount_amount: Optional[float] = Field(None, gt=0)
    requires_document: bool = True
    document_types: Optional[str] = None
    age_min: Optional[int] = Field(None, ge=0)
    age_max: Optional[int] = Field(None, ge=0)
    applies_to_services: bool = True
    applies_to_appointments: bool = True
    monthly_limit: Optional[float] = Field(None, gt=0)
    yearly_limit: Optional[float] = Field(None, gt=0)


class BenefitUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    discount_percentage: Optional[float] = Field(None, gt=0, le=100)
    max_discount_amount: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None
    requires_document: Optional[bool] = None
    document_types: Optional[str] = None
    age_min: Optional[int] = Field(None, ge=0)
    age_max: Optional[int] = Field(None, ge=0)
    applies_to_services: Optional[bool] = None
    applies_to_appointments: Optional[bool] = None
    monthly_limit: Optional[float] = Field(None, gt=0)
    yearly_limit: Optional[float] = Field(None, gt=0)


class PatientBenefitCreate(BaseModel):
    patient_id: int
    benefit_id: int
    document_number: Optional[str] = None
    document_issued_date: Optional[datetime] = None
    document_expiry_date: Optional[datetime] = None


class LoyaltyProgramCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    points_per_ruble: float = Field(default=1.0, gt=0)
    min_purchase_for_points: float = Field(default=0, ge=0)
    ruble_per_point: float = Field(default=1.0, gt=0)
    min_points_to_redeem: int = Field(default=100, gt=0)
    max_points_per_purchase: Optional[int] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class DiscountCalculationRequest(BaseModel):
    patient_id: int
    service_ids: List[int]
    amount: float = Field(..., gt=0)


class ApplyDiscountRequest(BaseModel):
    discount_id: int
    amount: float = Field(..., gt=0)
    appointment_id: Optional[int] = None
    visit_id: Optional[int] = None
    invoice_id: Optional[int] = None


class ApplyBenefitRequest(BaseModel):
    patient_benefit_id: int
    amount: float = Field(..., gt=0)
    appointment_id: Optional[int] = None
    visit_id: Optional[int] = None
    invoice_id: Optional[int] = None


class EarnPointsRequest(BaseModel):
    patient_id: int
    program_id: int
    amount: float = Field(..., gt=0)
    appointment_id: Optional[int] = None
    visit_id: Optional[int] = None
    invoice_id: Optional[int] = None


class RedeemPointsRequest(BaseModel):
    patient_id: int
    program_id: int
    points: int = Field(..., gt=0)
    appointment_id: Optional[int] = None
    visit_id: Optional[int] = None
    invoice_id: Optional[int] = None


# === СКИДКИ ===

@router.post("/discounts")
async def create_discount(
    discount_data: DiscountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать скидку"""
    service = DiscountBenefitsService(db)
    try:
        discount = service.create_discount(
            discount_data.dict(),
            created_by=current_user.id
        )
        return {
            "success": True,
            "message": "Скидка создана успешно",
            "discount_id": discount.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/discounts")
async def get_discounts(
    active_only: bool = Query(True),
    service_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список скидок"""
    service = DiscountBenefitsService(db)
    
    if active_only:
        discounts = service.get_active_discounts(service_ids)
    else:
        # Получить все скидки (нужно добавить метод в сервис)
        discounts = db.query(service.db.query(service.Discount)).all()
    
    return {
        "success": True,
        "discounts": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "discount_type": d.discount_type,
                "value": d.value,
                "min_amount": d.min_amount,
                "max_discount": d.max_discount,
                "is_active": d.is_active,
                "usage_count": d.usage_count,
                "usage_limit": d.usage_limit,
                "start_date": d.start_date,
                "end_date": d.end_date,
                "priority": d.priority
            }
            for d in discounts
        ]
    }


@router.put("/discounts/{discount_id}")
async def update_discount(
    discount_id: int,
    discount_data: DiscountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить скидку"""
    from app.models.discount_benefits import Discount
    
    discount = db.query(Discount).filter(Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Скидка не найдена")
    
    # Обновить поля
    update_data = discount_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(discount, field, value)
    
    discount.updated_at = datetime.now()
    db.commit()
    
    return {
        "success": True,
        "message": "Скидка обновлена успешно"
    }


@router.delete("/discounts/{discount_id}")
async def delete_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Удалить скидку"""
    from app.models.discount_benefits import Discount
    
    discount = db.query(Discount).filter(Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Скидка не найдена")
    
    # Деактивировать вместо удаления
    discount.is_active = False
    discount.updated_at = datetime.now()
    db.commit()
    
    return {
        "success": True,
        "message": "Скидка деактивирована успешно"
    }


@router.post("/discounts/apply")
async def apply_discount(
    request: ApplyDiscountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Применить скидку"""
    service = DiscountBenefitsService(db)
    try:
        application = service.apply_discount(
            discount_id=request.discount_id,
            amount=request.amount,
            appointment_id=request.appointment_id,
            visit_id=request.visit_id,
            invoice_id=request.invoice_id,
            applied_by=current_user.id
        )
        
        return {
            "success": True,
            "message": "Скидка применена успешно",
            "application": {
                "id": application.id,
                "original_amount": application.original_amount,
                "discount_amount": application.discount_amount,
                "final_amount": application.final_amount
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# === ЛЬГОТЫ ===

@router.post("/benefits")
async def create_benefit(
    benefit_data: BenefitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать льготу"""
    service = DiscountBenefitsService(db)
    try:
        benefit = service.create_benefit(
            benefit_data.dict(),
            created_by=current_user.id
        )
        return {
            "success": True,
            "message": "Льгота создана успешно",
            "benefit_id": benefit.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/benefits")
async def get_benefits(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список льгот"""
    from app.models.discount_benefits import Benefit
    
    query = db.query(Benefit)
    if active_only:
        query = query.filter(Benefit.is_active == True)
    
    benefits = query.all()
    
    return {
        "success": True,
        "benefits": [
            {
                "id": b.id,
                "name": b.name,
                "description": b.description,
                "benefit_type": b.benefit_type,
                "discount_percentage": b.discount_percentage,
                "max_discount_amount": b.max_discount_amount,
                "is_active": b.is_active,
                "requires_document": b.requires_document,
                "monthly_limit": b.monthly_limit,
                "yearly_limit": b.yearly_limit
            }
            for b in benefits
        ]
    }


@router.post("/benefits/assign")
async def assign_benefit_to_patient(
    request: PatientBenefitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Назначить льготу пациенту"""
    service = DiscountBenefitsService(db)
    try:
        patient_benefit = service.assign_benefit_to_patient(
            patient_id=request.patient_id,
            benefit_id=request.benefit_id,
            document_data={
                'document_number': request.document_number,
                'document_issued_date': request.document_issued_date,
                'document_expiry_date': request.document_expiry_date
            },
            created_by=current_user.id
        )
        
        return {
            "success": True,
            "message": "Льгота назначена пациенту",
            "patient_benefit_id": patient_benefit.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/benefits/verify/{patient_benefit_id}")
async def verify_patient_benefit(
    patient_benefit_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Верифицировать льготу пациента"""
    service = DiscountBenefitsService(db)
    try:
        patient_benefit = service.verify_patient_benefit(
            patient_benefit_id=patient_benefit_id,
            verified_by=current_user.id,
            notes=notes
        )
        
        return {
            "success": True,
            "message": "Льгота верифицирована успешно"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/benefits/patient/{patient_id}")
async def get_patient_benefits(
    patient_id: int,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить льготы пациента"""
    service = DiscountBenefitsService(db)
    patient_benefits = service.get_patient_benefits(patient_id, active_only)
    
    return {
        "success": True,
        "patient_benefits": [
            {
                "id": pb.id,
                "benefit": {
                    "id": pb.benefit.id,
                    "name": pb.benefit.name,
                    "benefit_type": pb.benefit.benefit_type,
                    "discount_percentage": pb.benefit.discount_percentage
                },
                "is_active": pb.is_active,
                "verified": pb.verified,
                "verification_date": pb.verification_date,
                "document_number": pb.document_number,
                "document_expiry_date": pb.document_expiry_date,
                "monthly_used_amount": pb.monthly_used_amount,
                "yearly_used_amount": pb.yearly_used_amount
            }
            for pb in patient_benefits
        ]
    }


@router.post("/benefits/apply")
async def apply_benefit(
    request: ApplyBenefitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Применить льготу"""
    service = DiscountBenefitsService(db)
    try:
        application = service.apply_benefit(
            patient_benefit_id=request.patient_benefit_id,
            amount=request.amount,
            appointment_id=request.appointment_id,
            visit_id=request.visit_id,
            invoice_id=request.invoice_id,
            applied_by=current_user.id
        )
        
        return {
            "success": True,
            "message": "Льгота применена успешно",
            "application": {
                "id": application.id,
                "original_amount": application.original_amount,
                "benefit_amount": application.benefit_amount,
                "final_amount": application.final_amount
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# === ПРОГРАММЫ ЛОЯЛЬНОСТИ ===

@router.post("/loyalty-programs")
async def create_loyalty_program(
    program_data: LoyaltyProgramCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать программу лояльности"""
    service = DiscountBenefitsService(db)
    try:
        program = service.create_loyalty_program(
            program_data.dict(),
            created_by=current_user.id
        )
        return {
            "success": True,
            "message": "Программа лояльности создана успешно",
            "program_id": program.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/loyalty-programs")
async def get_loyalty_programs(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить программы лояльности"""
    from app.models.discount_benefits import LoyaltyProgram
    
    query = db.query(LoyaltyProgram)
    if active_only:
        query = query.filter(LoyaltyProgram.is_active == True)
    
    programs = query.all()
    
    return {
        "success": True,
        "programs": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "points_per_ruble": p.points_per_ruble,
                "ruble_per_point": p.ruble_per_point,
                "min_points_to_redeem": p.min_points_to_redeem,
                "is_active": p.is_active
            }
            for p in programs
        ]
    }


@router.post("/loyalty-programs/enroll")
async def enroll_patient_in_loyalty(
    patient_id: int,
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Записать пациента в программу лояльности"""
    service = DiscountBenefitsService(db)
    try:
        patient_loyalty = service.enroll_patient_in_loyalty(patient_id, program_id)
        return {
            "success": True,
            "message": "Пациент записан в программу лояльности",
            "patient_loyalty_id": patient_loyalty.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/loyalty-programs/earn-points")
async def earn_loyalty_points(
    request: EarnPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Начислить баллы лояльности"""
    service = DiscountBenefitsService(db)
    try:
        points = service.earn_loyalty_points(
            patient_id=request.patient_id,
            program_id=request.program_id,
            amount=request.amount,
            appointment_id=request.appointment_id,
            visit_id=request.visit_id,
            invoice_id=request.invoice_id,
            created_by=current_user.id
        )
        
        return {
            "success": True,
            "message": f"Начислено {points} баллов",
            "points_earned": points
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/loyalty-programs/redeem-points")
async def redeem_loyalty_points(
    request: RedeemPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Списать баллы лояльности"""
    service = DiscountBenefitsService(db)
    try:
        discount_amount = service.redeem_loyalty_points(
            patient_id=request.patient_id,
            program_id=request.program_id,
            points=request.points,
            appointment_id=request.appointment_id,
            visit_id=request.visit_id,
            invoice_id=request.invoice_id,
            created_by=current_user.id
        )
        
        return {
            "success": True,
            "message": f"Списано {request.points} баллов",
            "discount_amount": discount_amount
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/loyalty-programs/balance/{patient_id}/{program_id}")
async def get_loyalty_balance(
    patient_id: int,
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить баланс баллов пациента"""
    service = DiscountBenefitsService(db)
    balance = service.get_patient_loyalty_balance(patient_id, program_id)
    
    return {
        "success": True,
        "balance": balance
    }


# === КОМПЛЕКСНЫЕ ОПЕРАЦИИ ===

@router.post("/calculate-discount")
async def calculate_total_discount(
    request: DiscountCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Рассчитать общую скидку для пациента"""
    service = DiscountBenefitsService(db)
    try:
        result = service.calculate_total_discount(
            patient_id=request.patient_id,
            service_ids=request.service_ids,
            amount=request.amount
        )
        
        return {
            "success": True,
            "calculation": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# === АНАЛИТИКА ===

@router.get("/analytics/discounts")
async def get_discount_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить аналитику по скидкам"""
    service = DiscountBenefitsService(db)
    analytics = service.get_discount_analytics(start_date, end_date)
    
    return {
        "success": True,
        "analytics": analytics
    }


@router.get("/analytics/benefits")
async def get_benefit_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить аналитику по льготам"""
    service = DiscountBenefitsService(db)
    analytics = service.get_benefit_analytics(start_date, end_date)
    
    return {
        "success": True,
        "analytics": analytics
    }


@router.get("/analytics/loyalty")
async def get_loyalty_analytics(
    program_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить аналитику по программе лояльности"""
    service = DiscountBenefitsService(db)
    analytics = service.get_loyalty_analytics(program_id)
    
    return {
        "success": True,
        "analytics": analytics
    }

