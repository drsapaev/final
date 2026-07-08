"""
API эндпоинты для специализированных панелей (кардиолог, стоматолог)
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.specialized_panels_api_service import (
    SpecializedPanelsApiDomainError,
    SpecializedPanelsApiService,
)

router = APIRouter()

FINANCIAL_SPECIALIZED_PANEL_ROLES = ("Admin", "Manager")


@router.get("/cardiology/patients", response_model=dict[str, Any])
async def get_cardiology_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = Query(None),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    db: Session = Depends(get_db),
):
    """Получить пациентов кардиологического отделения"""
    return SpecializedPanelsApiService(db).get_cardiology_patients(
        skip=skip,
        limit=limit,
        search=search,
    )


@router.get("/cardiology/visits", response_model=dict[str, Any])
async def get_cardiology_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = Query(None),
    status: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    db: Session = Depends(get_db),
):
    """Получить визиты кардиологического отделения"""
    return SpecializedPanelsApiService(db).get_cardiology_visits(
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/cardiology/analytics", response_model=dict[str, Any])
async def get_cardiology_analytics(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(require_roles(*FINANCIAL_SPECIALIZED_PANEL_ROLES)),
    db: Session = Depends(get_db),
):
    """Получить аналитику кардиологического отделения"""
    return SpecializedPanelsApiService(db).get_cardiology_analytics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dentistry/patients", response_model=dict[str, Any])
async def get_dentistry_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = Query(None),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    db: Session = Depends(get_db),
):
    """Получить пациентов стоматологического отделения"""
    return SpecializedPanelsApiService(db).get_dentistry_patients(
        skip=skip,
        limit=limit,
        search=search,
    )


@router.get("/dentistry/visits", response_model=dict[str, Any])
async def get_dentistry_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = Query(None),
    status: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    db: Session = Depends(get_db),
):
    """Получить визиты стоматологического отделения"""
    return SpecializedPanelsApiService(db).get_dentistry_visits(
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dentistry/analytics", response_model=dict[str, Any])
async def get_dentistry_analytics(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(require_roles(*FINANCIAL_SPECIALIZED_PANEL_ROLES)),
    db: Session = Depends(get_db),
):
    """Получить аналитику стоматологического отделения"""
    return SpecializedPanelsApiService(db).get_dentistry_analytics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/specialized/services", response_model=dict[str, Any])
async def get_specialized_services(
    department: str | None = Query(
        None, description="Отделение: cardiology, dentistry"
    ),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    db: Session = Depends(get_db),
):
    """Получить услуги специализированных отделений"""
    return SpecializedPanelsApiService(db).get_specialized_services(department=department)


@router.get("/specialized/patient-history/{patient_id}", response_model=dict[str, Any])
async def get_specialized_patient_history(
    patient_id: int,
    department: str | None = Query(
        None, description="Отделение: cardiology, dentistry"
    ),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    db: Session = Depends(get_db),
):
    """Получить историю пациента в специализированном отделении.

    SPEC-AUDIT-28 P0-1: Doctor может видеть только пациентов, с которыми
    есть визит, привязанный к этому врачу. Раньше любой Doctor мог
    читать историю любого пациента.
    """
    # Ownership check for non-Admin
    if current_user.role != "Admin" and not current_user.is_superuser:
        from app.models.visit import Visit
        from app.models.clinic import Doctor
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            raise HTTPException(status_code=403, detail="Doctor profile not found")
        has_visit = db.query(Visit).filter(
            Visit.patient_id == patient_id,
            Visit.doctor_id == doctor.id,
        ).first()
        if not has_visit:
            raise HTTPException(status_code=403, detail="Access denied to this patient")
    try:
        return SpecializedPanelsApiService(db).get_specialized_patient_history(
            patient_id=patient_id,
            department=department,
        )
    except SpecializedPanelsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/specialized/statistics", response_model=dict[str, Any])
async def get_specialized_statistics(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    current_user: User = Depends(require_roles(*FINANCIAL_SPECIALIZED_PANEL_ROLES)),
    db: Session = Depends(get_db),
):
    """Получить общую статистику по специализированным отделениям"""
    return SpecializedPanelsApiService(db).get_specialized_statistics(
        start_date=start_date,
        end_date=end_date,
    )
