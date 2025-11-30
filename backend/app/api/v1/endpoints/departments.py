"""
Departments API endpoint
Provides department/tab management for registrar panel
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.department import Department
from app.models.user import User

router = APIRouter()


@router.get("/active")
@router.get("")
async def get_departments(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get list of departments/tabs

    Fetches departments from database with optional filtering by active status.
    """
    query = db.query(Department)

    if active_only:
        query = query.filter(Department.active == True)

    departments = query.order_by(Department.display_order).all()

    # Преобразуем в формат, ожидаемый frontend
    departments_data = [
        {
            "id": dept.id,
            "key": dept.key,
            "name": dept.name_ru,  # Для обратной совместимости
            "name_ru": dept.name_ru,
            "name_uz": dept.name_uz,
            "active": dept.active,
            "display_order": dept.display_order,
            "icon": dept.icon,
            "color": dept.color,
            "gradient": dept.gradient,
        }
        for dept in departments
    ]

    return {"success": True, "data": departments_data, "count": len(departments_data)}


@router.get("/{department_id}")
async def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single department by ID"""
    from fastapi import HTTPException

    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    return {
        "success": True,
        "data": {
            "id": department.id,
            "key": department.key,
            "name": department.name_ru,
            "name_ru": department.name_ru,
            "name_uz": department.name_uz,
            "active": department.active,
            "display_order": department.display_order,
            "icon": department.icon,
            "color": department.color,
            "gradient": department.gradient,
        },
    }
