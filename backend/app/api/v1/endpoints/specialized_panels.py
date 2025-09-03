"""
API эндпоинты для специализированных панелей (кардиолог, стоматолог)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_roles
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.service import Service
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import and_, or_, func

router = APIRouter()

@router.get("/cardiology/patients")
async def get_cardiology_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить пациентов кардиологического отделения"""
    
    query = db.query(Patient).join(Visit).join(Service).filter(
        Service.name.ilike("%кардиолог%")
    )
    
    if search:
        query = query.filter(
            or_(
                Patient.full_name.ilike(f"%{search}%"),
                Patient.phone.ilike(f"%{search}%")
            )
        )
    
    patients = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "patients": patients,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/cardiology/visits")
async def get_cardiology_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить визиты кардиологического отделения"""
    
    query = db.query(Visit).join(Service).filter(
        Service.name.ilike("%кардиолог%")
    )
    
    if patient_id:
        query = query.filter(Visit.patient_id == patient_id)
    
    if status:
        query = query.filter(Visit.status == status)
    
    if start_date:
        query = query.filter(Visit.created_at >= start_date)
    
    if end_date:
        query = query.filter(Visit.created_at <= end_date)
    
    visits = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "visits": visits,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/cardiology/analytics")
async def get_cardiology_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить аналитику кардиологического отделения"""
    
    # Базовый запрос для кардиологических услуг
    base_query = db.query(Visit).join(Service).filter(
        Service.name.ilike("%кардиолог%")
    )
    
    if start_date:
        base_query = base_query.filter(Visit.created_at >= start_date)
    
    if end_date:
        base_query = base_query.filter(Visit.created_at <= end_date)
    
    # Общая статистика
    total_visits = base_query.count()
    total_revenue = base_query.with_entities(
        func.sum(Visit.payment_amount)
    ).scalar() or 0
    
    # Статистика по статусам
    status_stats = db.query(
        Visit.status,
        func.count(Visit.id).label('count')
    ).join(Service).filter(
        Service.name.ilike("%кардиолог%")
    ).group_by(Visit.status).all()
    
    # Ежедневная статистика
    daily_stats = db.query(
        func.date(Visit.created_at).label('date'),
        func.count(Visit.id).label('visits'),
        func.sum(Visit.payment_amount).label('revenue')
    ).join(Service).filter(
        Service.name.ilike("%кардиолог%")
    ).group_by(func.date(Visit.created_at)).all()
    
    return {
        "total_visits": total_visits,
        "total_revenue": float(total_revenue),
        "status_breakdown": [
            {"status": stat.status, "count": stat.count}
            for stat in status_stats
        ],
        "daily_stats": [
            {
                "date": stat.date.isoformat(),
                "visits": stat.visits,
                "revenue": float(stat.revenue or 0)
            }
            for stat in daily_stats
        ]
    }

@router.get("/dentistry/patients")
async def get_dentistry_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить пациентов стоматологического отделения"""
    
    query = db.query(Patient).join(Visit).join(Service).filter(
        or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%")
        )
    )
    
    if search:
        query = query.filter(
            or_(
                Patient.full_name.ilike(f"%{search}%"),
                Patient.phone.ilike(f"%{search}%")
            )
        )
    
    patients = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "patients": patients,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/dentistry/visits")
async def get_dentistry_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить визиты стоматологического отделения"""
    
    query = db.query(Visit).join(Service).filter(
        or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%")
        )
    )
    
    if patient_id:
        query = query.filter(Visit.patient_id == patient_id)
    
    if status:
        query = query.filter(Visit.status == status)
    
    if start_date:
        query = query.filter(Visit.created_at >= start_date)
    
    if end_date:
        query = query.filter(Visit.created_at <= end_date)
    
    visits = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "visits": visits,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/dentistry/analytics")
