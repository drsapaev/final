"""
CRUD endpoints для управления отделениями в админ-панели
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, require_roles
from app.models.department import Department
from app.models.user import User

router = APIRouter()


# Pydantic schemas
class DepartmentCreate(BaseModel):
    """Схема для создания отделения"""
    key: str
    name_ru: str
    name_uz: Optional[str] = None
    icon: Optional[str] = "folder"
    color: Optional[str] = None
    gradient: Optional[str] = None
    display_order: Optional[int] = 999
    active: Optional[bool] = True
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    """Схема для обновления отделения"""
    name_ru: Optional[str] = None
    name_uz: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    gradient: Optional[str] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    """Схема ответа отделения"""
    id: int
    key: str
    name_ru: str
    name_uz: Optional[str]
    icon: str
    color: Optional[str]
    gradient: Optional[str]
    display_order: int
    active: bool
    description: Optional[str]

    class Config:
        from_attributes = True


@router.get("", response_model=dict)
def list_departments(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить список всех отделений

    Доступно только для администраторов
    """
    query = db.query(Department)

    if active_only:
        query = query.filter(Department.active == True)

    departments = query.order_by(Department.display_order).all()

    return {
        "success": True,
        "data": [DepartmentResponse.from_orm(d).dict() for d in departments],
        "count": len(departments)
    }


@router.get("/{department_id}", response_model=dict)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить отделение по ID

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict()
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Создать новое отделение

    Доступно только для администраторов
    """
    # Проверяем уникальность ключа
    existing = db.query(Department).filter(Department.key == department_data.key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with key '{department_data.key}' already exists"
        )

    # Создаем новое отделение
    department = Department(**department_data.dict())
    db.add(department)
    db.commit()
    db.refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": "Department created successfully"
    }


@router.put("/{department_id}", response_model=dict)
def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Обновить отделение

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    # Обновляем только переданные поля
    update_data = department_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": "Department updated successfully"
    }


@router.delete("/{department_id}", response_model=dict)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Удалить отделение

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    db.delete(department)
    db.commit()

    return {
        "success": True,
        "message": f"Department '{department.name_ru}' deleted successfully"
    }


@router.post("/{department_id}/toggle", response_model=dict)
def toggle_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Переключить активность отделения

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    # Переключаем active
    department.active = not department.active
    db.commit()
    db.refresh(department)

    status_text = "активировано" if department.active else "деактивировано"

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": f"Department '{department.name_ru}' {status_text}"
    }
