"""
API эндпоинты для специализированных панелей (кардиолог, стоматолог)
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.specialized_panels_api_service import (
    SpecializedPanelsApiDomainError,
    SpecializedPanelsApiService,
)

router = APIRouter()


@router.get("/cardiology/patients")
async def get_cardiology_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить пациентов кардиологического отделения"""
    return SpecializedPanelsApiService(db).get_cardiology_patients(
        skip=skip,
        limit=limit,
        search=search,
    )


@router.get("/cardiology/visits")
async def get_cardiology_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
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


@router.get("/cardiology/analytics")
async def get_cardiology_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить аналитику кардиологического отделения"""
    return SpecializedPanelsApiService(db).get_cardiology_analytics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dentistry/patients")
async def get_dentistry_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить пациентов стоматологического отделения"""
    return SpecializedPanelsApiService(db).get_dentistry_patients(
        skip=skip,
        limit=limit,
        search=search,
    )


@router.get("/dentistry/visits")
async def get_dentistry_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
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


@router.get("/dentistry/analytics")
async def get_dentistry_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить аналитику стоматологического отделения"""
    return SpecializedPanelsApiService(db).get_dentistry_analytics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/specialized/services")
async def get_specialized_services(
    department: Optional[str] = Query(
        None, description="Отделение: cardiology, dentistry"
    ),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить услуги специализированных отделений"""
    return SpecializedPanelsApiService(db).get_specialized_services(department=department)


@router.get("/specialized/patient-history/{patient_id}")
async def get_specialized_patient_history(
    patient_id: int,
    department: Optional[str] = Query(
        None, description="Отделение: cardiology, dentistry"
    ),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить историю пациента в специализированном отделении"""
    try:
        return SpecializedPanelsApiService(db).get_specialized_patient_history(
            patient_id=patient_id,
            department=department,
        )
    except SpecializedPanelsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/specialized/statistics")
async def get_specialized_statistics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
    db: Session = Depends(get_db),
):
    """Получить общую статистику по специализированным отделениям"""
    return SpecializedPanelsApiService(db).get_specialized_statistics(
        start_date=start_date,
        end_date=end_date,
    )
