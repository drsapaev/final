"""
API endpoints for Role management
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.role_permission import Role
from app.models.user import User
from app.schemas.role import (
    RoleCreate,
    RoleListResponse,
    RoleOptionResponse,
    RoleOptionsListResponse,
    RoleResponse,
    RoleUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=RoleListResponse)
async def get_roles(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_system: Optional[bool] = Query(None, description="Filter by system roles"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all roles.
    
    Returns a list of all roles, optionally filtered by active/system status.
    """
    try:
        query = db.query(Role)
        
        if is_active is not None:
            query = query.filter(Role.is_active == is_active)
        
        if is_system is not None:
            query = query.filter(Role.is_system == is_system)
        
        # Order by level (higher level = more privileges)
        roles = query.order_by(Role.level.desc()).all()
        
        return RoleListResponse(
            roles=[RoleResponse.model_validate(role) for role in roles],
            total=len(roles)
        )
    except Exception as e:
        logger.error(f"Error fetching roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка ролей: {str(e)}"
        )


@router.get("/options", response_model=RoleOptionsListResponse)
async def get_role_options(
    include_all: bool = Query(False, description="Include 'All roles' option for filters"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get roles as options for dropdowns.
    
    Returns simplified role list with value/label pairs.
    Used for role selection in forms and filters.
    """
    try:
        roles = db.query(Role).filter(Role.is_active == True).order_by(Role.level.desc()).all()
        
        options = []
        
        # Add "All roles" option for filters if requested
        if include_all:
            options.append(RoleOptionResponse(value="", label="Все роли"))
        
        # Add each role
        for role in roles:
            options.append(RoleOptionResponse(
                value=role.name,
                label=role.display_name
            ))
        
        return RoleOptionsListResponse(options=options)
    except Exception as e:
        logger.error(f"Error fetching role options: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка ролей: {str(e)}"
        )


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific role by ID."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Роль не найдена"
        )
    return RoleResponse.model_validate(role)


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new role.
    
    Only Admin users can create roles.
    """
    # Check admin permission
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут создавать роли"
        )
    
    # Check if role name already exists
    existing = db.query(Role).filter(Role.name == role_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Роль с именем '{role_data.name}' уже существует"
        )
    
    try:
        role = Role(**role_data.model_dump())
        db.add(role)
        db.commit()
        db.refresh(role)
        return RoleResponse.model_validate(role)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания роли: {str(e)}"
        )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a role.
    
    Only Admin users can update roles.
    System roles have limited editability.
    """
    # Check admin permission
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут изменять роли"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Роль не найдена"
        )
    
    # System roles can only have display_name and description changed
    if role.is_system:
        allowed_fields = {"display_name", "description"}
        update_data = role_data.model_dump(exclude_unset=True)
        for field in update_data:
            if field not in allowed_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Нельзя изменить поле '{field}' для системной роли"
                )
    
    try:
        update_data = role_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(role, field, value)
        
        db.commit()
        db.refresh(role)
        return RoleResponse.model_validate(role)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления роли: {str(e)}"
        )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a role.
    
    Only Admin users can delete roles.
    System roles cannot be deleted.
    """
    # Check admin permission
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут удалять роли"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Роль не найдена"
        )
    
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить системную роль"
        )
    
    try:
        db.delete(role)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления роли: {str(e)}"
        )