async def get_dentistry_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить аналитику стоматологического отделения"""
    
    # Базовый запрос для стоматологических услуг
    base_query = db.query(Visit).join(Service).filter(
        or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%")
        )
    )
    
    if start_date:
        base_query = base_query.filter(Visit.created_at >= start_date)
    
    if end_date:
        base_query = base_query.filter(Visit.created_at <= end_date)
    
    # Общая статистика
    total_visits = base_query.count()
    total_revenue = base_query.with_entities(
        func.sum(Visit.payment_amount)
    ).scalar() or 0
    
    # Статистика по статусам
    status_stats = db.query(
        Visit.status,
        func.count(Visit.id).label('count')
    ).join(Service).filter(
        or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%")
        )
    ).group_by(Visit.status).all()
    
    # Ежедневная статистика
    daily_stats = db.query(
        func.date(Visit.created_at).label('date'),
        func.count(Visit.id).label('visits'),
        func.sum(Visit.payment_amount).label('revenue')
    ).join(Service).filter(
        or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%")
        )
    ).group_by(func.date(Visit.created_at)).all()
    
    return {
        "total_visits": total_visits,
        "total_revenue": float(total_revenue),
        "status_breakdown": [
            {"status": stat.status, "count": stat.count}
            for stat in status_stats
        ],
        "daily_stats": [
            {
                "date": stat.date.isoformat(),
                "visits": stat.visits,
                "revenue": float(stat.revenue or 0)
            }
            for stat in daily_stats
        ]
    }

@router.get("/specialized/services")
async def get_specialized_services(
    department: Optional[str] = Query(None, description="Отделение: cardiology, dentistry"),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить услуги специализированных отделений"""
    
    query = db.query(Service)
    
    if department == "cardiology":
        query = query.filter(Service.name.ilike("%кардиолог%"))
    elif department == "dentistry":
        query = query.filter(
            or_(
                Service.name.ilike("%стоматолог%"),
                Service.name.ilike("%зуб%"),
                Service.name.ilike("%дентал%")
            )
        )
    
    services = query.all()
    
    return {
        "services": services,
        "department": department
    }

@router.get("/specialized/patient-history/{patient_id}")
async def get_specialized_patient_history(
    patient_id: int,
    department: Optional[str] = Query(None, description="Отделение: cardiology, dentistry"),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить историю пациента в специализированном отделении"""
    
    # Проверяем существование пациента
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    # Получаем визиты пациента
    query = db.query(Visit).filter(Visit.patient_id == patient_id)
    
    if department == "cardiology":
        query = query.join(Service).filter(Service.name.ilike("%кардиолог%"))
    elif department == "dentistry":
        query = query.join(Service).filter(
            or_(
                Service.name.ilike("%стоматолог%"),
                Service.name.ilike("%зуб%"),
                Service.name.ilike("%дентал%")
            )
        )
    
    visits = query.order_by(Visit.created_at.desc()).all()
    
    return {
        "patient": patient,
        "visits": visits,
        "department": department,
        "total_visits": len(visits)
    }

@router.get("/specialized/statistics")
async def get_specialized_statistics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db)
):
    """Получить общую статистику по специализированным отделениям"""
    
    # Статистика по кардиологии
    cardiology_query = db.query(Visit).join(Service).filter(
        Service.name.ilike("%кардиолог%")
    )
    
    if start_date:
        cardiology_query = cardiology_query.filter(Visit.created_at >= start_date)
    if end_date:
        cardiology_query = cardiology_query.filter(Visit.created_at <= end_date)
    
    cardiology_visits = cardiology_query.count()
    cardiology_revenue = cardiology_query.with_entities(
        func.sum(Visit.payment_amount)
    ).scalar() or 0
    
    # Статистика по стоматологии
    dentistry_query = db.query(Visit).join(Service).filter(
        or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%")
        )
    )
    
    if start_date:
        dentistry_query = dentistry_query.filter(Visit.created_at >= start_date)
    if end_date:
        dentistry_query = dentistry_query.filter(Visit.created_at <= end_date)
    
    dentistry_visits = dentistry_query.count()
    dentistry_revenue = dentistry_query.with_entities(
        func.sum(Visit.payment_amount)
    ).scalar() or 0
    
    return {
        "cardiology": {
            "visits": cardiology_visits,
            "revenue": float(cardiology_revenue),
            "average_visit_value": float(cardiology_revenue / cardiology_visits) if cardiology_visits > 0 else 0
        },
        "dentistry": {
            "visits": dentistry_visits,
            "revenue": float(dentistry_revenue),
            "average_visit_value": float(dentistry_revenue / dentistry_visits) if dentistry_visits > 0 else 0
        },
        "total": {
            "visits": cardiology_visits + dentistry_visits,
            "revenue": float(cardiology_revenue + dentistry_revenue)
        }
    }
