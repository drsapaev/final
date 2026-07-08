"""
Departments API endpoint
Provides department/tab management for registrar panel
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.services.departments_api_service import (
    DepartmentsApiDomainError,
    DepartmentsApiService,
)

router = APIRouter()


@router.get("/active", response_model=dict[str, Any])
@router.get("", response_model=dict[str, Any])
async def get_departments(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get list of departments/tabs

    Fetches departments from database with optional filtering by active status.
    """
    return DepartmentsApiService(db).get_departments(active_only=active_only)


@router.get("/{department_id}", response_model=dict[str, Any])
async def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single department by ID"""
    service = DepartmentsApiService(db)
    try:
        return service.get_department(department_id=department_id)
    except DepartmentsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
